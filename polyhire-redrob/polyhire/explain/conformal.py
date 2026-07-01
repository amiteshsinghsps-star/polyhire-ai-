"""
Split Conformal Prediction Intervals for PolyHire ranking confidence.

Method
------
Standard split conformal prediction (Vovk et al., 2005; Angelopoulos & Bates 2021).

1.  Score a calibration subset using the ranking pipeline.
2.  Compute nonconformity residuals: |silver_relevance_normalised - calibrated_score|
3.  Take the ceil( (n+1)(1-alpha) ) / n quantile of residuals as the margin.
4.  Every future candidate gets: [score - margin, score + margin]

Coverage guarantee (finite-sample, distribution-free):
    P(true_relevance in CI) >= 1 - alpha

No distributional assumptions.  Works even with few calibration points,
though tighter intervals require more calibration data.
"""
from __future__ import annotations

import math
from typing import Sequence


def calibrate_conformal(
    cal_scores: Sequence[float],
    cal_labels: Sequence[float],
    alpha: float = 0.10,
) -> float:
    """Compute the conformal margin from a calibration split.

    Parameters
    ----------
    cal_scores:
        Pipeline scores on calibration candidates (values in [0, 1]).
    cal_labels:
        Ground-truth relevance labels for the same candidates, normalised to [0, 1].
        Use silver_relevance(c) / 3.0 for the existing silver-label source.
    alpha:
        Miscoverage rate. 0.10 gives a 90% coverage guarantee.

    Returns
    -------
    margin: float — add/subtract from any future score to form a CI.
    """
    n = len(cal_scores)
    if n == 0:
        return 1.0  # degenerate: no calibration data → widest interval

    residuals = sorted(abs(float(l) - float(s)) for s, l in zip(cal_scores, cal_labels))

    # The (1-alpha)-quantile with the finite-sample correction ceil((n+1)(1-alpha))/n
    idx = math.ceil((n + 1) * (1.0 - alpha)) - 1  # zero-indexed
    idx = min(idx, n - 1)  # clamp to available data
    margin = residuals[idx]
    return float(margin)


def predict_interval(score: float, margin: float) -> tuple[float, float]:
    """Return the symmetric conformal prediction interval.

    Parameters
    ----------
    score:
        The point-estimate fusion score.
    margin:
        Output of calibrate_conformal().

    Returns
    -------
    (lower, upper) clipped to [0, 1].
    """
    lower = max(0.0, score - margin)
    upper = min(1.0, score + margin)
    return round(lower, 4), round(upper, 4)


def empirical_coverage(
    test_scores: Sequence[float],
    test_labels: Sequence[float],
    margin: float,
) -> float:
    """Sanity-check: fraction of test candidates whose label falls in their CI.

    Should be >= (1 - alpha) on a fresh hold-out.
    """
    if not test_scores:
        return 0.0
    covered = sum(
        1
        for s, l in zip(test_scores, test_labels)
        if predict_interval(s, margin)[0] <= l <= predict_interval(s, margin)[1]
    )
    return round(covered / len(test_scores), 4)


def conformal_summary(margin: float, alpha: float, n_cal: int) -> str:
    """Human-readable summary for logs/reports."""
    return (
        f"Conformal margin={margin:.4f} | "
        f"coverage_guarantee={1-alpha:.0%} | "
        f"cal_n={n_cal} | "
        f"interval_width={2*margin:.4f}"
    )
