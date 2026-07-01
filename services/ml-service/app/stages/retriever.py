"""
Stage 3 — Fast top-K candidate retrieval.

Uses an in-process pure-NumPy/FAISS index, so the pipeline runs with 
zero external services.

The Retriever owns the candidate index. Indexing is decoupled from search
so the orchestrator can warm the index once at boot and query it per JD.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

import numpy as np

from ..config import get_settings

log = logging.getLogger(__name__)

DEFAULT_COLLECTION = "candidates"


class _Backend(Protocol):
    def upsert(self, ids: list[str], vectors: np.ndarray, payloads: list[dict[str, Any]]) -> None: ...

    def search(self, query: np.ndarray, top_k: int) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# NumPy in-memory backend (always available, zero deps beyond numpy)
# ---------------------------------------------------------------------------


class _InMemoryBackend:
    """Plain cosine-similarity search over a stacked matrix. O(N) per query."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._vectors: np.ndarray = np.zeros((0, 1), dtype=np.float32)
        self._payloads: list[dict[str, Any]] = []

    def upsert(self, ids: list[str], vectors: np.ndarray, payloads: list[dict[str, Any]]) -> None:
        id_to_idx = {cid: i for i, cid in enumerate(self._ids)}
        new_rows: list[tuple[str, np.ndarray, dict[str, Any]]] = []
        for cid, vec, payload in zip(ids, vectors, payloads):
            if cid in id_to_idx:
                idx = id_to_idx[cid]
                self._vectors[idx] = vec
                self._payloads[idx] = payload
            else:
                new_rows.append((cid, vec, payload))
        if new_rows:
            new_ids = [r[0] for r in new_rows]
            new_vecs = np.vstack([r[1] for r in new_rows]).astype(np.float32)
            self._ids.extend(new_ids)
            self._payloads.extend([r[2] for r in new_rows])
            self._vectors = (
                new_vecs if self._vectors.shape[0] == 0 else np.vstack([self._vectors, new_vecs])
            )

    def search(self, query: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        if self._vectors.shape[0] == 0:
            return []
        q = query.astype(np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-9)
        v_norm = self._vectors / (np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-9)
        sims = v_norm @ q_norm
        k = min(top_k, len(self._ids))
        # partial top-k via argpartition then sort the small slice
        idx_part = np.argpartition(-sims, k - 1)[:k]
        idx_sorted = idx_part[np.argsort(-sims[idx_part])]
        results: list[dict[str, Any]] = []
        for i in idx_sorted:
            payload = dict(self._payloads[i])
            payload["id"] = self._ids[i]
            payload["embedding_similarity"] = float(sims[i])
            results.append(payload)
        return results


# ---------------------------------------------------------------------------
# FAISS backend (optional, faster for very large pools)
# ---------------------------------------------------------------------------


class _FAISSBackend:
    """Uses faiss-cpu if importable; otherwise the Retriever won't select it."""

    def __init__(self, dim: int) -> None:
        import faiss  # type: ignore

        self._faiss = faiss
        self._index = faiss.IndexFlatIP(dim)  # inner product == cosine on normalized vecs
        self._ids: list[str] = []
        self._payloads: list[dict[str, Any]] = []
        self._dim = dim

    def upsert(self, ids: list[str], vectors: np.ndarray, payloads: list[dict[str, Any]]) -> None:
        # IndexFlatIP doesn't support in-place updates cheaply; rebuild on upsert.
        # Fine for the PoC scale (hundreds–thousands of candidates).
        self._ids.extend(ids)
        self._payloads.extend(payloads)
        self._index.add(np.ascontiguousarray(vectors).astype(np.float32))

    def search(self, query: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        if self._index.ntotal == 0:
            return []
        q = np.ascontiguousarray(query.reshape(1, -1)).astype(np.float32)
        sims, indices = self._index.search(q, min(top_k, self._index.ntotal))
        results: list[dict[str, Any]] = []
        for score, raw_i in zip(sims[0], indices[0]):
            if raw_i < 0:
                continue
            payload = dict(self._payloads[raw_i])
            payload["id"] = self._ids[raw_i]
            payload["embedding_similarity"] = float(score)
            results.append(payload)
        return results


def _stable_int_id(candidate_id: str) -> int:
    import hashlib

    h = hashlib.md5(candidate_id.encode("utf-8")).hexdigest()
    return int(h[:12], 16)  # 48-bit

def _jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure the payload is JSON-serializable, preserving the original id."""
    import dataclasses

    out: dict[str, Any] = {"_candidate_id": payload.get("id")}
    for k, v in payload.items():
        if dataclasses.is_dataclass(v):
            out[k] = dataclasses.asdict(v)
        elif hasattr(v, "tolist"):
            out[k] = v.tolist()
        else:
            out[k] = v
    return out


class Retriever:
    """Selects the best available backend and exposes upsert/search uniformly."""

    def __init__(self, dim: int) -> None:
        self._dim = dim
        self._backend: _Backend | None = None
        self._backend_name = ""

    def _select_backend(self) -> _Backend:
        try:
            backend = _FAISSBackend(self._dim)
            self._backend_name = "faiss"
            log.info("Retriever backend: FAISS (CPU)")
            return backend
        except Exception as exc:  # noqa: BLE001
            log.warning("FAISS unavailable (%s); falling back to NumPy index.", exc)

        self._backend_name = "numpy"
        log.info("Retriever backend: NumPy in-memory")
        return _InMemoryBackend()

    @property
    def backend(self) -> _Backend:
        if self._backend is None:
            self._backend = self._select_backend()
        return self._backend

    @property
    def backend_name(self) -> str:
        _ = self.backend  # ensure initialized
        return self._backend_name

    def upsert_candidates(
        self, ids: list[str], vectors: np.ndarray, payloads: list[dict[str, Any]]
    ) -> None:
        if len(ids) == 0:
            return
        self.backend.upsert(ids, vectors, payloads)

    def search(self, query: np.ndarray, top_k: int = 100) -> list[dict[str, Any]]:
        return self.backend.search(query, top_k=top_k)
