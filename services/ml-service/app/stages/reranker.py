"""
Stage 4 — Cross-encoder reranking precision pass.

Uses gte-reranker-modernbert-base (Alibaba-NLP). Falls back to a token-overlap
scorer when the model can't load, so the rest of the pipeline is never blocked.
"""
from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)


def _token_overlap_score(jd_text: str, candidate_text: str) -> float:
    """Fallback scorer: logit-ish value derived from token Jaccard × density."""
    jd_tokens = {t for t in jd_text.lower().split() if len(t) > 2}
    cand_tokens = {t for t in candidate_text.lower().split() if len(t) > 2}
    if not jd_tokens or not cand_tokens:
        return 0.0
    inter = len(jd_tokens & cand_tokens)
    union = len(jd_tokens | cand_tokens)
    return float(inter / union) * 4.0 - 2.0  # center around 0 like a logit


class Reranker:
    def __init__(self) -> None:
        self._model: Any = None
        self._fallback = False
        self._load_attempted = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        try:
            from sentence_transformers import CrossEncoder  # lazy import

            log.info("Loading reranker %s …", settings.reranker_model)
            self._model = CrossEncoder(settings.reranker_model, trust_remote_code=True)
            log.info("Reranker loaded.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Could not load %s (%s). Falling back to token-overlap reranker. "
                "Run scripts/download_models.sh for full precision.",
                settings.reranker_model,
                exc,
            )
            self._model = None
            self._fallback = True

    def rerank(
        self, jd_text: str, candidates: list[dict[str, Any]], top_k: int = 30
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        self._ensure_model()
        for c in candidates:
            c.setdefault("rerank_score", 0.0)

        if self._model is not None:
            pairs = [[jd_text, str(c.get("profile_text", c.get("summary", "")))] for c in candidates]
            scores = self._model.predict(pairs)
            for c, s in zip(candidates, scores):
                c["rerank_score"] = float(s)
        else:
            for c in candidates:
                c["rerank_score"] = _token_overlap_score(
                    jd_text, str(c.get("profile_text", c.get("summary", "")))
                )

        ranked = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
        return ranked[:top_k]

    @property
    def is_fallback(self) -> bool:
        self._ensure_model()
        return self._fallback
