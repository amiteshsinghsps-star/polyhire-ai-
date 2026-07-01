"""
Enterprise Feature §23.2 — Counterfactual Explanation Engine.

Generates minimal feature perturbations that would move a candidate above
a target rank threshold — answers "what would need to change."

Library: DiCE (Microsoft Research, MIT License)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from .fusion_ranker import FEATURE_COLS

log = logging.getLogger(__name__)

_READABLE_NAMES: dict[str, str] = {
    "years_experience_match": "years of relevant experience",
    "skill_overlap_ratio": "skill overlap with the role",
    "career_trajectory_slope": "rate of career progression",
    "engagement_score": "platform activity and profile completeness",
    "recency_of_activity": "recency of platform activity",
    "embedding_similarity": "semantic similarity to the JD",
    "rerank_score": "cross-encoder relevance",
    "trust_score": "profile trustworthiness",
}


class CounterfactualEngine:
    """
    Generates minimal changes that would push a candidate's score to a target.
    Falls back to a greedy perturbation search when DiCE is unavailable.
    """

    def __init__(self, fusion_model: Any = None, training_df: pd.DataFrame | None = None) -> None:
        self._fusion_model = fusion_model
        self._training_df = training_df
        self._dice: Any = None
        self._init_dice()

    def _init_dice(self) -> None:
        try:
            import dice_ml  # type: ignore

            if self._fusion_model is not None and self._training_df is not None:
                data_interface = dice_ml.Data(
                    dataframe=self._training_df,
                    continuous_features=list(FEATURE_COLS),
                    outcome_name="fusion_score",
                )
                model_interface = dice_ml.Model(
                    model=self._fusion_model, backend="sklearn", model_type="regressor",
                )
                self._dice = dice_ml.Dice(
                    data_interface, model_interface, method="genetic",
                )
                log.info("DiCE counterfactual engine initialized.")
        except ImportError:
            log.warning(
                "DiCE not installed; counterfactuals will use greedy search. "
                "Install with: pip install dice-ml"
            )

    def explain(
        self,
        candidate_row: dict[str, float],
        target_score: float,
        total_cfs: int = 3,
    ) -> list[dict[str, Any]]:
        """Returns minimal changes to reach the target score."""
        results: list[dict[str, Any]] = []

        # Try DiCE first
        if self._dice is not None:
            try:
                import dice_ml  # type: ignore

                df_row = pd.DataFrame([candidate_row])
                cf = self._dice.generate_counterfactuals(
                    df_row[FEATURE_COLS],
                    total_CFs=total_cfs,
                    desired_range=[target_score, target_score + 0.1],
                )
                cf_df = cf.cf_examples_list[0].final_cfs_df
                original = candidate_row
                for _, row in cf_df.iterrows():
                    changes = {
                        col: {"from": float(original.get(col, 0)), "to": float(row[col])}
                        for col in FEATURE_COLS
                        if abs(row[col] - original.get(col, 0)) > 1e-3
                    }
                    results.append({
                        "changes": changes,
                        "resulting_score": target_score,
                    })
                return results
            except Exception as exc:  # noqa: BLE001
                log.warning("DiCE failed (%s), falling back to greedy search.", exc)

        # Fallback: greedy perturbation
        return self._greedy_counterfactuals(candidate_row, target_score, total_cfs)

    def _greedy_counterfactuals(
        self, row: dict[str, float], target: float, n: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Simple greedy approach: for each feature, compute the delta needed
        to reach the target assuming a linear baseline weighting.
        """
        from .fusion_ranker import BASELINE_WEIGHTS

        baseline = BASELINE_WEIGHTS
        total_w = sum(baseline.values()) or 1.0
        current_score = sum(baseline.get(f, 0) * row.get(f, 0) for f in FEATURE_COLS) / total_w
        deficit = target - current_score

        if deficit <= 0:
            return [{"changes": {}, "resulting_score": current_score}]

        # Find features that can be increased
        candidates = []
        for feat in FEATURE_COLS:
            w = baseline.get(feat, 0) / total_w
            room = 1.0 - row.get(feat, 0)
            if w > 0 and room > 0:
                needed = deficit / w
                if needed <= room:
                    candidates.append((feat, needed, w))
                else:
                    candidates.append((feat, room, w))

        candidates.sort(key=lambda x: x[2], reverse=True)  # highest-weight first
        results = []
        for i, (feat, delta, _) in enumerate(candidates[:n]):
            change = {
                "changes": {
                    feat: {
                        "from": float(row.get(feat, 0)),
                        "to": float(row.get(feat, 0) + delta),
                    }
                },
                "resulting_score": target,
            }
            results.append(change)
        return results

    def to_human_readable(self, counterfactual: dict[str, Any]) -> str:
        """Converts a raw counterfactual dict into recruiter/candidate-facing prose."""
        parts = []
        for feat, delta in counterfactual.get("changes", {}).items():
            name = _READABLE_NAMES.get(feat, feat)
            direction = "higher" if delta["to"] > delta["from"] else "lower"
            parts.append(f"{name} were {direction}")
        if not parts:
            return "This candidate is already in the target tier."
        return "If " + " and ".join(parts) + f", this candidate would rank in the top tier."

    def is_available(self) -> bool:
        return self._dice is not None
