"""
Enterprise Feature §23.6 — Passive Talent Pool Mining.

Background job that scores every candidate against a library of role archetypes
(clusters derived from historical JDs), surfacing high-fit candidates before a
matching role is even posted.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

log = logging.getLogger(__name__)


class PassiveTalentMiner:
    """
    Maintains role archetype embeddings and flags candidates who are strong
    latent matches for archetypes with no currently open requisition.
    """

    def __init__(self, embedder: Any = None) -> None:
        self.embedder = embedder
        self.archetypes: dict[str, np.ndarray] = {}

    def build_archetypes(
        self,
        historical_jds: list[dict[str, Any]],
        min_cluster_size: int = 5,
    ) -> dict[str, np.ndarray]:
        """Clusters historical JD embeddings into reusable role archetypes."""
        from sklearn.cluster import KMeans  # type: ignore

        if not self.embedder:
            log.warning("No embedder provided; cannot build archetypes.")
            return self.archetypes

        jd_embeddings = np.array([self.embedder.embed_jd(jd) for jd in historical_jds])
        n_clusters = max(2, len(historical_jds) // min_cluster_size)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit(jd_embeddings)

        for cluster_id in range(n_clusters):
            mask = kmeans.labels_ == cluster_id
            if mask.sum() >= min_cluster_size:
                centroid = jd_embeddings[mask].mean(axis=0)
                sample_titles = [historical_jds[i].get("role_title", "") for i in np.where(mask)[0][:3]]
                name = f"archetype_{cluster_id}_{'_'.join(t for t in sample_titles[:1] if t) or 'general'}"
                self.archetypes[name] = centroid.astype(np.float32)

        log.info("Built %d role archetypes from %d JDs.", len(self.archetypes), len(historical_jds))
        return self.archetypes

    def scan_candidate_pool(
        self,
        candidates: list[dict[str, Any]],
        threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        """Returns candidates strongly matching an archetype."""
        if not self.embedder or not self.archetypes:
            return []

        from datetime import datetime, timezone

        flags: list[dict[str, Any]] = []
        for candidate in candidates:
            try:
                cand_embedding = self.embedder.embed_candidate(
                    candidate.get("profile_text", candidate.get("summary", ""))
                )
            except Exception:  # noqa: BLE001
                continue

            for archetype_name, archetype_embedding in self.archetypes.items():
                sim = self._cosine_sim(cand_embedding, archetype_embedding)
                if sim >= threshold:
                    flags.append({
                        "candidate_id": candidate.get("id", candidate.get("candidate_id", "")),
                        "matched_archetype": archetype_name,
                        "similarity": float(sim),
                        "flagged_at": datetime.now(timezone.utc).isoformat(),
                        "recommended_action": (
                            "Proactively reach out — strong latent fit for a recurring role pattern."
                        ),
                    })

        flags.sort(key=lambda f: f["similarity"], reverse=True)
        log.info("Passive talent scan: %d flags across %d candidates.", len(flags), len(candidates))
        return flags

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
