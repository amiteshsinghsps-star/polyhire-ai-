"""
Stage 6 — Explainability.

Turns the fusion ranker's numeric per-feature contributions into a
recruiter-facing one-line justification, surfaced in the dashboard and as
3D galaxy hover text. Uses a deterministic templated explanation
so the pipeline is fully runnable offline (zero API keys).
"""
from __future__ import annotations

import logging

from ..config import get_settings

log = logging.getLogger(__name__)

EXPLAIN_PROMPT = """Candidate ranked #{rank} for this role. Their top contributing
factors were: {top_factors}. In ONE sentence, written for a recruiter (not a data
scientist), explain why this candidate ranks here. Be specific, not generic.
"""

# Human-readable gloss of each feature for the templated fallback.
FEATURE_GLOSS: dict[str, str] = {
    "embedding_similarity": "overall semantic fit to the role",
    "rerank_score": "deep cross-encoder relevance",
    "years_experience_match": "experience depth vs. the role's requirement",
    "skill_overlap_ratio": "must-have skill coverage",
    "recency_of_activity": "recent platform engagement",
    "career_trajectory_slope": "upward career trajectory",
    "engagement_score": "profile completeness and activity",
    "trust_score": "resume authenticity / consistency",
}


def _templated_explanation(rank: int, top_factors: list[tuple[str, float]]) -> str:
    if not top_factors:
        return f"Ranked #{rank} on combined signal strength."
    primary = top_factors[0]
    gloss = FEATURE_GLOSS.get(primary[0], primary[0].replace("_", " "))
    parts = [f"Ranked #{rank}, driven mainly by {gloss}"]
    if len(top_factors) > 1:
        secondary = FEATURE_GLOSS.get(top_factors[1][0], top_factors[1][0].replace("_", " "))
        parts.append(f"reinforced by {secondary}")
    return ", ".join(parts) + "."


def explain_ranking(rank: int, top_factors: list[tuple[str, float]]) -> str:
    """
    Produce a one-sentence justification for a candidate's rank.

    Args:
        rank: 1-indexed rank of the candidate.
        top_factors: (feature_name, contribution) pairs, highest-magnitude first.
    """
    return _templated_explanation(rank, top_factors)
