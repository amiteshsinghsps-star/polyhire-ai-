"""
Bias & Fairness Tests
=====================
Validates that the ranking system does not systematically disadvantage
candidates based on protected characteristics (gender, caste, city tier,
institution tier).

Tests use paired candidates — identical on merit, different on identity.
"""
from __future__ import annotations
import pytest
from tests.conftest import make_candidate
from app.stages.diverse_hire import JdBiasAnalyzer
from app.stages.resume_shield import ResumeShieldEngine


class TestGenderBias:
    """Paired male/female candidates with identical skills should rank equally."""

    def _make_paired(self, name_a: str, name_b: str) -> tuple[dict, dict]:
        base = dict(
            skills=["python", "fastapi", "postgresql", "docker"],
            years_experience=5,
            trust_score=0.9,
            fraud_risk_score=0.05,
        )
        a = make_candidate("ga", name=name_a, **base)
        b = make_candidate("gb", name=name_b, **base)
        return a, b

    def test_male_female_names_same_fraud_score(self):
        """ResumeShield must not penalize based on candidate name."""
        engine = ResumeShieldEngine()
        male, female = self._make_paired("Amit Kumar", "Priya Sharma")
        r_male   = engine.analyze(male)
        r_female = engine.analyze(female)
        # Fraud scores must be within 0.05 of each other
        assert abs(r_male["fraud_risk_score"] - r_female["fraud_risk_score"]) < 0.05

    def test_jd_bias_analyzer_flags_gendered_jd(self):
        analyzer = JdBiasAnalyzer()
        biased = "We are looking for a dominant male engineer who is a rockstar."
        result = analyzer.analyze(biased)
        assert result["masculine_coded_count"] > 0 or result["has_prohibited_attributes"] is True


class TestCityBias:
    """Tier-3 city candidates with identical skills must not be systematically penalized."""

    def test_metro_vs_tier3_same_skill_level(self):
        engine = ResumeShieldEngine()
        metro = make_candidate(
            "metro_01",
            city="Mumbai",
            skills=["python", "docker", "fastapi"],
            years_experience=4,
        )
        tier3 = make_candidate(
            "tier3_01",
            city="Bhilai",
            skills=["python", "docker", "fastapi"],
            years_experience=4,
            bharat_tier="tier_3",
        )
        r_metro = engine.analyze(metro)
        r_tier3 = engine.analyze(tier3)
        # City alone must not inflate fraud score
        assert abs(r_metro["fraud_risk_score"] - r_tier3["fraud_risk_score"]) < 0.10


class TestInstitutionBias:
    """Shannon entropy scorer must improve when tier-3 institutions are included."""

    def test_including_tier3_improves_diversity(self):
        from app.stages.diverse_hire import ShortlistDiversityScorer
        scorer = ShortlistDiversityScorer()

        iit_heavy = [
            {"id": f"c{i}", "institution": "IIT Bombay", "bharat_tier": "tier_1", "city": "Mumbai"}
            for i in range(7)
        ]
        mixed = [
            {"id": "c1", "institution": "IIT Bombay",        "bharat_tier": "tier_1", "city": "Mumbai"},
            {"id": "c2", "institution": "NIT Raipur",         "bharat_tier": "tier_2", "city": "Raipur"},
            {"id": "c3", "institution": "Amity University",   "bharat_tier": "tier_2", "city": "Noida"},
            {"id": "c4", "institution": "Govt College Patna", "bharat_tier": "tier_3", "city": "Patna"},
            {"id": "c5", "institution": "VIT Vellore",        "bharat_tier": "tier_2", "city": "Vellore"},
            {"id": "c6", "institution": "BHU",                "bharat_tier": "tier_2", "city": "Varanasi"},
            {"id": "c7", "institution": "BITS Pilani",        "bharat_tier": "tier_1", "city": "Pilani"},
        ]
        iit_score   = scorer.score(iit_heavy)["shannon_entropy"]
        mixed_score = scorer.score(mixed)["shannon_entropy"]
        assert mixed_score > iit_score


class TestProtectedAttributeFiltering:
    """JDs containing protected attributes must be flagged before submission."""

    analyzer = JdBiasAnalyzer()

    @pytest.mark.parametrize("violation, attr_category", [
        ("We require male candidates only",    "gender"),
        ("Preferred age: 22-28 years",          "age"),
        ("Must be Hindu",                       "religion"),
        ("Only upper-caste candidates apply",   "caste"),
    ])
    def test_protected_attributes_blocked(self, violation, attr_category):
        result = self.analyzer.analyze(violation)
        assert result["has_prohibited_attributes"] is True


class TestFairnessAcrossLanguageGroups:
    """JD bias analyzer must handle Hinglish / mixed-language JDs correctly."""

    analyzer = JdBiasAnalyzer()

    def test_hinglish_jd_analyzed_without_crash(self):
        jd = "Ham chahte hain ek strong developer jo Python aur FastAPI mein expert ho."
        result = self.analyzer.analyze(jd)
        assert "overall_bias_score" in result
        assert 0.0 <= result["overall_bias_score"] <= 1.0
