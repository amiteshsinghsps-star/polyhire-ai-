"""Independent rule-based silver-label scorer for offline weight tuning."""
from __future__ import annotations
import math


def silver_relevance(candidate: dict) -> int:
    title = (candidate.get("profile", {}).get("current_title") or "").lower()
    yoe = candidate.get("profile", {}).get("years_of_experience", 0) or 0
    descriptions = " ".join(r.get("description", "") for r in candidate.get("career_history", [])).lower()

    has_ir_keywords = any(
        k in descriptions for k in ["retrieval", "ranking", "embeddings", "search", "recommendation"]
    )
    has_ml_title = any(
        k in title for k in ["ml", "machine learning", "ai engineer", "applied scientist", "data scientist"]
    )
    in_band = 4 <= yoe <= 11

    score = int(has_ir_keywords) + int(has_ml_title) + int(in_band)
    return min(3, score)


def ndcg_at_k(ranked_relevances: list[int], k: int) -> float:
    dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ranked_relevances[:k]))
    ideal = sorted(ranked_relevances, reverse=True)
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0


def average_precision(ranked_relevances: list[int], relevance_threshold: int = 1) -> float:
    hits, precision_sum = 0, 0.0
    for i, rel in enumerate(ranked_relevances, start=1):
        if rel >= relevance_threshold:
            hits += 1
            precision_sum += hits / i
    return precision_sum / hits if hits > 0 else 0.0


def precision_at_k(ranked_relevances: list[int], k: int, threshold: int = 1) -> float:
    top_k = ranked_relevances[:k]
    return sum(1 for r in top_k if r >= threshold) / k


def composite(ranked_candidates: list[dict]) -> dict:
    rels = [silver_relevance(c) for c in ranked_candidates]
    score = (
        0.50 * ndcg_at_k(rels, 10)
        + 0.30 * ndcg_at_k(rels, 50)
        + 0.15 * average_precision(rels)
        + 0.05 * precision_at_k(rels, 10)
    )
    return {
        "composite": round(score, 4),
        "ndcg@10": round(ndcg_at_k(rels, 10), 4),
        "ndcg@50": round(ndcg_at_k(rels, 50), 4),
        "map": round(average_precision(rels), 4),
        "p@10": round(precision_at_k(rels, 10), 4),
        "p@5": round(precision_at_k(rels, 5), 4),
    }
