"""BIL-4 informal sector translator tests."""
from app.stages.bharat.informal_sector_translator import InformalSectorTranslator


def test_small_business_detection():
    translator = InformalSectorTranslator()
    result = translator.translate(
        "Ran a small textile shop in Nagpur for 3 years, managing 4 staff"
    )
    assert result.informal_sector_score > 0.5
    assert "team management" in result.high_confidence_skills
    assert "vendor management" in result.high_confidence_skills


def test_freelance_detection():
    translator = InformalSectorTranslator()
    result = translator.translate("Freelance web developer, managed 15+ client projects")
    assert result.informal_sector_score > 0.4
    assert "client management" in result.high_confidence_skills


def test_no_informal_experience():
    translator = InformalSectorTranslator()
    result = translator.translate("5 years at Infosys as Senior Software Engineer")
    assert result.informal_sector_score == 0.0


def test_batch_translation():
    translator = InformalSectorTranslator()
    candidates = [
        {"id": "c1", "profile_text": "Ran a small shop for 2 years", "skills": []},
        {"id": "c2", "profile_text": "Software engineer at TCS", "skills": ["Java"]},
    ]
    result = translator.translate_batch(candidates)
    assert result[0]["informal_sector_score"] > 0.0
    assert result[1]["informal_sector_score"] == 0.0
