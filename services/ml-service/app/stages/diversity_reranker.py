"""
Enterprise Feature §23.5 — Diversity-Aware Re-ranking.

Opt-in Maximal Marginal Relevance (MMR) re-ranking that balances relevance
against diversity within the embedding space already computed in Stage 2.
No new model needed — just a different selection objective over existing scores.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


class DiversityReranker:
    """
    Re-orders the top-N candidates using Maximal Marginal Relevance:
    balances staying close to the JD (relevance) against staying far
    from already-selected candidates (diversity), in embedding space.

    Strictly opt-in and fully transparent.
    """

    def __init__(self, lambda_param: float = 0.7) -> None:
        # lambda=1.0 => pure relevance; lambda=0.0 => pure diversity
        self.lambda_param = lambda_param

    def rerank(
        self,
        candidate_embeddings: np.ndarray,
        relevance_scores: np.ndarray,
        candidate_ids: list[str],
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Returns diversity-optimized ranked list."""
        selected_idx: list[int] = []
        remaining_idx = list(range(len(candidate_ids)))

        if len(relevance_scores) == 0:
            return []

        # Seed with highest-relevance candidate
        first = int(np.argmax(relevance_scores))
        selected_idx.append(first)
        remaining_idx.remove(first)

        while len(selected_idx) < top_k and remaining_idx:
            mmr_scores: list[tuple[int, float]] = []
            for idx in remaining_idx:
                relevance = relevance_scores[idx]
                max_sim_to_selected = max(
                    self._cosine_sim(candidate_embeddings[idx], candidate_embeddings[s])
                    for s in selected_idx
                )
                mmr = self.lambda_param * relevance - (1 - self.lambda_param) * max_sim_to_selected
                mmr_scores.append((idx, mmr))
            best_idx, _ = max(mmr_scores, key=lambda x: x[1])
            selected_idx.append(best_idx)
            remaining_idx.remove(best_idx)

        return [
            {
                "candidate_id": candidate_ids[i],
                "relevance_score": float(relevance_scores[i]),
                "selection_order": rank,
            }
            for rank, i in enumerate(selected_idx, start=1)
        ]

    def diversity_report(
        self,
        original_order: list[str],
        diversified_order: list[str],
    ) -> dict[str, Any]:
        """Quantifies how much the diversity pass changed the shortlist."""
        reordered_count = 0
        for i, cid in enumerate(diversified_order):
            if cid not in original_order:
                continue
            orig_pos = original_order.index(cid)
            if orig_pos != i:
                reordered_count += 1
        total = min(len(diversified_order), len(original_order))
        return {
            "candidates_reordered_pct": round((reordered_count / total) * 100, 1) if total else 0,
            "top_5_unchanged": original_order[:5] == diversified_order[:5],
        }

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
