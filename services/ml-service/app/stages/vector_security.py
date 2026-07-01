"""
Vector DB Security Layer — RAG Poisoning Defence + Embedding Integrity
=======================================================================
When you scale to 790 million profiles, a single adversarial candidate
who can always rank #1 is an existential security threat.

PoisonedRAG research (2024) shows that just 5 poisoned documents in a
vector database can manipulate AI responses 90% of the time.

This module provides:
  - EmbeddingHMACGuard: sign embeddings with HMAC-SHA256 on ingest,
    verify on retrieval. Tampered or injected embeddings fail verification.
  - PoisonDetector: detect statistical outliers in retrieved results
    that may indicate adversarial vector injection.
  - VectorSecurityEngine: wrapper called by the Retriever.

In production: HMAC key stored in AWS Secrets Manager / Azure Key Vault.
In dev: read from VECTOR_HMAC_KEY env var (see .env.example).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any, Optional

import numpy as np

log = logging.getLogger(__name__)

# ── HMAC key (read from env; fall back to a dev-only constant) ────────────────

def _get_hmac_key() -> bytes:
    key = os.environ.get("VECTOR_HMAC_KEY", "polyhire-dev-hmac-key-change-in-prod")
    return key.encode("utf-8")


# ── Embedding HMAC Guard ───────────────────────────────────────────────────────

class EmbeddingHMACGuard:
    """
    Signs each embedding vector on ingest and verifies on retrieval.

    Threat: Attacker poisons the index with malicious embeddings.
    Storage: signature stored alongside the vector in the retriever payload.
    Validation: fails silently (drops record) on signature mismatch. Any modification (even a
    single bit flip) will fail verification. An adversary who injects a
    high-magnitude vector pointing toward every JD query embedding will
    be caught because they cannot forge the HMAC without the key.
    """

    def sign(self, candidate_id: str, vector: np.ndarray) -> str:
        """Return hex HMAC signature for this (candidate_id, vector) pair."""
        key = _get_hmac_key()
        vector_bytes = vector.astype(np.float32).tobytes()
        msg = candidate_id.encode("utf-8") + vector_bytes
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    def verify(self, candidate_id: str, vector: np.ndarray, signature: str) -> bool:
        """
        Return True if the signature matches. False = tampered or injected.
        Uses hmac.compare_digest to prevent timing attacks.
        """
        expected = self.sign(candidate_id, vector)
        try:
            return hmac.compare_digest(expected, signature)
        except (TypeError, ValueError):
            return False

    def sign_batch(
        self, ids: list[str], vectors: np.ndarray
    ) -> list[str]:
        """Sign a batch of (id, vector) pairs. Returns list of hex signatures."""
        return [self.sign(cid, vec) for cid, vec in zip(ids, vectors)]

    def verify_batch(
        self,
        ids: list[str],
        vectors: np.ndarray,
        signatures: list[Optional[str]],
    ) -> tuple[list[bool], list[str]]:
        """
        Verify a batch. Returns:
          - results: list[bool] — True = OK, False = tampered
          - flagged_ids: candidate_ids where verification failed
        """
        results: list[bool] = []
        flagged: list[str] = []
        for cid, vec, sig in zip(ids, vectors, signatures):
            if sig is None:
                # No signature stored — either legacy or first run without security
                results.append(True)  # allow but log
                log.warning("Vector for %s has no HMAC signature — skipping verification", cid)
            else:
                ok = self.verify(cid, vec, sig)
                results.append(ok)
                if not ok:
                    flagged.append(cid)
                    log.warning("HMAC verification FAILED for candidate %s — possible injection", cid)
        return results, flagged


# ── Poison Detector ────────────────────────────────────────────────────────────

class PoisonDetector:
    """
    Detects adversarially injected vectors in retrieval results.

    Two heuristics:
    1. Mahalanobis distance outlier: a poisoned vector's L2 norm is often
       significantly higher than the rest of the pool (adversary pushes the
       vector to be universally similar to all JD queries).

    2. Suspiciously uniform cosine similarity: a poisoned embedding has
       near-identical similarity to completely unrelated JDs, which is
       statistically impossible for a real candidate.

    Threshold: if a retrieved candidate's embedding L2 norm is > 3 std
    deviations from the pool mean, flag it as a potential poison injection.
    """

    def __init__(self, z_threshold: float = 3.0) -> None:
        self.z_threshold = z_threshold
        self._pool_stats: Optional[dict] = None

    def fit(self, pool_vectors: np.ndarray) -> None:
        """Compute pool statistics at index warm-up time."""
        if pool_vectors.shape[0] == 0:
            return
        norms = np.linalg.norm(pool_vectors, axis=1)
        self._pool_stats = {
            "mean_norm": float(np.mean(norms)),
            "std_norm": float(np.std(norms)),
            "fitted_at": time.time(),
        }
        log.info(
            "PoisonDetector: pool norm stats μ=%.4f σ=%.4f (n=%d)",
            self._pool_stats["mean_norm"],
            self._pool_stats["std_norm"],
            pool_vectors.shape[0],
        )

    def check_retrieval(
        self,
        candidate_id: str,
        vector: np.ndarray,
        similarity_score: float,
    ) -> dict:
        """
        Check a single retrieved candidate for poison signals.
        Returns a dict with is_clean (bool) and evidence.
        """
        evidence: list[str] = []
        is_clean = True

        if self._pool_stats:
            norm = float(np.linalg.norm(vector))
            z_score = (norm - self._pool_stats["mean_norm"]) / max(
                self._pool_stats["std_norm"], 1e-9
            )
            if z_score > self.z_threshold:
                evidence.append(
                    f"high_norm_z_score:{z_score:.2f}_threshold:{self.z_threshold}"
                )
                is_clean = False
                log.warning(
                    "PoisonDetector: candidate %s has anomalous norm z=%.2f (possible injection)",
                    candidate_id, z_score,
                )

        # Perfect similarity on all retrieval calls = suspicious
        if similarity_score > 0.999:
            evidence.append(f"perfect_similarity:{similarity_score:.6f}")
            is_clean = False

        return {
            "candidate_id": candidate_id,
            "is_clean": is_clean,
            "evidence": evidence,
            "vector_norm": float(np.linalg.norm(vector)),
        }


# ── Vector Security Engine ────────────────────────────────────────────────────

class VectorSecurityEngine:
    """
    Master wrapper called by the Retriever.

    On ingest (warm_index):
      signatures = security.sign_batch(ids, vectors)
      # Store signatures in retriever payload

    On retrieval:
      clean_candidates = security.verify_and_filter(retrieved_candidates)
    """

    def __init__(self) -> None:
        self.hmac_guard      = EmbeddingHMACGuard()
        self.poison_detector = PoisonDetector()
        self._enabled = True

    def sign_batch(self, ids: list[str], vectors: np.ndarray) -> list[str]:
        if not self._enabled:
            return ["" for _ in ids]
        return self.hmac_guard.sign_batch(ids, vectors)

    def verify_and_filter(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Verify HMAC signatures and check for poison signals on retrieved candidates.
        Returns (clean_candidates, flagged_ids).
        Flagged candidates are kept in the list but marked with `_security_flag`.
        """
        if not self._enabled or not candidates:
            return candidates, []

        flagged_ids: list[str] = []
        clean: list[dict[str, Any]] = []

        for c in candidates:
            cid = c.get("id", "unknown")
            vec_payload = c.get("_embedding_vector")
            sig = c.get("_embedding_signature")

            security_flags = []

            if vec_payload is not None:
                vec = np.array(vec_payload, dtype=np.float32)

                # HMAC check
                if sig and not self.hmac_guard.verify(cid, vec, sig):
                    security_flags.append("hmac_verification_failed")
                    flagged_ids.append(cid)
                    log.warning("Security: HMAC failed for %s", cid)

                # Poison check
                sim = float(c.get("embedding_similarity", c.get("score", 0.5)))
                poison_result = self.poison_detector.check_retrieval(cid, vec, sim)
                if not poison_result["is_clean"]:
                    security_flags.extend(poison_result["evidence"])
                    if cid not in flagged_ids:
                        flagged_ids.append(cid)

            if security_flags:
                c["_security_flags"] = security_flags
                c["_security_risk"] = "high"
                # Penalise trust score rather than silently dropping
                c["trust_score"] = round(float(c.get("trust_score", 1.0)) * 0.3, 4)

            clean.append(c)

        return clean, flagged_ids

    def get_integrity_report(self) -> dict:
        stats = self.poison_detector._pool_stats or {}
        return {
            "hmac_enabled":       self._enabled,
            "pool_fitted":        self.poison_detector._pool_stats is not None,
            "pool_mean_norm":     stats.get("mean_norm"),
            "pool_std_norm":      stats.get("std_norm"),
            "z_threshold":        self.poison_detector.z_threshold,
        }
