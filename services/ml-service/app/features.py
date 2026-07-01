"""
Feature-engineering helpers used by the fusion ranker.

Pure functions — no I/O, no model loads — so they're trivially unit-testable.
These compute the "career metadata" + "behavioral signal" features the problem
statement explicitly asks us to fuse alongside embedding + rerank scores.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def skill_overlap_ratio(jd_skills: list[str], candidate_skills: list[str]) -> float:
    """Recall-style overlap: fraction of JD must-have skills present in candidate's skill set.

    Uses recall (not Jaccard) because extra candidate skills should never penalize.
    """
    if not jd_skills:
        return 1.0
    jd_set = {s.strip().lower() for s in jd_skills if s.strip()}
    cand_set = {s.strip().lower() for s in candidate_skills if s.strip()}
    if not cand_set:
        return 0.0
    matched = jd_set & cand_set
    return len(matched) / len(jd_set)


def years_experience_match(jd_min_years: float, candidate_years: float) -> float:
    """
    1.0 when candidate meets/exceeds the bar, scaled down below it.
    Saturating curve so 10y vs a 5y requirement == 1.0, not 2.0.
    """
    if jd_min_years <= 0:
        return 1.0
    ratio = candidate_years / jd_min_years
    return float(np.clip(ratio, 0.0, 1.0))


def recency_of_activity(last_activity_days_ago: int) -> float:
    """
    Behavioral signal: how recently the candidate was active on the platform.
    Decays exponentially with a 90-day half-life.
    """
    if last_activity_days_ago <= 0:
        return 1.0
    return float(np.exp(-last_activity_days_ago / 90.0))


def normalize_embedding_similarity(cos_sim: float) -> float:
    """Map raw cosine [-1, 1] to [0, 1]."""
    return float((cos_sim + 1.0) / 2.0)


def build_feature_vector(
    *,
    embedding_similarity: float,
    rerank_score: float,
    structured_jd: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, float]:
    """
    Assemble the full fusion-feature dict for one (JD, candidate) pair.

    The candidate dict is expected to carry a `metadata` sub-dict matching
    CandidateMetadata plus a `skills` list and a `trust_score`.
    """
    meta = candidate.get("metadata", {}) or {}
    years = float(meta.get("years_experience", 0.0))
    skills = candidate.get("skills", []) or []
    last_active = int(meta.get("last_activity_days_ago", 0))
    trajectory = float(meta.get("career_trajectory_slope", 0.0))
    # BIL-1 may normalize engagement/recency in-place on the candidate dict.
    engagement = float(
        candidate.get("engagement_score", meta.get("engagement_score", 0.5))
    )
    if "recency_of_activity" in candidate:
        recency = float(candidate["recency_of_activity"])
    else:
        recency = recency_of_activity(last_active)
    institution_tier = float(candidate.get("institution_tier_score", 0.5))
    informal_sector = float(candidate.get("informal_sector_score", 0.0))
    trust = float(candidate.get("trust_score", 1.0) or 1.0)

    # Reranker scores can be unbounded logits — squash to [0, 1] via sigmoid.
    rerank_norm = float(1.0 / (1.0 + np.exp(-rerank_score)))

    return {
        "embedding_similarity": normalize_embedding_similarity(float(embedding_similarity)),
        "rerank_score": rerank_norm,
        "years_experience_match": years_experience_match(
            float(structured_jd.get("min_years_experience", 0.0)), years
        ),
        "skill_overlap_ratio": skill_overlap_ratio(
            structured_jd.get("must_have_skills", []) or [], skills
        ),
        "recency_of_activity": recency,
        "career_trajectory_slope": float(np.tanh(trajectory)),  # bound to (-1, 1)
        "engagement_score": float(np.clip(engagement, 0.0, 1.0)),
        "trust_score": float(np.clip(trust, 0.0, 1.0)),
        "institution_tier_score": float(np.clip(institution_tier, 0.0, 1.0)),
        "informal_sector_score": float(np.clip(informal_sector, 0.0, 1.0)),
    }
