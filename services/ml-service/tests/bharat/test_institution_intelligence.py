"""BIL-2 institution intelligence tests."""
from app.stages.bharat.institution_intelligence import IndiaInstitutionIntelligence


def test_iit_scores_high():
    iiq = IndiaInstitutionIntelligence()
    result = iiq.score_candidate("IIT Bombay", "B.Tech")
    assert result.final_score >= 0.95
    assert result.in_nirf_database is True
    assert result.match_type == "exact"


def test_nit_scores_in_tier_b():
    iiq = IndiaInstitutionIntelligence()
    result = iiq.score_candidate("NIT Nagpur", "B.Tech")
    assert 0.75 <= result.final_score <= 0.90
    assert result.in_nirf_database is True


def test_bits_scores_high():
    iiq = IndiaInstitutionIntelligence()
    result = iiq.score_candidate("BITS Pilani", "B.E.")
    assert result.final_score >= 0.85


def test_unknown_institution_gets_reasonable_default():
    iiq = IndiaInstitutionIntelligence()
    result = iiq.score_candidate("Dummy College of Engineering")
    assert 0.35 <= result.final_score <= 0.55
    assert result.in_nirf_database is False


def test_nit_pattern_match_for_unlisted():
    iiq = IndiaInstitutionIntelligence()
    result = iiq.score_candidate("NIT Uttarakhand")
    assert result.final_score >= 0.70
