from polyhire.security.honeypot_detector import HoneypotDetector


def test_clean_candidate_not_flagged(sample_candidate):
    result = HoneypotDetector().check(sample_candidate)
    assert result.is_honeypot is False


def test_expert_low_duration_flagged(honeypot_candidate):
    result = HoneypotDetector().check(honeypot_candidate)
    assert result.is_honeypot is True
    assert "proficiency_duration_impossibility" in result.triggered_rules


def test_yoe_history_mismatch_flagged(sample_candidate):
    c = dict(sample_candidate)
    c["profile"] = dict(c["profile"], years_of_experience=15)
    result = HoneypotDetector().check(c)
    assert "yoe_history_mismatch" in result.triggered_rules
