"""
BIL-1: Tier-City Engagement Normalizer.

Adjusts engagement_score and recency_of_activity for candidates from Tier-2 and
Tier-3 cities so that the fusion ranker receives signals that reflect genuine
engagement *relative to their local context*, not relative to a national baseline
dominated by metro-area platform usage.

The normalization formula is a z-score renormalization:
    normalized = (raw - tier_mean) / tier_std * GLOBAL_STD + GLOBAL_MEAN

This places every candidate on the same national distribution while preserving
within-tier variance — so a genuinely disengaged Tier-2 candidate still scores
low relative to their own peers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ── Tier classification ────────────────────────────────────────────────────

TIER_1_CITIES = frozenset({
    "mumbai", "bangalore", "bengaluru", "delhi", "new delhi", "hyderabad",
    "chennai", "pune", "kolkata", "ahmedabad", "gurugram", "gurgaon",
    "noida", "thane", "navi mumbai", "greater noida",
})

TIER_2_CITIES = frozenset({
    "nagpur", "lucknow", "jaipur", "indore", "chandigarh", "coimbatore",
    "bhopal", "visakhapatnam", "vizag", "patna", "vadodara", "baroda",
    "surat", "agra", "nashik", "rajkot", "meerut", "faridabad",
    "amritsar", "allahabad", "prayagraj", "ranchi", "jabalpur", "gwalior",
    "vijayawada", "aurangabad", "solapur", "mysore", "mysuru", "jodhpur",
    "madurai", "raipur", "kochi", "cochin", "thiruvananthapuram",
    "trivandrum", "srinagar", "ludhiana", "agartala", "mangalore",
    "tiruchirappalli", "trichy", "hubli", "dharwad", "thrissur", "aligarh",
    "moradabad", "guwahati", "dehradun", "varanasi", "bhubaneswar",
})

# Everything else is Tier-3.

# ── Empirical baselines (derive from platform data in production) ──────────


@dataclass
class TierBaseline:
    engagement_mean: float
    engagement_std: float
    recency_mean: float
    recency_std: float


TIER_BASELINES: dict[str, TierBaseline] = {
    "tier_1": TierBaseline(
        engagement_mean=0.78, engagement_std=0.14,
        recency_mean=0.71, recency_std=0.18,
    ),
    "tier_2": TierBaseline(
        engagement_mean=0.52, engagement_std=0.16,
        recency_mean=0.49, recency_std=0.20,
    ),
    "tier_3": TierBaseline(
        engagement_mean=0.34, engagement_std=0.15,
        recency_mean=0.31, recency_std=0.17,
    ),
}

GLOBAL_ENGAGEMENT_MEAN = 0.60
GLOBAL_ENGAGEMENT_STD = 0.18
GLOBAL_RECENCY_MEAN = 0.55
GLOBAL_RECENCY_STD = 0.20


def classify_city_tier(city: Optional[str]) -> str:
    """Return 'tier_1', 'tier_2', or 'tier_3' for a given city string."""
    if not city:
        return "tier_2"  # conservative default — avoid punishing unknown cities
    normalized = city.lower().strip()
    if normalized in TIER_1_CITIES:
        return "tier_1"
    if normalized in TIER_2_CITIES:
        return "tier_2"
    return "tier_3"


def _z_renormalize(
    raw: float,
    src_mean: float,
    src_std: float,
    tgt_mean: float,
    tgt_std: float,
) -> float:
    """Z-score under src distribution, then project onto tgt distribution. Clipped to [0,1]."""
    if src_std < 1e-9:
        return raw
    z = (raw - src_mean) / src_std
    renormalized = z * tgt_std + tgt_mean
    return float(np.clip(renormalized, 0.0, 1.0))


@dataclass
class TierNormalizationResult:
    original_engagement_score: float
    original_recency_score: float
    normalized_engagement_score: float
    normalized_recency_score: float
    city_tier: str
    city_name: Optional[str]
    adjustment_applied: bool
    engagement_delta: float
    recency_delta: float


class TierCityEngagementNormalizer:
    """
    BIL-1: Normalize engagement_score and recency_of_activity per candidate
    based on their city tier, so the fusion ranker operates on context-adjusted
    signals rather than raw platform engagement counts.
    """

    def normalize(
        self,
        engagement_score: float,
        recency_score: float,
        city: Optional[str] = None,
        tier_override: Optional[str] = None,
    ) -> TierNormalizationResult:
        tier = tier_override or classify_city_tier(city)
        baseline = TIER_BASELINES[tier]

        norm_engagement = _z_renormalize(
            engagement_score,
            baseline.engagement_mean, baseline.engagement_std,
            GLOBAL_ENGAGEMENT_MEAN, GLOBAL_ENGAGEMENT_STD,
        )
        norm_recency = _z_renormalize(
            recency_score,
            baseline.recency_mean, baseline.recency_std,
            GLOBAL_RECENCY_MEAN, GLOBAL_RECENCY_STD,
        )

        return TierNormalizationResult(
            original_engagement_score=engagement_score,
            original_recency_score=recency_score,
            normalized_engagement_score=round(norm_engagement, 4),
            normalized_recency_score=round(norm_recency, 4),
            city_tier=tier,
            city_name=city,
            adjustment_applied=(tier != "tier_1"),
            engagement_delta=round(norm_engagement - engagement_score, 4),
            recency_delta=round(norm_recency - recency_score, 4),
        )

    def normalize_batch(self, candidates: list[dict]) -> list[dict]:
        """
        In-place normalization of engagement_score and recency_of_activity.
        Adds 'bharat_tier', 'tier_adjusted', 'engagement_delta' keys for
        downstream transparency logging.
        """
        for c in candidates:
            city = c.get("city") or c.get("location") or c.get("current_location")
            result = self.normalize(
                engagement_score=float(c.get("engagement_score", 0.5)),
                recency_score=float(c.get("recency_of_activity", 0.5)),
                city=city,
            )
            c["engagement_score"] = result.normalized_engagement_score
            c["recency_of_activity"] = result.normalized_recency_score
            c["bharat_tier"] = result.city_tier
            c["tier_adjusted"] = result.adjustment_applied
            c["engagement_delta"] = result.engagement_delta
        return candidates
