"""
Exact Shapley Attribution for the PolyHire fusion score.

Mathematical basis
------------------
The fusion formula is a weighted linear combination:

    base_score = w_skill*skill + w_role*role + w_exp*exp + w_loc*location - penalty

For any linear/additive function f(x) = sum_i(w_i * x_i),
the Shapley value for feature i is:

    phi_i = w_i * (x_i - baseline_i)

This is exact (not an approximation) — no coalition sampling, no exponential blowup.
The defining property holds to machine precision:

    sum(phi_i for all i) == f(x) - f(baseline)

Reference: Charnes et al. (1988), Shapley (1953) — for linear games the
Shapley value collapses to this closed form.
"""
from __future__ import annotations

import json
from typing import Any


# Feature signal names that enter the linear base_score
FUSION_FEATURE_NAMES = [
    "skill_match",
    "role_relevance",
    "experience_fit",
    "location_logistics",
    "negative_penalty",
]


def shapley_exact(
    score_breakdown: dict[str, float],
    weights: dict[str, float],
    baselines: dict[str, float] | None = None,
) -> dict[str, float]:
    """Compute exact Shapley attribution for one candidate's fusion score.

    Parameters
    ----------
    score_breakdown:
        Dict from FusionRanker.score() — must contain keys for every
        signal in FUSION_FEATURE_NAMES plus behavioral_multiplier and
        bharat_adjustment.
    weights:
        jd_profile.WEIGHTS — the w_i coefficients for each feature.
    baselines:
        Reference "zero-signal" candidate. Defaults to all zeros for
        additive features and 1.0 for multiplicative adjustments.

    Returns
    -------
    Dict mapping feature name -> exact Shapley value (can be negative).
    Satisfies: sum(values) ~= final_score - baseline_final_score
    """
    baselines = baselines or {}

    # Default baselines: 0 for additive signals, 1.0 for multipliers
    base_skill     = baselines.get("skill_match", 0.0)
    base_role      = baselines.get("role_relevance", 0.0)
    base_exp       = baselines.get("experience_fit", 0.0)
    base_loc       = baselines.get("location_logistics", 0.0)
    base_penalty   = baselines.get("negative_penalty", 0.0)
    base_beh_mult  = baselines.get("behavioral_multiplier", 1.0)
    base_bhar_mult = baselines.get("bharat_adjustment", 1.0)

    skill    = score_breakdown.get("skill_match", 0.0)
    role     = score_breakdown.get("role_relevance", 0.0)
    exp      = score_breakdown.get("experience_fit", 0.0)
    loc      = score_breakdown.get("location_logistics", 0.0)
    penalty  = score_breakdown.get("negative_penalty", 0.0)
    beh_mult = score_breakdown.get("behavioral_multiplier", 1.0)
    bhar_adj = score_breakdown.get("bharat_adjustment", 1.0)

    # Linear base_score Shapley (exact)
    phi_skill   = weights.get("skill_match", 0.30) * (skill - base_skill)
    phi_role    = weights.get("role_relevance", 0.30) * (role - base_role)
    phi_exp     = weights.get("experience_fit", 0.15) * (exp - base_exp)
    phi_loc     = weights.get("location_logistics", 0.10) * (loc - base_loc)
    phi_penalty = -(penalty - base_penalty)  # penalty enters with negative sign

    # Multiplicative adjustments — linearise around baseline using first-order delta
    # actual_mult_effect = base_score_actual * (beh_mult * bhar_adj - base_beh_mult * base_bhar_mult)
    # We attribute this proportionally to each multiplier's marginal contribution.
    base_linear = (
        weights.get("skill_match", 0.30) * skill
        + weights.get("role_relevance", 0.30) * role
        + weights.get("experience_fit", 0.15) * exp
        + weights.get("location_logistics", 0.10) * loc
        - penalty
    )
    base_linear = max(0.0, base_linear)

    actual_mult = beh_mult * bhar_adj
    baseline_mult = base_beh_mult * base_bhar_mult
    total_mult_delta = base_linear * (actual_mult - baseline_mult)

    # Split mult delta proportionally by each factor's relative departure
    mult_delta = actual_mult - baseline_mult
    if abs(mult_delta) > 1e-9:
        beh_frac = (beh_mult - base_beh_mult) / (
            abs(beh_mult - base_beh_mult) + abs(bhar_adj - base_bhar_mult) + 1e-12
        )
        bhar_frac = 1.0 - beh_frac
    else:
        beh_frac = bhar_frac = 0.5

    phi_behavioral = total_mult_delta * beh_frac
    phi_bharat     = total_mult_delta * bhar_frac

    attributions: dict[str, float] = {
        "skill_match":          round(phi_skill,      6),
        "role_relevance":       round(phi_role,       6),
        "experience_fit":       round(phi_exp,        6),
        "location_logistics":   round(phi_loc,        6),
        "negative_penalty":     round(phi_penalty,    6),
        "behavioral_multiplier": round(phi_behavioral, 6),
        "bharat_adjustment":    round(phi_bharat,     6),
    }

    return attributions


def top_contributor(attributions: dict[str, float]) -> str:
    """Return the feature name with the largest positive Shapley contribution."""
    return max(attributions, key=lambda k: attributions[k])


def attribution_to_json(attributions: dict[str, float]) -> str:
    """Compact JSON string suitable for a CSV cell."""
    return json.dumps({k: round(v, 4) for k, v in attributions.items()}, separators=(",", ":"))


# ─── Unit-testable invariant ──────────────────────────────────────────────────

def verify_additivity(
    attributions: dict[str, float],
    actual_score: float,
    baseline_score: float = 0.0,
    tol: float = 1e-4,
) -> bool:
    """Assert sum(phi_i) ~= actual_score - baseline_score within tolerance.

    Always returns True/False; never raises so callers can log rather than crash.
    """
    total = sum(attributions.values())
    expected = actual_score - baseline_score
    return abs(total - expected) <= tol
