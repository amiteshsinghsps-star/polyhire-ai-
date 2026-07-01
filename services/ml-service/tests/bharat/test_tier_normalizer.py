"""BIL-1 tier normalizer tests."""
from app.stages.bharat.tier_normalizer import (
    TierCityEngagementNormalizer,
    classify_city_tier,
)


def test_classify_tier1_cities():
    assert classify_city_tier("Bangalore") == "tier_1"
    assert classify_city_tier("Mumbai") == "tier_1"
    assert classify_city_tier("bengaluru") == "tier_1"


def test_classify_tier2_cities():
    assert classify_city_tier("Nagpur") == "tier_2"
    assert classify_city_tier("Lucknow") == "tier_2"


def test_classify_unknown_city_defaults():
    assert classify_city_tier("Chhapra") == "tier_3"
    assert classify_city_tier(None) == "tier_2"


def test_tier2_engagement_normalized_upward():
    norm = TierCityEngagementNormalizer()
    result = norm.normalize(engagement_score=0.52, recency_score=0.49, city="Nagpur")
    assert result.normalized_engagement_score > 0.52
    assert result.city_tier == "tier_2"
    assert result.adjustment_applied is True


def test_tier1_engagement_small_adjustment():
    norm = TierCityEngagementNormalizer()
    result = norm.normalize(engagement_score=0.78, recency_score=0.71, city="Bangalore")
    assert abs(result.engagement_delta) < 0.20
    assert result.adjustment_applied is False


def test_batch_normalization_inplace():
    norm = TierCityEngagementNormalizer()
    candidates = [
        {"id": "c1", "city": "Nagpur", "engagement_score": 0.52, "recency_of_activity": 0.49},
        {"id": "c2", "city": "Bangalore", "engagement_score": 0.78, "recency_of_activity": 0.71},
    ]
    result = norm.normalize_batch(candidates)
    assert result[0]["bharat_tier"] == "tier_2"
    assert result[1]["bharat_tier"] == "tier_1"
    assert result[0]["tier_adjusted"] is True
    assert result[1]["tier_adjusted"] is False
