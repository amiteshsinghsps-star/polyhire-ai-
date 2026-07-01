"""
3D Galaxy projection.

Reduces the high-dimensional candidate feature space to 3D coordinates for
the "Candidate Galaxy" visualization (§11). The JD sits at the origin; each
candidate is placed so that semantic + fused-signal similarity maps to
spatial proximity. Closer to core = better match.

Primary reducer: UMAP. Fallback: a deterministic PCA-ish projection via SVD,
then a radial jitter based on rank — so the galaxy is always renderable.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


def _normalize_rows(X: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return X / norms


def _fallback_project(vectors: np.ndarray, ranks: np.ndarray, scores: np.ndarray) -> np.ndarray:
    """
    No-UMAP fallback: SVD to 3 dims, then push points outward by inverse rank
    so the top-ranked candidates cluster nearest the JD core (origin).
    """
    if vectors.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float32)
    X = _normalize_rows(vectors.astype(np.float64))
    if X.shape[1] > 3:
        # Truncated SVD via numpy (works on (n, d) for n >= 3 or n < 3)
        try:
            u, s, vt = np.linalg.svd(X, full_matrices=False)
            X3 = u[:, :3] * s[:3]
        except np.linalg.LinAlgError:
            X3 = X[:, :3]
    else:
        X3 = X
    if X3.shape[1] < 3:
        pad = np.zeros((X3.shape[0], 3 - X3.shape[1]))
        X3 = np.hstack([X3, pad])
    # Scale magnitude by score: high-score candidates pulled toward the core.
    radius = 1.0 - np.clip(scores, 0.0, 1.0)  # higher score → smaller radius
    radius = 0.3 + radius * 2.5  # keep min radius so nodes don't stack at origin
    direction = X3 / (np.linalg.norm(X3, axis=1, keepdims=True) + 1e-9)
    coords = direction * radius[:, None]
    # Deterministic per-rank angular jitter so nodes don't sit on a single ray.
    rng = np.random.default_rng(seed=42)
    jitter = rng.normal(0.0, 0.05, size=coords.shape)
    return (coords + jitter).astype(np.float32)


def project_galaxy(
    jd_vector: np.ndarray,
    candidate_vectors: np.ndarray,
    ranks: list[int],
    scores: list[float],
    clusters: list[str],
    candidate_ids: list[str],
    use_umap: bool = True,
) -> list[dict[str, Any]]:
    """
    Build the GalaxyNode list for the frontend.

    Returns a list of dicts matching the GalaxyNode schema in shared-types:
      { candidateId, x, y, z, rank, score, cluster, isNearMiss }
    The JD core node is always at (0, 0, 0).
    """
    n = len(candidate_ids)
    if n == 0:
        return []

    ranks_arr = np.asarray(ranks, dtype=np.int32)
    scores_arr = np.clip(np.asarray(scores, dtype=np.float64), 0.0, 1.0)

    if use_umap and n >= 5:
        try:
            from umap import UMAP  # type: ignore

            reducer = UMAP(n_components=3, n_neighbors=min(15, n - 1), min_dist=0.3, random_state=42)
            stacked = np.vstack([jd_vector.reshape(1, -1), candidate_vectors])
            projected = reducer.fit_transform(stacked)
            # Re-center so the JD core (row 0) is at the origin.
            coords = projected[1:] - projected[0]
        except Exception as exc:  # noqa: BLE001
            log.info("UMAP unavailable (%s); using SVD fallback projection.", exc)
            coords = _fallback_project(candidate_vectors, ranks_arr, scores_arr)
    else:
        coords = _fallback_project(candidate_vectors, ranks_arr, scores_arr)

    nodes: list[dict[str, Any]] = []
    shortlist_size = int(np.median(ranks_arr)) if len(ranks_arr) else 0  # unused, kept explicit
    del shortlist_size
    for i, cid in enumerate(candidate_ids):
        nodes.append(
            {
                "candidateId": cid,
                "x": float(coords[i, 0]),
                "y": float(coords[i, 1]),
                "z": float(coords[i, 2]),
                "rank": int(ranks_arr[i]),
                "score": float(scores_arr[i]),
                "cluster": clusters[i],
                "isNearMiss": int(ranks_arr[i]) > 20,
            }
        )
    return nodes
