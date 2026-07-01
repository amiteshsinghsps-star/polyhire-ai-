"""
SkillDecay™ Graph — Stage 10b (post-ranking enrichment)
========================================================
Treats skills as time-series signals, not static keywords.
Replaces the static `skill_overlap_ratio` in the fusion ranker with
a temporally-decayed `temporal_skill_overlap_ratio`.

Model: S(t) = BaseWeight × exp(-λ × age_years) × RecentEvidenceBonus

λ constants are technology-specific (framework skills decay fast,
core languages decay slowly). Calibrated to NASSCOM & Gartner 2025 data.

Fully deterministic — no model weights. Works on first clone.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# ── Per-skill decay constants (λ in years⁻¹) ─────────────────────────────────
# half-life = ln(2) / λ

SKILL_DECAY_CONSTANTS: dict[str, float] = {
    # ── Fast decay — frameworks (≈2yr half-life) ──
    "react": 0.35, "angular": 0.40, "vue": 0.38, "nextjs": 0.35,
    "tailwind": 0.30, "svelte": 0.38, "gatsby": 0.45,
    "flutter": 0.32, "react native": 0.33,

    # ── Moderate — cloud & infra (≈2.5yr half-life) ──
    "aws": 0.28, "gcp": 0.28, "azure": 0.28,
    "kubernetes": 0.25, "docker": 0.22, "terraform": 0.25,
    "helm": 0.28, "argocd": 0.28, "ansible": 0.26,

    # ── Moderate — ML frameworks (≈2yr half-life) ──
    "pytorch": 0.35, "tensorflow": 0.35, "keras": 0.38,
    "langchain": 0.45, "huggingface": 0.30, "transformers": 0.28,
    "scikit-learn": 0.22, "lightgbm": 0.22, "xgboost": 0.22,

    # ── Slow — core languages (≈5yr half-life) ──
    "python": 0.14, "javascript": 0.14, "typescript": 0.16,
    "java": 0.10, "go": 0.14, "rust": 0.14, "sql": 0.08,
    "c++": 0.10, "c#": 0.12, "scala": 0.14, "kotlin": 0.14,

    # ── Very slow — databases (≈4yr half-life) ──
    "postgresql": 0.17, "mysql": 0.17, "mongodb": 0.18,
    "redis": 0.18, "elasticsearch": 0.20, "cassandra": 0.18,

    # ── Fastest decay — specific versions/legacy (≈1yr half-life) ──
    "hadoop": 0.70, "hive": 0.65, "jquery": 0.70,
    "ruby on rails": 0.45, "struts": 0.80, "ejb": 0.80,

    # ── Near-permanent — concepts & soft skills ──
    "system design": 0.05, "leadership": 0.05,
    "communication": 0.04, "microservices": 0.10,
    "data structures": 0.06, "algorithms": 0.06,
}

DEFAULT_LAMBDA = 0.20          # unknown skills: ≈3.5yr half-life
EVIDENCE_MULTIPLIER = 1.4      # recent demonstrated skill bonus


# ── Per-skill relevance score ─────────────────────────────────────────────────

@dataclass
class SkillRelevanceScore:
    skill_name:          str
    raw_listing_age_yrs: float
    decay_constant:      float
    base_relevance:      float
    evidence_bonus:      float
    final_relevance:     float
    half_life_years:     float
    is_decayed:          bool
    evidence_sources:    list[str]


def compute_skill_relevance(
    skill_name: str,
    listed_date: Optional[datetime],
    recent_evidence: Optional[list[dict]] = None,
    reference_time: Optional[datetime] = None,
) -> SkillRelevanceScore:
    """
    Compute time-decayed relevance for a single skill.

    recent_evidence items: {"source": str, "date": ISO-8601 string}
    """
    now = reference_time or datetime.now(timezone.utc)
    recent_evidence = recent_evidence or []

    # Decay constant lookup (case-insensitive fuzzy)
    skill_key = skill_name.lower().strip()
    lambda_val = DEFAULT_LAMBDA
    for key, val in SKILL_DECAY_CONSTANTS.items():
        if key in skill_key or skill_key in key:
            lambda_val = val
            break

    # Age of listing
    age_years = (now - listed_date).days / 365.25 if listed_date else 2.0
    age_years = max(0.0, age_years)

    base = math.exp(-lambda_val * age_years)

    # Recent evidence bonus (any evidence in last 12 months)
    cutoff = now - timedelta(days=365)
    sources: list[str] = []
    bonus = 1.0
    for ev in recent_evidence:
        try:
            ev_dt = datetime.fromisoformat(ev["date"]).replace(tzinfo=timezone.utc)
            if ev_dt >= cutoff:
                sources.append(ev.get("source", "recent project"))
                bonus = max(bonus, EVIDENCE_MULTIPLIER)
        except Exception:
            pass

    final = min(1.0, base * bonus)
    half_life = math.log(2) / lambda_val

    return SkillRelevanceScore(
        skill_name=skill_name,
        raw_listing_age_yrs=round(age_years, 2),
        decay_constant=lambda_val,
        base_relevance=round(base, 4),
        evidence_bonus=round(bonus, 4),
        final_relevance=round(final, 4),
        half_life_years=round(half_life, 1),
        is_decayed=final < 0.50,
        evidence_sources=sources,
    )


# ── Batch Analyzer ────────────────────────────────────────────────────────────

class SkillDecayAnalyzer:
    """
    SkillDecay™ — enriches candidates with temporal skill overlap.

    Candidate dict expected fields (all optional — safe defaults used):
      skills:          list[str]
      skill_dates:     dict[str, ISO-8601]   # when skill was listed/verified
      skill_evidence:  dict[str, list[dict]] # [{source, date}] recent evidence

    JD dict expected fields:
      must_have_skills:     list[str]
      nice_to_have_skills:  list[str]
    """

    def analyze(
        self,
        candidate: dict,
        structured_jd: dict,
        reference_time: Optional[datetime] = None,
    ) -> dict:
        now = reference_time or datetime.now(timezone.utc)

        skills         = candidate.get("skills") or []
        skill_dates    = candidate.get("skill_dates") or {}
        skill_evidence = candidate.get("skill_evidence") or {}

        must_have = {s.lower() for s in (structured_jd.get("must_have_skills") or [])}
        nice_have = {s.lower() for s in (structured_jd.get("nice_to_have_skills") or [])}
        all_jd    = must_have | nice_have
        total_jd  = len(all_jd) or 1

        # Per-skill scores
        scores: dict[str, SkillRelevanceScore] = {}
        for skill in skills:
            date_str = skill_dates.get(skill) or skill_dates.get(skill.lower())
            listed: Optional[datetime] = None
            if date_str:
                try:
                    listed = datetime.fromisoformat(str(date_str)).replace(tzinfo=timezone.utc)
                except Exception:
                    pass
            evidence = skill_evidence.get(skill, [])
            scores[skill] = compute_skill_relevance(skill, listed, evidence, now)

        # Decay-adjusted overlap
        temporal_sum = sum(
            scores[s].final_relevance
            for s in skills if s.lower() in all_jd
        )
        static_sum = sum(1 for s in skills if s.lower() in all_jd)

        temporal_overlap = temporal_sum / total_jd
        static_overlap   = static_sum   / total_jd

        decayed = [s for s, sc in scores.items() if sc.is_decayed]
        strong  = [s for s, sc in scores.items() if sc.final_relevance >= 0.80]

        # Recruiter warning for decayed must-have skills
        warning: Optional[str] = None
        for skill in skills:
            if skill.lower() in must_have and scores[skill].final_relevance < 0.40:
                sc = scores[skill]
                warning = (
                    f"'{skill}' is a must-have but last demonstrated "
                    f"{sc.raw_listing_age_yrs:.1f}yr ago "
                    f"(half-life: {sc.half_life_years}yr). Verify in interview."
                )
                break

        return {
            "candidate_id": candidate.get("id", "unknown"),
            "live_skills":  {s: sc.final_relevance for s, sc in scores.items()},
            "decayed_skills": decayed,
            "strong_skills":  strong,
            "temporal_skill_overlap": round(min(1.0, temporal_overlap), 4),
            "static_skill_overlap":   round(min(1.0, static_overlap),   4),
            "overlap_inflation":      round(max(0.0, static_overlap - temporal_overlap), 4),
            "recruiter_warning": warning,
            "skill_decay_details": {
                s: {
                    "relevance":    sc.final_relevance,
                    "age_years":    sc.raw_listing_age_yrs,
                    "half_life":    sc.half_life_years,
                    "is_decayed":   sc.is_decayed,
                    "had_evidence": len(sc.evidence_sources) > 0,
                }
                for s, sc in scores.items()
            },
        }

    def enrich_candidates(self, candidates: list[dict], structured_jd: dict) -> list[dict]:
        """Replace static skill_overlap_ratio with temporal version in-place."""
        for c in candidates:
            try:
                profile = self.analyze(c, structured_jd)
                c["skill_overlap_ratio"]        = profile["temporal_skill_overlap"]
                c["skill_overlap_ratio_static"] = profile["static_skill_overlap"]
                c["decayed_skills"]             = profile["decayed_skills"]
                c["strong_skills"]              = profile["strong_skills"]
                c["skill_decay_warning"]        = profile["recruiter_warning"]
                c["skill_decay_details"]        = profile["skill_decay_details"]
            except Exception as exc:  # noqa: BLE001
                log.warning("SkillDecay enrichment failed for %s: %s", c.get("id", "?"), exc)
        return candidates
