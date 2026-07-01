"""BharatContextualizer orchestrator integration tests."""
from app.stages.bharat_contextualizer import BharatContextualizer


def test_enrich_applies_all_modules():
    ctx = BharatContextualizer(enabled=True, use_indictrans2=False)
    candidates = [
        {
            "id": "c1",
            "city": "Nagpur",
            "engagement_score": 0.52,
            "recency_of_activity": 0.49,
            "institution": "NIT Nagpur",
            "degree": "B.Tech",
            "profile_text": "5 years ka anubhav in Python. Ran a small shop for 2 years.",
            "skills": ["python"],
        }
    ]
    enriched = ctx.enrich(candidates, skill_pool={"python", "machine learning"})
    assert enriched[0]["bharat_context_applied"] is True
    assert enriched[0]["institution_tier_score"] > 0.7
    assert ctx.last_summary is not None
    assert ctx.last_summary.total_candidates == 1


def test_enrich_disabled_passthrough():
    ctx = BharatContextualizer(enabled=False)
    candidates = [{"id": "c1", "engagement_score": 0.5, "recency_of_activity": 0.5}]
    enriched = ctx.enrich(candidates)
    assert enriched[0]["bharat_context_applied"] is False
    assert ctx.last_summary is None
