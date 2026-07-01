"""
Unit Tests — DiverseHire™ (bias detection + diversity scoring)
"""
from __future__ import annotations
import math
import pytest
from app.stages.diverse_hire import JdBiasAnalyzer, ShortlistDiversityScorer


class TestJdBiasAnalyzer:
    """Gaucher (2011) gendered language detection."""

    analyzer = JdBiasAnalyzer()

    # ── Masculine-coded JDs ───────────────────────────────────────────────────
    @pytest.mark.parametrize("biased_jd", [
        "We need a competitive rock-star ninja who can dominate the market.",
        "You will lead aggressive growth and drive ambitious targets.",
        "Looking for a fearless, dominant leader to crush the competition.",
    ])
    def test_masculine_coded_jd_flagged(self, biased_jd):
        result = self.analyzer.analyze(biased_jd)
        assert result["overall_bias_score"] > 0.3
        assert result["masculine_coded_count"] > 0

    # ── Feminine-coded JDs ────────────────────────────────────────────────────
    def test_feminine_coded_jd_flagged(self):
        jd = "We are a collaborative, nurturing team. Support and share. Be loyal and sensitive."
        result = self.analyzer.analyze(jd)
        assert result["feminine_coded_count"] > 0

    # ── Neutral JD ────────────────────────────────────────────────────────────
    def test_neutral_jd_has_low_score(self, jd_text):
        result = self.analyzer.analyze(jd_text)
        assert result["overall_bias_score"] < 0.5

    # ── Protected attributes ──────────────────────────────────────────────────
    @pytest.mark.parametrize("illegal_text", [
        "Candidates must be male",
        "Preferred age: 22-28",
        "Must be a fresh graduate from IIT only",
    ])
    def test_protected_attributes_flagged(self, illegal_text):
        result = self.analyzer.analyze(illegal_text)
        assert result["has_prohibited_attributes"] is True

    # ── Output shape ──────────────────────────────────────────────────────────
    def test_output_has_required_keys(self, jd_text):
        result = self.analyzer.analyze(jd_text)
        required_keys = [
            "overall_bias_score",
            "masculine_coded_count",
            "feminine_coded_count",
            "masculine_coded_words",
            "feminine_coded_words",
            "has_prohibited_attributes",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_bias_score_in_valid_range(self, jd_text):
        result = self.analyzer.analyze(jd_text)
        assert 0.0 <= result["overall_bias_score"] <= 1.0

    # ── JD cleaner ────────────────────────────────────────────────────────────
    def test_cleaner_removes_gendered_words(self):
        if not hasattr(self.analyzer, "suggest_cleaned_jd"):
            pytest.skip("suggest_cleaned_jd not implemented yet")
        biased = "We need a dominant ninja to lead aggressive campaigns."
        cleaned = self.analyzer.suggest_cleaned_jd(biased)
        assert "dominant" not in cleaned.lower() or "ninja" not in cleaned.lower()


class TestShortlistDiversityScorer:
    """Shannon entropy diversity scoring for institution distribution."""

    scorer = ShortlistDiversityScorer()

    def test_diverse_shortlist_has_high_entropy(self):
        """7 candidates from 7 different institutions = max diversity."""
        candidates = [
            {"id": f"c{i}", "bharat_tier": "tier_2",
             "institution": f"Institution_{i}", "city": f"City_{i}"}
            for i in range(7)
        ]
        result = self.scorer.score(candidates)
        assert result["shannon_entropy"] > 1.5

    def test_monoculture_shortlist_has_low_entropy(self):
        """7 candidates all from IIT Bombay = no diversity."""
        candidates = [
            {"id": f"c{i}", "bharat_tier": "tier_1", "institution": "IIT Bombay", "city": "Mumbai"}
            for i in range(7)
        ]
        result = self.scorer.score(candidates)
        assert result["shannon_entropy"] < 0.5

    def test_entropy_is_non_negative(self, clean_candidates):
        result = self.scorer.score(clean_candidates)
        assert result["shannon_entropy"] >= 0.0

    def test_empty_list_returns_zero_entropy(self):
        result = self.scorer.score([])
        assert result["shannon_entropy"] == 0.0

    def test_output_has_tier_breakdown(self, clean_candidates):
        result = self.scorer.score(clean_candidates)
        assert "tier_breakdown" in result

    def test_single_candidate_entropy_is_zero(self):
        result = self.scorer.score([{"id": "c1", "institution": "IIT Delhi", "bharat_tier": "tier_1", "city": "Delhi"}])
        assert result["shannon_entropy"] == pytest.approx(0.0, abs=0.01)
