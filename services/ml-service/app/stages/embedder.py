"""
Stage 2 — Contextual Relevance (embedding).

Qwen3-Embedding-0.6B via sentence-transformers. The model is
instruction-aware — we prepend different task instructions to JD vs
candidate text so both end up in a shared semantic space optimized for
retrieval.

Falls back to a lightweight hashing-based embedder when the model can't
be loaded (no internet, no weights downloaded), so the rest of the
pipeline remains runnable end-to-end by judges.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import numpy as np

from ..config import get_settings

log = logging.getLogger(__name__)

JD_INSTRUCTION = "Represent this job description for retrieving relevant candidate profiles: "
CANDIDATE_INSTRUCTION = "Represent this candidate profile for job matching: "

# Qwen3-Embedding-0.6B native dimension. The hashing fallback must match.
EMBED_DIM = 1024


def _flatten_jd(jd: dict[str, Any]) -> str:
    return (
        f"Role: {jd.get('role_title', '')}. "
        f"Seniority: {jd.get('seniority', '')}. "
        f"Must-have: {', '.join(jd.get('must_have_skills', []) or [])}. "
        f"Nice-to-have: {', '.join(jd.get('nice_to_have_skills', []) or [])}. "
        f"Domain: {jd.get('domain', '')}. "
        f"Min years: {jd.get('min_years_experience', 0)}. "
        f"Soft reqs: {', '.join(jd.get('soft_requirements', []) or [])}. "
        f"Implicit reqs: {', '.join(jd.get('implicit_requirements', []) or [])}."
    )


def _hash_embed(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """
    Deterministic, dependency-free fallback embedder.
    Bag-of-token hashed features → L2-normalized. Strictly worse than Qwen3
    semantically, but keeps the pipeline fully runnable offline.
    """
    vec = np.zeros(dim, dtype=np.float32)
    for token in text.lower().split():
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    # bigrams for a bit more signal
    tokens = text.lower().split()
    for a, b in zip(tokens, tokens[1:]):
        h = int(hashlib.md5(f"{a}_{b}".encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 0.5
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


class Embedder:
    """Wraps the sentence-transformers model with a graceful offline fallback."""

    def __init__(self) -> None:
        self._model: Any = None
        self._fallback = False
        self._load_attempted = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        model_name = getattr(settings, "qwen_embedding_model", "Qwen/Qwen-Embedding-0.6B")
        try:
            from sentence_transformers import SentenceTransformer  # lazy import
            log.info("Loading embedding model %s …", model_name)
            self._model = SentenceTransformer(
                model_name, trust_remote_code=True
            )
            log.info("Embedding model loaded.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Could not load %s (%s). Falling back to hashing embedder. "
                "Run scripts/download_models.sh for full semantic quality.",
                model_name,
                exc,
            )
            self._model = None
            self._fallback = True

    def _encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        self._ensure_model()
        if self._model is not None:
            return np.asarray(
                self._model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )
        return np.vstack([_hash_embed(t) for t in texts])

    def embed_jd(self, structured_jd: dict[str, Any]) -> np.ndarray:
        text = JD_INSTRUCTION + _flatten_jd(structured_jd)
        return self._encode([text])[0]

    def embed_candidate(self, profile_text: str) -> np.ndarray:
        return self._encode([CANDIDATE_INSTRUCTION + profile_text])[0]

    def embed_candidates_batch(self, profiles: list[str]) -> np.ndarray:
        texts = [CANDIDATE_INSTRUCTION + p for p in profiles]
        if not texts:
            return np.zeros((0, EMBED_DIM), dtype=np.float32)
        return self._encode(texts)

    @property
    def is_fallback(self) -> bool:
        self._ensure_model()
        return self._fallback
