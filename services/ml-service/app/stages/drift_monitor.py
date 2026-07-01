"""
Enterprise Feature §23.8 — Model Drift Monitoring.

Compares the feature distribution of the current candidate batch against
the distribution the fusion ranker was originally trained on. Surfaces
a drift score the team can act on before ranking quality silently degrades.

Library: Evidently AI (Apache 2.0)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class DriftMonitor:
    """
    Compares current feature distributions against a reference (training-time)
    snapshot. Falls back to simple statistical tests when Evidently is unavailable.
    """

    def __init__(self, reference_data: pd.DataFrame | None = None) -> None:
        self._reference_data = reference_data
        self._evidently_available: bool | None = None
        self._latest_result: dict[str, Any] | None = None

    def set_reference(self, reference_data: pd.DataFrame) -> None:
        """Set the reference (training-time) feature distribution."""
        self._reference_data = reference_data
        log.info("Drift monitor reference set (%d rows).", len(reference_data))

    def check_drift(self, current_data: pd.DataFrame) -> dict[str, Any]:
        """
        Runs drift detection. Returns:
          - dataset_level_drift_detected: bool
          - drifted_features: list[str]
          - recommendation: str
        """
        if self._reference_data is None or current_data.empty:
            return {
                "dataset_level_drift_detected": False,
                "drifted_features": [],
                "recommendation": "No reference data available — cannot check drift.",
            }

        # Try Evidently first
        if self._evidently_available is None:
            try:
                from evidently.report import Report  # type: ignore
                from evidently.metric_preset import DataDriftPreset  # type: ignore

                self._evidently_available = True
            except ImportError:
                self._evidently_available = False
                log.info("Evidently not installed; drift uses KS-test fallback.")

        if self._evidently_available:
            try:
                return self._check_drift_evidently(current_data)
            except Exception as exc:  # noqa: BLE001
                log.warning("Evidently drift check failed (%s), using fallback.", exc)

        return self._check_drift_fallback(current_data)

    def _check_drift_evidently(self, current_data: pd.DataFrame) -> dict[str, Any]:
        from evidently.report import Report  # type: ignore
        from evidently.metric_preset import DataDriftPreset  # type: ignore

        report = Report(metrics=[DataDriftPreset()])
        report.run(reference_data=self._reference_data, current_data=current_data)
        result = report.as_dict()

        drifted_features = [
            metric["result"]["column_name"]
            for metric in result.get("metrics", [])
            if metric.get("metric") == "ColumnDriftMetric"
            and metric.get("result", {}).get("drift_detected")
        ]
        dataset_drift = False
        for metric in result.get("metrics", []):
            if metric.get("metric") == "DatasetDriftMetric":
                dataset_drift = metric.get("result", {}).get("dataset_drift", False)
                break

        self._latest_result = {
            "dataset_level_drift_detected": dataset_drift,
            "drifted_features": drifted_features,
            "recommendation": (
                "Retrain fusion_ranker.txt — significant drift detected in "
                f"{len(drifted_features)} feature(s)."
                if dataset_drift
                else "No action needed — feature distributions stable."
            ),
        }
        return self._latest_result

    def _check_drift_fallback(self, current_data: pd.DataFrame) -> dict[str, Any]:
        """Kolmogorov-Smirnov test per numeric column vs reference."""
        from scipy.stats import ks_2samp  # type: ignore

        numeric_cols = [
            col for col in self._reference_data.columns
            if col in current_data.columns
            and pd.api.types.is_numeric_dtype(self._reference_data[col])
        ]

        drifted_features: list[str] = []
        for col in numeric_cols:
            ref_vals = self._reference_data[col].dropna().values
            cur_vals = current_data[col].dropna().values
            if len(ref_vals) > 0 and len(cur_vals) > 0:
                stat, p_value = ks_2samp(ref_vals, cur_vals)
                if p_value < 0.05:
                    drifted_features.append(col)

        dataset_drift = len(drifted_features) > 0
        self._latest_result = {
            "dataset_level_drift_detected": dataset_drift,
            "drifted_features": drifted_features,
            "recommendation": (
                f"Drift detected in {len(drifted_features)} feature(s) via KS-test. "
                "Consider retraining the fusion ranker."
                if dataset_drift
                else "No action needed — feature distributions stable."
            ),
        }
        return self._latest_result

    def get_latest(self) -> dict[str, Any] | None:
        """Returns the most recent drift check result."""
        return self._latest_result
