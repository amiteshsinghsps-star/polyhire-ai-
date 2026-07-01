"""BIL-3 code-switch parser tests."""
from app.stages.bharat.code_switch_parser import CodeSwitchResumeParser


def test_hinglish_normalization():
    parser = CodeSwitchResumeParser(use_indictrans2=False)
    result = parser.parse("5 years ka anubhav in machiene learning and developement")
    assert "machine learning" in result.normalized_text
    assert "development" in result.normalized_text
    assert result.has_hinglish is True


def test_devanagari_static_map():
    parser = CodeSwitchResumeParser(use_indictrans2=False)
    result = parser.parse("Expert in डेटा विश्लेषण and मशीन लर्निंग")
    assert "data" in result.normalized_text.lower()
    assert "analysis" in result.normalized_text.lower()
    assert result.has_devanagari is True


def test_no_code_switch_clean_english():
    parser = CodeSwitchResumeParser(use_indictrans2=False)
    result = parser.parse("5 years of experience in Python and machine learning")
    assert result.code_switch_detected is False


def test_skill_augmentation():
    parser = CodeSwitchResumeParser(use_indictrans2=False)
    skill_pool = {"machine learning", "python", "data analysis"}
    result = parser.parse(
        text="Worked on मशीन लर्निंग projects",
        existing_skills=["python"],
        skill_pool=skill_pool,
    )
    assert "machine learning" in result.augmented_skills
