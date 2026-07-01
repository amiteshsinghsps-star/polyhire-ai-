"""
Robust Rank Aggregation — Bootstrap-Stable Top-N.

Method
------
Instead of committing to one exact weight vector, sample N weight vectors
from a ±noise_pct neighbourhood of jd_profile.WEIGHTS, re-score the
top-K candidate pool under each, and report a stability-weighted final rank.

A candidate who reaches the top-100 in 90% of weight samples is more
defensible than one who only makes it under the exact hand-tuned weights.

Runtime
-------
We operate only on the top-300 scored candidates (not the full 100K) so
the extra re-scoring is fast (< 1s for 50 samples × 300 candidates on CPU).
"""
from __future__ import annotations

import copy
import random
from typing import Any

import jd_profile as jd


def _perturb_weights(base_weights: dict[str, float], noise_pct: float, rng: random.Random) -> dict[str, float]:
    """Return a new weight dict where each weight is randomly scaled within ±noise_pct."""
    new_w = {}
    for k, v in base_weights.items():
        scale = 1.0 + rng.uniform(-noise_pct, noise_pct)
        new_w[k] = max(0.0, v * scale)
    return new_w


def _rescore_with_weights(
    candidate: dict[str, Any],
    new_weights: dict[str, float],
    score_breakdown: dict[str, float],
) -> float:
    """Fast re-evaluation: reuse pre-computed sub-scores with new weights (no embeddings re-run)."""
    skill    = score_breakdown["skill_match"]
    role     = score_breakdown["role_relevance"]
    exp      = score_breakdown["experience_fit"]
    loc      = score_breakdown["location_logistics"]
    penalty  = score_breakdown["negative_penalty"]
    beh_mult = score_breakdown["behavioral_multiplier"]
    bhar_adj = score_breakdown["bharat_adjustment"]

    base = (
        new_weights.get("skill_match", 0.30) * skill
        + new_weights.get("role_relevance", 0.30) * role
        + new_weights.get("experience_fit", 0.15) * exp
        + new_weights.get("location_logistics", 0.10) * loc
        - penalty
    )
    return max(0.0, min(1.0, base * beh_mult * bhar_adj))


def aggregate_robust_rank(
    top_scored: list[dict[str, Any]],
    base_weights: dict[str, float] | None = None,
    num_samples: int = 50,
    noise_pct: float = 0.15,
    stable_top_n: int = 100,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Re-rank `top_scored` by rank stability across weight perturbations.

    Parameters
    ----------
    top_scored:
        List of score_breakdown dicts (output of FusionRanker.score()) for
        the top-K candidates only (e.g. top 300). Must include sub-scores.
    base_weights:
        The nominal weights to perturb. Defaults to jd_profile.WEIGHTS.
    num_samples:
        Number of weight perturbation samples (50 gives stable estimates
        in < 1 second for 300 candidates).
    noise_pct:
        Fractional noise on each weight, e.g. 0.15 = ±15%.
    stable_top_n:
        Count candidates in this top bracket for the stability ratio.
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    List of dicts sorted by stability_score descending. Each dict has an
    added key ``rank_stability`` (fraction of samples in top-N).
    """
    base_weights = base_weights or dict(jd.WEIGHTS)
    rng = random.Random(seed)

    # Counters: how many times each candidate appeared in top stable_top_n
    cid_counts: dict[str, int] = {r["candidate_id"]: 0 for r in top_scored}

    for _ in range(num_samples):
        w = _perturb_weights(base_weights, noise_pct, rng)

        perturbed_scores: list[tuple[str, float]] = []
        for row in top_scored:
            s = _rescore_with_weights(row.get("_candidate", {}), w, row)
            perturbed_scores.append((row["candidate_id"], s))

        # Sort and take top-N
        perturbed_scores.sort(key=lambda x: -x[1])
        in_top = {cid for cid, _ in perturbed_scores[:stable_top_n]}
        for cid in in_top:
            if cid in cid_counts:
                cid_counts[cid] += 1

    # Attach stability ratio and re-sort
    enriched = []
    for row in top_scored:
        row = dict(row)
        stability = cid_counts[row["candidate_id"]] / num_samples
        row["rank_stability"] = round(stability, 4)
        # Stability-weighted final score: blend original score with stability
        row["_robust_score"] = 0.7 * row["final_score"] + 0.3 * stability
        enriched.append(row)

    enriched.sort(key=lambda r: (-r["_robust_score"], -r["role_relevance"], r["candidate_id"]))
    return enriched
