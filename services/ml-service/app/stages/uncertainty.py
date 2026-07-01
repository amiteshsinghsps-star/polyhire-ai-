"""
Enterprise Feature §23.1 — Calibrated Confidence & Uncertainty Quantification.

Wraps the fusion ranker with conformal prediction to produce statistically
valid prediction intervals per candidate score, instead of bare point estimates.

Library: MAPIE (scikit-learn-contrib, BSD-3-Clause)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


class UncertaintyEstimator:
    """
    Wraps the fusion ranker with split-conformal prediction to produce
    calibrated [lower, upper] confidence bands per candidate score.
    Falls back to simple standard-deviation bands when MAPIE is unavailable.
    """

    def __init__(self, alpha: float = 0.1) -> None:
        self.alpha = alpha
        self._mapie: Any = None
        self._base_model: Any = None
        self._fitted = False
        self._feature_cols: list[str] | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, feature_cols: list[str] | None = None) -> None:
        """Fit the conformal regressor on training data."""
        self._feature_cols = feature_cols
        try:
            from mapie.regression import MapieRegressor  # type: ignore
            from sklearn.ensemble import GradientBoostingRegressor  # type: ignore

            self._base_model = GradientBoostingRegressor(
                n_estimators=200, max_depth=4, random_state=42,
            )
            self._mapie = MapieRegressor(
                estimator=self._base_model,
                method="plus",
                cv="prefit" if hasattr(self._base_model, "estimators_") else 5,
            )
            if not hasattr(self._base_model, "estimators_"):
                # Fit both the base model and MAPIE calibration
                self._mapie.fit(X, y)
            else:
                # Base model already fitted externally
                self._mapie.fit(X, y)
            self._fitted = True
            log.info("MAPIE uncertainty estimator fitted (alpha=%.2f).", self.alpha)
        except ImportError:
            log.warning(
                "MAPIE not installed; uncertainty will use simple std-dev bands. "
                "Install with: pip install mapie"
            )
            # Fallback: store training data for simple stats
            self._train_y_mean = float(np.mean(y))
            self._train_y_std = float(np.std(y)) + 1e-9
            self._fitted = True

    def predict_with_bounds(self, X: np.ndarray) -> list[dict[str, Any]]:
        """
        Returns per-candidate confidence bands:
          - point_estimate: the predicted score
          - lower_bound / upper_bound: calibrated interval
          - confidence_width: band width
          - is_high_confidence: True if width < threshold
        """
        if not self._fitted or X.shape[0] == 0:
            return []

        results: list[dict[str, Any]] = []
        if self._mapie is not None:
            try:
                y_pred, y_pis = self._mapie.predict(X, alpha=self.alpha)
                for i in range(len(y_pred)):
                    lo = float(y_pis[i, 0, 0])
                    hi = float(y_pis[i, 1, 0])
                    results.append({
                        "point_estimate": float(y_pred[i]),
                        "lower_bound": lo,
                        "upper_bound": hi,
                        "confidence_width": hi - lo,
                        "is_high_confidence": (hi - lo) < 0.15,
                    })
                return results
            except Exception as exc:  # noqa: BLE001
                log.warning("MAPIE predict failed (%s), falling back to std bands.", exc)

        # Fallback: point estimate ± 1.5 * training std
        for i in range(X.shape[0]):
            pe = float(np.mean(X[i]))  # crude fallback
            band = getattr(self, "_train_y_std", 0.1) * 1.5
            results.append({
                "point_estimate": pe,
                "lower_bound": max(0.0, pe - band),
                "upper_bound": min(1.0, pe + band),
                "confidence_width": band * 2,
                "is_high_confidence": band < 0.075,
            })
        return results

    def is_available(self) -> bool:
        return self._mapie is not None
