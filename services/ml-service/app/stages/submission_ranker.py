"""
Submission Ranker Stage — delegates to polyhire-redrob/ PRD v2.0 by default.

Set SUBMISSION_RANKER_BACKEND=legacy to use the monolithic services/ml-service/rank.py.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from .v2_ranker_bridge import get_v2_engine, polyhire_redrob_root, run_rank_py

log = logging.getLogger(__name__)

_BACKEND = os.getenv("SUBMISSION_RANKER_BACKEND", "v2").lower()


def _legacy_rank_module():
    ml_root = Path(__file__).resolve().parents[2]
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    import rank as legacy_rank  # noqa: WPS433

    return legacy_rank


class SubmissionRanker:
    """
    CPU-only ranking for hackathon submission mode.
    v2 (default): polyhire-redrob fusion ranker + honeypot hard-exclude.
    legacy: original 9-component heuristic in services/ml-service/rank.py.
    """

    def __init__(self) -> None:
        self.backend = _BACKEND
        self.is_fallback = False
        self._company_first_seen: dict[str, int] | None = None
        log.info(
            "Initialized SubmissionRanker backend=%s polyhire-redrob=%s",
            self.backend,
            polyhire_redrob_root(),
        )

    def _score_v2(self, candidate: dict[str, Any], detector, ranker, gen_reasoning) -> dict[str, Any]:
        hp = detector.check(candidate)
        if hp.is_honeypot:
            return {
                "candidate_id": candidate.get("candidate_id", "unknown"),
                "score": 0.0,
                "reasoning": "Excluded: internal profile consistency check failed.",
                "is_honeypot": True,
                "triggered_rules": hp.triggered_rules,
            }
        breakdown = ranker.score(candidate)
        reasoning = gen_reasoning(candidate, breakdown)
        return {
            "candidate_id": breakdown["candidate_id"],
            "score": breakdown["final_score"],
            "reasoning": reasoning,
            "is_honeypot": False,
            "skill_match": breakdown.get("skill_match"),
            "role_relevance": breakdown.get("role_relevance"),
        }

    def score_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            if self.backend == "legacy":
                legacy = _legacy_rank_module()
                result = legacy.score_candidate(candidate)
                result["reasoning"] = legacy.generate_reasoning(result)
                return result

            ranker, detector, gen_reasoning = get_v2_engine()
            return self._score_v2(candidate, detector, ranker, gen_reasoning)
        except Exception as exc:
            log.warning(
                "SubmissionRanker failed for candidate %s: %s",
                candidate.get("candidate_id"),
                exc,
            )
            return {
                "candidate_id": candidate.get("candidate_id", "unknown"),
                "score": 0.0,
                "reasoning": "Error during scoring",
                "is_honeypot": False,
            }

    def score_batch(
        self,
        candidates: list[dict[str, Any]],
        *,
        exclude_honeypots: bool = True,
    ) -> list[dict[str, Any]]:
        if self.backend == "legacy":
            results = [self.score_candidate(c) for c in candidates]
            if exclude_honeypots:
                results = [r for r in results if not r.get("is_honeypot")]
            results.sort(key=lambda x: (-x.get("score", 0.0), str(x.get("candidate_id", ""))))
            return results

        from polyhire.security.honeypot_detector import build_company_first_seen

        company_first_seen = build_company_first_seen(candidates)
        pool_max = max(
            (float(c.get("redrob_signals", {}).get("profile_views_received_30d", 0) or 0) for c in candidates),
            default=1.0,
        )
        ranker, detector, gen_reasoning = get_v2_engine(pool_max_exposure=pool_max)
        detector.company_first_seen = company_first_seen

        results = []
        for cand in candidates:
            scored = self._score_v2(cand, detector, ranker, gen_reasoning)
            if exclude_honeypots and scored.get("is_honeypot"):
                continue
            results.append(scored)
        results.sort(key=lambda x: (-x.get("score", 0.0), str(x.get("candidate_id", ""))))
        return results

    def run_submission_csv(
        self,
        candidates_path: str | Path,
        output_path: str | Path,
        *,
        top_n: int = 100,
    ) -> Path:
        """Full Phase B run via polyhire-redrob/rank.py (preferred for 100K pool)."""
        if self.backend == "legacy":
            legacy = _legacy_rank_module()
            import subprocess

            ml_root = Path(__file__).resolve().parents[2]
            rank_script = ml_root / "rank.py"
            out = Path(output_path).resolve()
            subprocess.run(
                [
                    sys.executable,
                    str(rank_script),
                    "--candidates",
                    str(Path(candidates_path).resolve()),
                    "--out",
                    str(out),
                ],
                check=True,
                cwd=str(ml_root),
            )
            return out

        return run_rank_py(candidates_path, output_path, top_n=top_n)
