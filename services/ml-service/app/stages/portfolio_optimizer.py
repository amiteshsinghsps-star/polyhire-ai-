"""
Enterprise Feature §23.3 — Cross-Role Portfolio Optimization.

Treats multi-role hiring as a global assignment problem: build a cost matrix
of (candidate × role) fusion scores, solve via the Hungarian algorithm for the
assignment that maximizes total quality across ALL open roles simultaneously.

Library: scipy.optimize.linear_sum_assignment (BSD-3-Clause, part of scipy)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Solves the multi-role, multi-candidate assignment problem so that
    strong candidates are distributed across open roles instead of all
    being recommended for the same single role.
    """

    def optimize(
        self,
        score_matrix: pd.DataFrame,
        slots_per_role: dict[str, int],
    ) -> list[dict[str, Any]]:
        """
        Args:
            score_matrix: rows = candidates, columns = role_ids, values = fusion_score
            slots_per_role: how many shortlist slots each role gets

        Returns:
            The globally optimal candidate-to-role assignment.
        """
        # Expand columns: each role gets `slots` virtual columns for the Hungarian algorithm
        expanded_cols: list[str] = []
        col_to_role: dict[str, str] = {}
        for role_id, slots in slots_per_role.items():
            if role_id not in score_matrix.columns:
                log.warning("Role '%s' not in score matrix, skipping.", role_id)
                continue
            for slot_idx in range(slots):
                col_name = f"{role_id}__slot{slot_idx}"
                expanded_cols.append(col_name)
                col_to_role[col_name] = role_id

        if not expanded_cols:
            return []

        cost_matrix = np.zeros((len(score_matrix), len(expanded_cols)))
        for j, col in enumerate(expanded_cols):
            role_id = col_to_role[col]
            cost_matrix[:, j] = -score_matrix[role_id].values  # negative: maximize = minimize cost

        row_ind, col_ind = self._hungarian(cost_matrix)

        assignments: list[dict[str, Any]] = []
        for r, c in zip(row_ind, col_ind):
            score = -cost_matrix[r, c]
            if score > 0:
                assignments.append({
                    "candidate_id": score_matrix.index[r],
                    "assigned_role": col_to_role[expanded_cols[c]],
                    "score": float(score),
                })
        return sorted(assignments, key=lambda a: a["score"], reverse=True)

    def compare_to_naive(
        self,
        score_matrix: pd.DataFrame,
        slots_per_role: dict[str, int],
    ) -> dict[str, Any]:
        """Quantifies improvement over independent per-role top-K ranking."""
        naive_picks: set[tuple[str, str]] = set()
        for role_id, slots in slots_per_role.items():
            if role_id not in score_matrix.columns:
                continue
            top_k = score_matrix[role_id].nlargest(slots)
            for cid in top_k.index:
                naive_picks.add((str(cid), role_id))

        optimized = self.optimize(score_matrix, slots_per_role)
        optimized_picks = {(a["candidate_id"], a["assigned_role"]) for a in optimized}

        naive_total_score = sum(
            score_matrix.loc[cid, role] for cid, role in naive_picks
            if role in score_matrix.columns and cid in score_matrix.index
        )
        optimized_total_score = sum(a["score"] for a in optimized)

        return {
            "naive_total_score": float(naive_total_score),
            "optimized_total_score": float(optimized_total_score),
            "naive_unique_candidates_used": len({cid for cid, _ in naive_picks}),
            "optimized_unique_candidates_used": len({a["candidate_id"] for a in optimized}),
            "candidate_pool_utilization_gain": (
                len({a["candidate_id"] for a in optimized})
                - len({cid for cid, _ in naive_picks})
            ),
        }

    def _hungarian(self, cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Run the Hungarian algorithm via scipy."""
        from scipy.optimize import linear_sum_assignment  # type: ignore

        return linear_sum_assignment(cost_matrix)
