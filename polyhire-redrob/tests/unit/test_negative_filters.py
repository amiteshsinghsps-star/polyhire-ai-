from polyhire.features.negative_filters import negative_filter_penalty


def test_pure_consulting_career_penalized():
    c = {
        "career_history": [{
            "company": "TCS",
            "industry": "IT Services",
            "description": "",
            "start_date": "2018-01-01",
        }],
        "profile": {"years_of_experience": 5},
        "certifications": [],
        "redrob_signals": {"github_activity_score": -1},
    }
    penalty, rules = negative_filter_penalty(c)
    assert "pure_consulting_career" in rules
    assert penalty > 0
