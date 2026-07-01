"""
Full candidate-discovery pipeline orchestrator.

Wires the 9 stages into one end-to-end run:
  input normalize → bias scan → JD parse → embed → retrieve → rerank →
  fuse → explain → skill-gap → galaxy project

Each stage is independent; this module owns ordering, timing, and the
data shapes passed between them. Designed so any stage can fail gracefully
without aborting the whole pipeline — the recruiter always gets a result.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from .config import get_settings
from .dataset import load_dataset, profiles_to_feature_matrix
from .features import build_feature_vector
from .output_writer import write_ranked_output
from .schemas import (
    BiasFlag,
    BharatContextSummary,
    CandidateBharatAdjustment,
    GalaxyPayload,
    PipelineInput,
    PipelineMetrics,
    PipelineResult,
    RankedCandidate,
    SkillGapReport,
    StructuredJD,
)
from .features import recency_of_activity
from .stages.anomaly_detector import AnomalyDetector
from .stages.bias_detector import BiasDetector
from .stages.embedder import EMBED_DIM, Embedder
from .stages.explainer import explain_ranking
from .stages.fusion_ranker import FEATURE_COLS, FusionRanker
from .stages.galaxy import project_galaxy
from .stages.jd_parser import parse_jd
from .stages.reranker import Reranker
from .stages.retriever import Retriever
from .stages.skill_gap import SkillGapGenerator
from .stages.translator import Translator
from .stages.voice_input import VoiceTranscriber
from .stages.bharat_contextualizer import BharatContextualizer
from .stages.skill_decay import SkillDecayAnalyzer
from .stages.candidate_intent import CandidateIntentEngine
from .stages.hire_predict import HirePredictStore, HirePredictModel
# v3.0 stages
from .stages.resume_shield import ResumeShieldEngine
from .stages.diverse_hire import DiverseHireEngine
from .stages.dpdp_layer import DPDPComplianceEngine
from .stages.submission_ranker import SubmissionRanker

log = logging.getLogger(__name__)

StageCallback = Callable[[str, Optional[str], Optional[float]], None]


class CandidateDiscoveryPipeline:
    """
    Owns long-lived state (loaded models, indexed candidate pool) so that
    repeated JD submissions reuse the warm index. Thread-hostile: serve from
    a single event loop or wrap calls externally.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.translator = Translator()
        self.voice = VoiceTranscriber()
        self.bias = BiasDetector()
        self.embedder = Embedder()
        self.retriever = Retriever(dim=EMBED_DIM)
        self.reranker = Reranker()
        self.fusion = FusionRanker()
        self.skill_gap = SkillGapGenerator()
        self.anomaly = AnomalyDetector()
        self.bharat = BharatContextualizer(
            use_indictrans2=self.settings.enable_indictrans2,
            enabled=self.settings.enable_bharat_intelligence,
        )
        # v2.0 Feature Expansion stages
        self.skill_decay = SkillDecayAnalyzer()
        self.intent_engine = CandidateIntentEngine()
        _hp_store = HirePredictStore()
        self.hire_predict = HirePredictModel(_hp_store)
        # v3.0 Feature Expansion stages
        self.resume_shield  = ResumeShieldEngine()
        self.diverse_hire   = DiverseHireEngine()
        self.dpdp           = DPDPComplianceEngine()
        self.submission_ranker = SubmissionRanker()

        # Cached candidate pool state
        self._profiles: list[Any] = []
        self._index_ready = False
        self._trust_scores: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Index warming (run once at boot or on first request)
    # ------------------------------------------------------------------

    def warm_index(self, dataset_path: str | None = None) -> int:
        """Load the candidate pool, embed + index it, and compute trust scores."""
        profiles = load_dataset(dataset_path)
        self._profiles = profiles

        # 1. Anomaly / trust scores at ingestion time (JD-independent)
        ids, _, matrix = profiles_to_feature_matrix(profiles)
        if ids:
            trust = self.anomaly.fit_score(matrix)
            self._trust_scores = dict(zip(ids, [float(t) for t in trust]))
            for p in profiles:
                p.trust_score = self._trust_scores.get(p.id, 1.0)

        # 2. Embed + upsert into the retriever index
        profile_texts = [p.profile_text for p in profiles]
        vectors = self.embedder.embed_candidates_batch(profile_texts)
        payloads = [self._payload_for(p) for p in profiles]
        self.retriever.upsert_candidates([p.id for p in profiles], vectors, payloads)

        self._index_ready = True
        log.info(
            "Index warmed: %d candidates, backend=%s, embedder_fallback=%s",
            len(profiles),
            self.retriever.backend_name,
            self.embedder.is_fallback,
        )
        return len(profiles)

    def _payload_for(self, profile: Any) -> dict[str, Any]:
        """Compact payload stored in the vector index for retrieval hits."""
        education = []
        if profile.education:
            education = [e.model_dump() for e in profile.education]
        return {
            "id": profile.id,
            "name": profile.name,
            "summary": profile.summary,
            "skills": list(profile.skills),
            "current_title": profile.current_title,
            "profile_text": profile.profile_text,
            "metadata": profile.metadata.model_dump(),
            "trust_score": float(profile.trust_score or 1.0),
            "city": profile.city or profile.location,
            "location": profile.location or profile.city,
            "institution": profile.institution,
            "degree": profile.degree,
            "education": education,
        }

    def ensure_index(self) -> None:
        if not self._index_ready:
            self.warm_index()

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(
        self,
        jd_input: PipelineInput | dict[str, Any],
        on_stage: StageCallback | None = None,
    ) -> PipelineResult:
        if isinstance(jd_input, dict):
            jd_input = PipelineInput(**jd_input)

        start = time.perf_counter()
        jd_id = f"jd_{uuid.uuid4().hex[:6]}"
        s = self.settings

        def emit(stage: str, message: str | None = None, progress: float | None = None) -> None:
            if on_stage:
                try:
                    on_stage(stage, message, progress)
                except Exception:  # noqa: BLE001 — never let a progress callback abort the run
                    log.debug("on_stage callback raised; ignored.")

        # 0. Ensure index is warm
        self.ensure_index()

        # 1. Input normalization (voice / Hindi / plain text)
        emit("input_normalization", "Normalizing input", 0.05)
        jd_text = self._normalize_input(jd_input, emit)

        # 2. Bias scan (non-blocking in spirit; sync here for PoC simplicity)
        emit("bias_scan", "Scanning JD for biased language", 0.1)
        bias_flags = [BiasFlag(**f) for f in self.bias.scan(jd_text)] if jd_text else []

        # 3. Deep job understanding
        emit("jd_parsing", "Parsing JD into structured requirements", 0.2)
        structured_jd = parse_jd(jd_text) if jd_text else StructuredJD(role_title="Untitled Role")
        jd_dict = structured_jd.model_dump()

        # 3.5 DiverseHire™ JD analysis (non-blocking)
        diverse_jd_analysis: dict = {}
        try:
            diverse_jd_analysis = self.diverse_hire.analyze_jd(jd_text or "")
            if diverse_jd_analysis.get("gender_language", {}).get("is_biased"):
                log.info("DiverseHire™: JD contains gendered language (%s)",
                         diverse_jd_analysis["gender_language"]["bias_direction"])
        except Exception as exc:  # noqa: BLE001
            log.warning("DiverseHire™ JD analysis failed (non-fatal): %s", exc)

        # 3.6 DPDP JD validation
        try:
            dpdp_jd_check = self.dpdp.validate_jd(jd_text or "")
            if not dpdp_jd_check.get("jd_compliant", True):
                log.warning("DPDP: JD has %d prohibited attribute violation(s)",
                            dpdp_jd_check.get("violation_count", 0))
        except Exception as exc:  # noqa: BLE001
            log.warning("DPDP JD validation failed (non-fatal): %s", exc)

        # 4. Embed JD + retrieve top-K
        emit("embedding", "Embedding JD", 0.3)
        jd_vector = self.embedder.embed_jd(jd_dict)

        emit("retrieval", f"Retrieving top-{s.retrieval_top_k} candidates", 0.4)
        candidates = self.retriever.search(jd_vector, top_k=s.retrieval_top_k)
        retrieval_count = len(candidates)

        if not candidates:
            log.warning("Retrieval returned no candidates.")
            return self._empty_result(jd_id, structured_jd, bias_flags, start)

        # 4.5 ResumeShield™ — run 6 fraud detectors before reranking
        emit("resume_shield", "ResumeShield™: scanning for fraud signals", 0.48)
        try:
            candidates = self.resume_shield.analyze_batch(candidates, jd_dict)
            shield_blocked = sum(1 for c in candidates if c.get("fraud_label") == "blocked")
            if shield_blocked:
                log.info("ResumeShield™ flagged %d blocked candidates (kept, flagged for recruiter)", shield_blocked)
        except Exception as exc:  # noqa: BLE001
            log.warning("ResumeShield™ failed (non-fatal): %s", exc)

        # 5. Rerank
        emit("reranking", f"Cross-encoder reranking to top-{s.rerank_top_k}", 0.55)
        reranked = self.reranker.rerank(jd_text, candidates, top_k=s.rerank_top_k)
        rerank_count = len(reranked)

        # 5.5 Bharat Intelligence Layer — context normalization before fusion
        emit("bharat_contextualization", "Applying Bharat Intelligence Layer", 0.62)
        self._prepare_candidates_for_bharat(reranked)
        jd_skill_pool = {
            sk.lower()
            for sk in (jd_dict.get("must_have_skills", []) or [])
            + (jd_dict.get("nice_to_have_skills", []) or [])
            if sk
        }
        reranked = self.bharat.enrich(reranked, skill_pool=jd_skill_pool)
        bharat_summary = self.bharat.last_summary
        bharat_adjustments = self._collect_bharat_adjustments(reranked)

        # 6. Build fusion feature rows
        emit("fusion", "Fusing semantic + behavioral signals", 0.7)
        feature_rows = []
        for c in reranked:
            sim = c.get("embedding_similarity", 0.0)
            rerank_score = c.get("rerank_score", 0.0)
            row = build_feature_vector(
                embedding_similarity=sim,
                rerank_score=rerank_score,
                structured_jd=jd_dict,
                candidate=c,
            )
            row["id"] = c.get("id")
            row["name"] = c.get("name")
            row["skills"] = c.get("skills", [])
            row["current_title"] = c.get("current_title")
            row["summary"] = c.get("summary", "")
            row["metadata"] = c.get("metadata", {})
            row["profile_text"] = c.get("profile_text", "")
            row["embedding_similarity_raw"] = sim  # keep raw for galaxy projection
            row["trust_score"] = float(c.get("trust_score", self._trust_scores.get(c.get("id"), 1.0)))
            # BIL metadata for ranked output transparency
            row["tier_adjusted"] = c.get("tier_adjusted", False)
            row["bharat_tier"] = c.get("bharat_tier")
            row["engagement_delta"] = c.get("engagement_delta", 0.0)
            row["institution_tier_score"] = c.get("institution_tier_score", 0.5)
            row["institution_nirf_matched"] = c.get("institution_nirf_matched", False)
            row["code_switch_detected"] = c.get("code_switch_detected", False)
            row["skills_added_by_bil3"] = c.get("skills_added_by_bil3", [])
            row["informal_sector_score"] = c.get("informal_sector_score", 0.0)
            row["informal_sector_explanation"] = c.get("informal_sector_explanation", "")
            row["informal_skills_injected"] = c.get("informal_skills_injected", [])
            feature_rows.append(row)
        df = pd.DataFrame(feature_rows)

        ranked_df = self.fusion.score(df)
        shortlist = ranked_df.head(s.shortlist_size).reset_index(drop=True)
        near_miss = ranked_df.iloc[s.shortlist_size : s.shortlist_size + s.near_miss_band_size]

        # ── v2.0: SkillDecay™ enrichment (replaces static skill_overlap_ratio) ──
        emit("skill_decay", "Computing temporal skill relevance (SkillDecay™)", 0.79)
        try:
            shortlist_records = shortlist.to_dict(orient="records")
            enriched = self.skill_decay.enrich_candidates(shortlist_records, jd_dict)
            shortlist = pd.DataFrame(enriched)
        except Exception as exc:  # noqa: BLE001
            log.warning("SkillDecay™ enrichment failed (non-fatal): %s", exc)

        # ── v2.0: CandidateIntent™ enrichment (mobility scoring) ──────────────
        emit("candidate_intent", "Scoring candidate mobility and intent (CandidateIntent™)", 0.81)
        try:
            intent_records = shortlist.to_dict(orient="records")
            enriched_intent = self.intent_engine.score_batch(intent_records, jd_dict)
            shortlist = pd.DataFrame(enriched_intent)
        except Exception as exc:  # noqa: BLE001
            log.warning("CandidateIntent™ enrichment failed (non-fatal): %s", exc)

        # ── v2.0: HirePredict™ predictions (if model is trained) ──────────────
        emit("hire_predict", "Attaching hire probability predictions (HirePredict™)", 0.825)
        try:
            hp_records = shortlist.to_dict(orient="records")
            hp_enriched = self.hire_predict.predict(hp_records)
            shortlist = pd.DataFrame(hp_enriched)
        except Exception as exc:  # noqa: BLE001
            log.warning("HirePredict™ predictions failed (non-fatal): %s", exc)

        # ── v3.0: DiverseHire™ shortlist diversity scoring ──────────────────
        emit("diverse_hire", "DiverseHire™: scoring shortlist diversity", 0.827)
        try:
            shortlist_records = shortlist.to_dict(orient="records")
            diverse_shortlist = self.diverse_hire.score_shortlist(shortlist_records)
            # Attach diversity_score to each row so frontend can display it
            div_score = diverse_shortlist.get("diversity_score", {}).get("diversity_score", None)
            if div_score is not None:
                shortlist["diversity_score"] = div_score
        except Exception as exc:  # noqa: BLE001
            log.warning("DiverseHire™ shortlist scoring failed (non-fatal): %s", exc)

        # 7. Explainability for the shortlist
        emit("explainability", "Generating per-candidate justifications", 0.82)
        ranked_candidates = self._build_ranked(shortlist)

        # 8. Skill-gap reports for the near-miss band
        emit("skill_gap", "Generating near-miss skill-gap reports", 0.9)
        skill_gaps = self._build_skill_gaps(jd_dict, near_miss)

        # 9. Galaxy projection (use the candidate embedding vectors + ranks/scores)
        emit("galaxy_projection", "Projecting the candidate galaxy", 0.95)
        galaxy = self._build_galaxy(jd_id, jd_vector, ranked_df)

        latency_ms = int((time.perf_counter() - start) * 1000)
        emit("complete", f"Done in {latency_ms}ms", 1.0)

        result = PipelineResult(
            jdId=jd_id,
            structured_jd=structured_jd,
            bias_flags=bias_flags,
            ranked_shortlist=ranked_candidates,
            near_miss_skill_gaps=skill_gaps,
            galaxy=galaxy,
            metrics=PipelineMetrics(
                retrieval_count=retrieval_count,
                rerank_count=rerank_count,
                latency_ms=latency_ms,
            ),
            bharat_context=(
                BharatContextSummary(**bharat_summary.to_dict())
                if bharat_summary
                else None
            ),
            bharat_adjustments=bharat_adjustments,
        )

        # Persist the submission artifact every run
        try:
            path = write_ranked_output(result)
            log.info("Wrote submission output → %s", path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to write submission output (%s).", exc)

        return result


    # ------------------------------------------------------------------
    # Galaxy reweight (recruiters drag sliders → live reclustering)
    # ------------------------------------------------------------------

    def reweight_galaxy(
        self,
        jd_id: str,
        weights: dict[str, float],
        ranked_snapshot: pd.DataFrame | None = None,
    ) -> GalaxyPayload | None:
        """Re-score under recruiter-adjusted weights and re-project the galaxy."""
        if ranked_snapshot is None or ranked_snapshot.empty:
            return None
        reweighted = self.fusion.score(ranked_snapshot, weights=weights)
        ranks = list(range(1, len(reweighted) + 1))
        scores = reweighted["fusion_score"].clip(0.0, 1.0).tolist() if "fusion_score" in reweighted else [0.5] * len(reweighted)
        ids = reweighted["id"].astype(str).tolist() if "id" in reweighted else []
        clusters = [self._cluster_for(row) for _, row in reweighted.iterrows()]
        # Use stored embedding similarity as a proxy vector for projection
        vectors = self._proxy_vectors(reweighted)
        nodes = project_galaxy(
            jd_vector=np.zeros(EMBED_DIM, dtype=np.float32),
            candidate_vectors=vectors,
            ranks=ranks,
            scores=scores,
            clusters=clusters,
            candidate_ids=ids,
        )
        return GalaxyPayload(
            jdId=jd_id,
            jdCore={"x": 0.0, "y": 0.0, "z": 0.0},
            nodes=nodes,  # project_galaxy already returns schema-matching dicts
            weights=weights,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _prepare_candidates_for_bharat(self, candidates: list[dict[str, Any]]) -> None:
        """Flatten metadata behavioral signals onto candidate dicts for BIL-1."""
        for c in candidates:
            meta = c.get("metadata", {}) or {}
            c["engagement_score"] = float(meta.get("engagement_score", 0.5))
            c["recency_of_activity"] = recency_of_activity(
                int(meta.get("last_activity_days_ago", 0))
            )

    def _collect_bharat_adjustments(
        self, candidates: list[dict[str, Any]]
    ) -> dict[str, CandidateBharatAdjustment]:
        """Build per-candidate BIL transparency metadata for the dashboard."""
        out: dict[str, CandidateBharatAdjustment] = {}
        for c in candidates:
            cid = str(c.get("id", ""))
            if not cid:
                continue
            out[cid] = CandidateBharatAdjustment(
                tier_adjusted=bool(c.get("tier_adjusted", False)),
                bharat_tier=str(c.get("bharat_tier", "tier_2")),
                engagement_delta=float(c.get("engagement_delta", 0.0)),
                institution_score=float(c.get("institution_tier_score", 0.5)),
                institution_matched=bool(c.get("institution_nirf_matched", False)),
                code_switch_detected=bool(c.get("code_switch_detected", False)),
                skills_added_by_bil3=list(c.get("skills_added_by_bil3", []) or []),
                informal_sector_score=float(c.get("informal_sector_score", 0.0)),
                informal_explanation=str(c.get("informal_sector_explanation", "")),
                skills_added_by_bil4=list(c.get("informal_skills_injected", []) or []),
            )
        return out

    def _bharat_adjustment_for_row(self, row: pd.Series) -> CandidateBharatAdjustment | None:
        cid = str(row.get("id", ""))
        if not cid:
            return None
        return CandidateBharatAdjustment(
            tier_adjusted=bool(row.get("tier_adjusted", False)),
            bharat_tier=str(row.get("bharat_tier", "tier_2")),
            engagement_delta=float(row.get("engagement_delta", 0.0)),
            institution_score=float(row.get("institution_tier_score", 0.5)),
            institution_matched=bool(row.get("institution_nirf_matched", False)),
            code_switch_detected=bool(row.get("code_switch_detected", False)),
            skills_added_by_bil3=list(row.get("skills_added_by_bil3", []) or []),
            informal_sector_score=float(row.get("informal_sector_score", 0.0)),
            informal_explanation=str(row.get("informal_sector_explanation", "")),
            skills_added_by_bil4=list(row.get("informal_skills_injected", []) or []),
        )

    def _normalize_input(self, jd_input: PipelineInput, emit: StageCallback) -> str:
        if jd_input.audio_path:
            emit("input_normalization", "Transcribing voice input", 0.07)
            try:
                text = self.voice.transcribe(jd_input.audio_path)
            except Exception as exc:  # noqa: BLE001
                log.warning("Voice transcription failed (%s); treating input as empty.", exc)
                text = jd_input.text or ""
        elif jd_input.language and jd_input.language.lower() in {"hi", "hin", "hindi"}:
            emit("input_normalization", "Translating Hindi JD → English", 0.07)
            text = self.translator.translate_to_english(jd_input.text or "")
        else:
            text = jd_input.text or ""
        return (text or "").strip()

    def _build_ranked(self, shortlist_df: pd.DataFrame) -> list[RankedCandidate]:
        out: list[RankedCandidate] = []
        for rank, (_, row) in enumerate(shortlist_df.iterrows(), start=1):
            contribs = row.get("feature_contributions", {})
            if isinstance(contribs, dict):
                top = sorted(
                    ((k, float(v)) for k, v in contribs.items() if k != "base_value"),
                    key=lambda kv: abs(kv[1]),
                    reverse=True,
                )[:3]
            else:
                top = []
            explanation = explain_ranking(rank, top)
            bharat_adj = self._bharat_adjustment_for_row(row)
            out.append(
                RankedCandidate(
                    rank=rank,
                    candidate_id=str(row["id"]),
                    name=row.get("name"),
                    score=round(float(row["fusion_score"]), 4),
                    explanation=explanation,
                    trust_score=round(float(row.get("trust_score", 1.0)), 4),
                    feature_contributions=contribs if isinstance(contribs, dict) else None,
                    skills=list(row.get("skills", []) or []),
                    current_title=row.get("current_title"),
                    bharat_adjustment=bharat_adj,
                )
            )
        return out

    def _build_skill_gaps(self, jd_dict: dict[str, Any], near_miss_df: pd.DataFrame) -> list[SkillGapReport]:
        if near_miss_df.empty or not self.settings.enable_skill_gap_reports:
            return []
        reports: list[SkillGapReport] = []
        for _, row in near_miss_df.iterrows():
            candidate_profile = {
                "summary": row.get("summary", ""),
                "skills": list(row.get("skills", []) or []),
            }
            text = self.skill_gap.generate(jd_dict, candidate_profile)
            missing = list(
                set(jd_dict.get("must_have_skills", []) or [])
                - {s.lower() for s in (row.get("skills", []) or [])}
            )
            reports.append(
                SkillGapReport(
                    candidate_id=str(row["id"]),
                    name=row.get("name"),
                    report=text,
                    missing_skills=missing,
                )
            )
        return reports

    def _build_galaxy(
        self,
        jd_id: str,
        jd_vector: np.ndarray,
        ranked_df: pd.DataFrame,
    ) -> GalaxyPayload:
        ranks = list(range(1, len(ranked_df) + 1))
        scores = ranked_df["fusion_score"].clip(0.0, 1.0).tolist() if len(ranked_df) else []
        ids = ranked_df["id"].astype(str).tolist() if len(ranked_df) else []
        clusters = [self._cluster_for(row) for _, row in ranked_df.iterrows()]
        vectors = self._proxy_vectors(ranked_df)
        nodes = project_galaxy(
            jd_vector=jd_vector,
            candidate_vectors=vectors,
            ranks=ranks,
            scores=scores,
            clusters=clusters,
            candidate_ids=ids,
        )
        from .stages.fusion_ranker import default_weights

        return GalaxyPayload(
            jdId=jd_id,
            jdCore={"x": 0.0, "y": 0.0, "z": 0.0},
            nodes=nodes,
            weights=default_weights(),
        )

    def _cluster_for(self, row: pd.Series) -> str:
        """Derive a cluster label from the candidate's dominant skill domain."""
        skills = {str(s).lower() for s in (row.get("skills", []) or [])}
        from .dataset import SKILL_DOMAINS

        best, best_score = "general", 0
        for domain, domain_skills in SKILL_DOMAINS.items():
            overlap = len(skills & {s.lower() for s in domain_skills})
            if overlap > best_score:
                best, best_score = domain, overlap
        return best

    def _proxy_vectors(self, df: pd.DataFrame) -> np.ndarray:
        """
        Build pseudo-vectors from fusion features for galaxy projection.
        We use the feature columns themselves as a low-dim representation —
        UMAP/SVD then project to 3D. This keeps the galaxy's geometry
        consistent with the fusion score's basis.
        """
        if len(df) == 0:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        feat = df[FEATURE_COLS].to_numpy(dtype=np.float32) if all(c in df.columns for c in FEATURE_COLS) else np.zeros((len(df), 1), dtype=np.float32)
        # Pad/truncate to EMBED_DIM so project_galaxy's SVD has room to work.
        if feat.shape[1] < EMBED_DIM:
            pad = np.zeros((feat.shape[0], EMBED_DIM - feat.shape[1]), dtype=np.float32)
            feat = np.hstack([feat, pad])
        return feat

    def run_submission_mode(
        self,
        candidates_path: str | None = None,
        output_path: str | None = None,
        top_k: int | None = None,
    ) -> Path:
        """
        Hackathon Phase B: rank full candidates.jsonl → submission CSV via polyhire-redrob/rank.py.
        """
        s = self.settings
        cand = candidates_path or s.submission_candidates_path
        out = output_path or s.submission_output_path
        k = top_k if top_k is not None else s.submission_top_k

        cand_path = Path(cand)
        if not cand_path.is_file() and Path(str(cand) + ".gz").is_file():
            cand_path = Path(str(cand) + ".gz")

        if not cand_path.is_file():
            raise FileNotFoundError(
                f"Candidate pool not found: {cand_path}. "
                "Download candidates.jsonl from Redrob and place under polyhire-redrob/data/."
            )

        log.info(
            "Submission mode: candidates=%s out=%s top_k=%d backend=%s",
            cand_path,
            out,
            k,
            s.submission_ranker_backend,
        )
        return self.submission_ranker.run_submission_csv(cand_path, out, top_n=k)

    def _empty_result(
        self,
        jd_id: str,
        structured_jd: StructuredJD,
        bias_flags: list[BiasFlag],
        start: float,
    ) -> PipelineResult:
        return PipelineResult(
            jdId=jd_id,
            structured_jd=structured_jd,
            bias_flags=bias_flags,
            metrics=PipelineMetrics(
                retrieval_count=0,
                rerank_count=0,
                latency_ms=int((time.perf_counter() - start) * 1000),
            ),
        )


# Module-level singleton — the FastAPI app shares one warm pipeline.
_pipeline_singleton: CandidateDiscoveryPipeline | None = None


def get_pipeline() -> CandidateDiscoveryPipeline:
    global _pipeline_singleton
    if _pipeline_singleton is None:
        _pipeline_singleton = CandidateDiscoveryPipeline()
    return _pipeline_singleton
