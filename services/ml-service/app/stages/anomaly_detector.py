"""
Bonus Differentiator 5 — PyOD resume anomaly detection.

Flags statistical outliers in the candidate pool (timeline overlaps,
improbable claim density, outlier career velocity). Produces a per-candidate
`trust_score` in [0, 1] that feeds Stage 5 fusion as a feature.

Runs at ingestion time, independent of any specific JD, so it's computed
once per candidate pool. Falls back to a z-score-based heuristic if PyOD
is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from ..config import get_settings

log = logging.getLogger(__name__)

# Columns expected in the ingestion feature matrix.
ANOMALY_FEATURES = [
    "years_experience",
    "num_jobs",
    "avg_tenure_months",
    "title_jump_velocity",
    "claimed_skill_count",
    "profile_completeness",
]


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05) -> None:
        self.contamination = contamination
        self._model: Any = None
        self._load_attempted = False
        self._fallback = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        if not settings.enable_anomaly_detection:
            self._fallback = True
            return
        try:
            from pyod.models.iforest import IForest  # type: ignore

            self._model = IForest(contamination=self.contamination, random_state=42)
            log.info("PyOD IForest anomaly detector ready.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "PyOD unavailable (%s). Using z-score fallback for trust scoring. "
                "Install with: pip install pyod",
                exc,
            )
            self._fallback = True

    def fit_score(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Fit on the candidate pool and return a trust_score ∈ [0,1] per candidate.
        1.0 = highly trustworthy, 0.0 = highly anomalous.

        `feature_matrix` columns should follow ANOMALY_FEATURES order.
        """
        self._ensure_model()
        if feature_matrix.size == 0:
            return np.array([], dtype=np.float64)

        # Sanitize NaN/inf so neither backend blows up.
        X = np.nan_to_num(np.asarray(feature_matrix, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)

        if self._model is not None:
            return self._score_pyod(X)
        return self._score_zscore(X)

    def _score_pyod(self, X: np.ndarray) -> np.ndarray:
        try:
            self._model.fit(X)
            raw = np.asarray(self._model.decision_scores_, dtype=np.float64)
        except Exception as exc:  # noqa: BLE001
            log.warning("PyOD IForest fit failed (%s); using z-score fallback.", exc)
            return self._score_zscore(X)
        return self._normalize_trust(raw)

    def _score_zscore(self, X: np.ndarray) -> np.ndarray:
        # Robust z-scores (median + MAD) per feature, then take the max
        # magnitude across features as the anomaly score.
        if X.shape[0] < 2:
            return np.ones(X.shape[0], dtype=np.float64)
        median = np.median(X, axis=0)
        mad = np.median(np.abs(X - median), axis=0)
        mad_safe = np.where(mad == 0, 1.0, mad)
        z = np.abs((X - median) / (1.4826 * mad_safe))
        raw = z.max(axis=1)
        return self._normalize_trust(raw)

    @staticmethod
    def _normalize_trust(raw_scores: np.ndarray) -> np.ndarray:
        lo, hi = float(raw_scores.min()), float(raw_scores.max())
        if hi - lo < 1e-9:
            return np.ones_like(raw_scores)
        normalized = (raw_scores - lo) / (hi - lo + 1e-9)
        return 1.0 - normalized  # higher anomaly score → lower trust

    @property
    def is_fallback(self) -> bool:
        self._ensure_model()
        return self._fallback
