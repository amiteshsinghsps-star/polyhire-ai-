from polyhire.bharat.contextualizer import BharatContextualizer


def test_bharat_adjustment_is_bounded(tmp_path):
    bc = BharatContextualizer(str(tmp_path / "missing.json"), str(tmp_path / "missing2.json"))
    for edu_tier in ["tier_1", "tier_2", "tier_3", "tier_4", "unknown"]:
        c = {
            "education": [{"institution": "Unknown College", "tier": edu_tier}],
            "profile": {"summary": "Worked on a freelance project."},
        }
        adj = bc.adjustment(c)
        assert 0.85 <= adj <= 1.15
