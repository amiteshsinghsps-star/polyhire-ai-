"""
Unit tests for polyhire.explain.attribution (exact Shapley values).

Key invariant: sum(phi_i) == score - baseline_score (to machine precision).
"""
from __future__ import annotations

import pytest
from polyhire.explain.attribution import (
    shapley_exact,
    top_contributor,
    verify_additivity,
)

_WEIGHTS = dict(
    skill_match=0.30,
    role_relevance=0.30,
    experience_fit=0.15,
    location_logistics=0.10,
    negative_filter_cap=0.25,  # not used in linear part directly
)


def _make_breakdown(skill=0.8, role=0.7, exp=0.6, loc=1.0, penalty=0.0, beh=1.0, bhar=1.0):
    return {
        "skill_match":           skill,
        "role_relevance":        role,
        "experience_fit":        exp,
        "location_logistics":    loc,
        "negative_penalty":      penalty,
        "behavioral_multiplier": beh,
        "bharat_adjustment":     bhar,
        # final_score is NOT used by shapley_exact — it recomputes from parts
        "final_score": (
            max(0.0, 0.30*skill + 0.30*role + 0.15*exp + 0.10*loc - penalty) * beh * bhar
        ),
    }


class TestShapleyAdditivity:
    """The defining invariant must hold for all synthetic candidates."""

    def test_perfect_candidate(self):
        bd = _make_breakdown(skill=1.0, role=1.0, exp=1.0, loc=1.0, penalty=0.0)
        phi = shapley_exact(bd, _WEIGHTS)
        actual = bd["final_score"]
        assert verify_additivity(phi, actual, baseline_score=0.0), (
            f"Additivity failed: sum={sum(phi.values()):.6f} != final_score={actual:.6f}"
        )

    def test_weak_candidate(self):
        bd = _make_breakdown(skill=0.1, role=0.1, exp=0.2, loc=0.0, penalty=0.08)
        phi = shapley_exact(bd, _WEIGHTS)
        actual = bd["final_score"]
        assert verify_additivity(phi, actual, baseline_score=0.0)

    def test_with_penalty(self):
        bd = _make_breakdown(skill=0.6, role=0.5, exp=0.7, loc=0.5, penalty=0.15)
        phi = shapley_exact(bd, _WEIGHTS)
        actual = bd["final_score"]
        assert verify_additivity(phi, actual, baseline_score=0.0)

    def test_multiplier_effect(self):
        """With behavioral_multiplier < 1 the multiplier contribution should be negative."""
        bd = _make_breakdown(skill=0.8, role=0.7, exp=0.6, loc=1.0, penalty=0.0, beh=0.45)
        phi = shapley_exact(bd, _WEIGHTS)
        assert phi["behavioral_multiplier"] < 0, "Suppressive multiplier should give negative attribution"
        assert verify_additivity(phi, bd["final_score"])

    def test_top_contributor_positive(self):
        """Top contributor must always be the feature with the largest attribution."""
        bd = _make_breakdown(skill=0.9, role=0.2, exp=0.3, loc=0.4, penalty=0.0)
        phi = shapley_exact(bd, _WEIGHTS)
        assert top_contributor(phi) == "skill_match", (
            f"Expected skill_match, got {top_contributor(phi)}, phi={phi}"
        )

    def test_zero_score_candidate(self):
        """All-zero profile => all Shapley values should be 0."""
        bd = _make_breakdown(skill=0.0, role=0.0, exp=0.0, loc=0.0, penalty=0.0, beh=1.0, bhar=1.0)
        bd["final_score"] = 0.0
        phi = shapley_exact(bd, _WEIGHTS)
        assert all(abs(v) < 1e-9 for v in phi.values()), f"Expected all-zero phi, got {phi}"

    @pytest.mark.parametrize("skill,role,exp,loc,pen", [
        (0.3, 0.4, 0.5, 0.6, 0.05),
        (0.9, 0.9, 0.9, 0.9, 0.0),
        (0.1, 0.2, 0.3, 0.0, 0.20),
        (0.5, 0.5, 0.5, 0.5, 0.10),
    ])
    def test_parametric_additivity(self, skill, role, exp, loc, pen):
        bd = _make_breakdown(skill=skill, role=role, exp=exp, loc=loc, penalty=pen)
        phi = shapley_exact(bd, _WEIGHTS)
        assert verify_additivity(phi, bd["final_score"], tol=1e-4), (
            f"Additivity failed for s={skill} r={role} e={exp} l={loc} p={pen}"
        )
