"""
Unit Tests — Vector Security (HMAC embedding integrity)
"""
from __future__ import annotations
import hashlib
import hmac
import pytest
from app.stages.vector_security import EmbeddingHMACGuard, PoisonDetector


class TestEmbeddingHMACGuard:
    """HMAC-SHA256 embedding signature tests."""

    KEY = "test_secret_key_32_chars_minimum!"

    def setup_method(self):
        self.guard = EmbeddingHMACGuard(secret_key=self.KEY)

    def test_sign_returns_hex_string(self):
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        signature = self.guard.sign(vector)
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA-256 hex

    def test_valid_signature_passes_verification(self):
        vector = [0.1, 0.2, 0.3, 0.9, 0.7]
        sig = self.guard.sign(vector)
        assert self.guard.verify(vector, sig) is True

    def test_tampered_vector_fails_verification(self):
        vector = [0.1, 0.2, 0.3, 0.9, 0.7]
        sig = self.guard.sign(vector)
        # Tamper: change one value
        tampered = [0.1, 0.2, 0.3, 0.9, 0.8]
        assert self.guard.verify(tampered, sig) is False

    def test_wrong_key_fails_verification(self):
        vector = [0.5, 0.5, 0.5]
        guard_a = EmbeddingHMACGuard(secret_key="key_A_32_chars_minimum_here_!!")
        guard_b = EmbeddingHMACGuard(secret_key="key_B_32_chars_minimum_here_!!")
        sig = guard_a.sign(vector)
        assert guard_b.verify(vector, sig) is False

    def test_empty_vector_handled(self):
        vector: list[float] = []
        sig = self.guard.sign(vector)
        assert self.guard.verify(vector, sig) is True

    def test_large_vector_handled(self):
        import random
        vector = [random.random() for _ in range(768)]  # Qwen3-Embedding-0.6B dim
        sig = self.guard.sign(vector)
        assert self.guard.verify(vector, sig) is True

    def test_signature_is_deterministic(self):
        vector = [0.42, 0.13, 0.88]
        assert self.guard.sign(vector) == self.guard.sign(vector)

    def test_different_vectors_different_signatures(self):
        v1 = [0.1, 0.2, 0.3]
        v2 = [0.1, 0.2, 0.4]
        assert self.guard.sign(v1) != self.guard.sign(v2)


class TestPoisonDetector:
    """RAG poisoning detection via statistical outlier analysis."""

    def setup_method(self):
        self.detector = PoisonDetector(z_score_threshold=3.0)

    def _normal_vectors(self, n: int = 50, dim: int = 64) -> list[list[float]]:
        import random
        random.seed(42)
        return [[random.gauss(0.5, 0.1) for _ in range(dim)] for _ in range(n)]

    def test_normal_vectors_pass(self):
        vectors = self._normal_vectors(50)
        results = self.detector.scan(vectors)
        outlier_count = sum(1 for r in results if r["is_outlier"])
        # At most 5% outliers in a normal distribution at 3-sigma
        assert outlier_count / len(results) < 0.10

    def test_extreme_outlier_detected(self):
        import random
        random.seed(42)
        vectors = self._normal_vectors(49)
        # Inject one extreme outlier
        poison = [100.0] * 64
        vectors.append(poison)
        results = self.detector.scan(vectors)
        # The last vector (the poison) should be flagged
        assert results[-1]["is_outlier"] is True

    def test_outlier_has_z_score(self):
        vectors = self._normal_vectors(49)
        vectors.append([100.0] * 64)
        results = self.detector.scan(vectors)
        for r in results:
            assert "z_score" in r
            assert isinstance(r["z_score"], float)

    def test_scan_result_count_matches_input(self):
        vectors = self._normal_vectors(30)
        results = self.detector.scan(vectors)
        assert len(results) == 30
