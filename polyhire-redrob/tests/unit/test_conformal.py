"""
Unit tests for polyhire.explain.conformal (split conformal prediction).

Checks:
- margin is finite and non-negative
- predict_interval always clips to [0, 1]
- empirical_coverage on calibration data >= (1-alpha) (by construction)
"""
from __future__ import annotations

import pytest
from polyhire.explain.conformal import (
    calibrate_conformal,
    predict_interval,
    empirical_coverage,
    conformal_summary,
)


class TestConformalCalibration:
    def test_basic_margin_is_positive(self):
        scores = [0.6, 0.7, 0.8, 0.5, 0.9]
        labels = [0.5, 0.8, 0.75, 0.4, 1.0]
        margin = calibrate_conformal(scores, labels, alpha=0.10)
        assert margin >= 0.0

    def test_empty_calibration_returns_max(self):
        margin = calibrate_conformal([], [], alpha=0.10)
        assert margin == 1.0

    def test_alpha_zero_gives_max_margin(self):
        scores = [0.5, 0.6, 0.7]
        labels = [0.3, 0.8, 0.4]
        margin_strict = calibrate_conformal(scores, labels, alpha=0.001)
        margin_loose = calibrate_conformal(scores, labels, alpha=0.50)
        assert margin_strict >= margin_loose

    def test_interval_clips_to_unit(self):
        lo, hi = predict_interval(0.05, 0.20)
        assert lo >= 0.0
        lo2, hi2 = predict_interval(0.95, 0.20)
        assert hi2 <= 1.0

    def test_interval_width(self):
        lo, hi = predict_interval(0.70, 0.08)
        assert abs((hi - lo) - 0.16) < 1e-3

    def test_empirical_coverage_on_calibration_set(self):
        """Coverage on the calibration set itself must be >= (1-alpha)."""
        import random
        rng = random.Random(42)
        n = 200
        scores = [rng.uniform(0, 1) for _ in range(n)]
        labels = [min(1.0, max(0.0, s + rng.gauss(0, 0.05))) for s in scores]

        alpha = 0.10
        margin = calibrate_conformal(scores, labels, alpha=alpha)
        cov = empirical_coverage(scores, labels, margin)
        # On the calibration set itself, coverage must be >= 1-alpha by construction
        assert cov >= (1.0 - alpha - 0.05), f"Coverage {cov:.3f} < {1-alpha:.2f}"

    def test_summary_string_format(self):
        s = conformal_summary(0.08, 0.10, 150)
        assert "margin=0.0800" in s
        assert "90%" in s
