"""BIL-1: Tier-city exposure-signal re-centering."""
from __future__ import annotations

TIER_1_CITIES = {
    "bangalore", "bengaluru", "pune", "hyderabad", "mumbai", "delhi", "noida",
    "gurgaon", "gurugram", "chennai",
}
TIER_2_CITIES = {
    "jaipur", "indore", "coimbatore", "chandigarh", "kochi", "lucknow", "nagpur",
    "bhopal", "vadodara", "surat", "kanpur", "vizag", "visakhapatnam", "mysore",
}

TIER_BASELINE_EXPOSURE = {"tier_1": 1.0, "tier_2": 0.55, "tier_3": 0.30}


def classify_tier(location: str) -> str:
    if not location:
        return "tier_3"
    loc = location.lower()
    if any(c in loc for c in TIER_1_CITIES):
        return "tier_1"
    if any(c in loc for c in TIER_2_CITIES):
        return "tier_2"
    return "tier_3"


def normalize_exposure_signal(raw_value: float, tier: str, pool_max: float) -> float:
    if pool_max <= 0:
        return 0.0
    baseline = TIER_BASELINE_EXPOSURE.get(tier, 0.30)
    normalized = (raw_value / pool_max) / max(baseline, 0.05)
    return min(1.0, normalized)
