"""
Unit Tests — Honeypot Integrity System
"""
from __future__ import annotations
import pytest
from app.security.honeypot import HoneypotManager, HONEYPOT_PREFIX


class TestHoneypotManager:
    mgr = HoneypotManager(secret_key="test_secret_change_in_prod")

    def test_inject_adds_honeypots(self, clean_candidates):
        pool = self.mgr.inject(clean_candidates, jd_id="jd_001")
        assert len(pool) == len(clean_candidates) + 3  # 3 honeypot templates

    def test_honeypots_have_prefix_ids(self, clean_candidates):
        pool = self.mgr.inject(clean_candidates, jd_id="jd_001")
        hp_ids = [c["id"] for c in pool if c.get("_is_honeypot")]
        assert len(hp_ids) == 3
        assert all(hid.startswith(HONEYPOT_PREFIX) for hid in hp_ids)

    def test_same_jd_same_honeypot_ids(self, clean_candidates):
        """Honeypot IDs are deterministic per JD."""
        pool_a = self.mgr.inject(clean_candidates[:], jd_id="jd_deterministic")
        pool_b = self.mgr.inject(clean_candidates[:], jd_id="jd_deterministic")
        ids_a = sorted(c["id"] for c in pool_a if c.get("_is_honeypot"))
        ids_b = sorted(c["id"] for c in pool_b if c.get("_is_honeypot"))
        assert ids_a == ids_b

    def test_different_jd_different_honeypot_ids(self, clean_candidates):
        pool_a = self.mgr.inject(clean_candidates[:], jd_id="jd_A")
        pool_b = self.mgr.inject(clean_candidates[:], jd_id="jd_B")
        ids_a = {c["id"] for c in pool_a if c.get("_is_honeypot")}
        ids_b = {c["id"] for c in pool_b if c.get("_is_honeypot")}
        assert ids_a.isdisjoint(ids_b)

    def test_check_clean_ranking_is_intact(self, clean_candidates):
        """If honeypots rank at the bottom (after real candidates), system is intact."""
        pool = self.mgr.inject(clean_candidates, jd_id="jd_001")
        # Simulate ranking: real candidates first, honeypots last
        ranked = sorted(pool, key=lambda c: 0 if not c.get("_is_honeypot") else 1)
        result = self.mgr.check(ranked, jd_id="jd_001")
        assert result.is_intact is True
        assert result.alert_level == "none"

    def test_check_detects_honeypot_in_top_20(self, clean_candidates):
        """If a honeypot appears in top-20, it's a critical violation."""
        pool = self.mgr.inject(clean_candidates, jd_id="jd_001")
        # Simulate compromised ranking: honeypots placed at rank 1, 2, 3
        honeypots = [c for c in pool if c.get("_is_honeypot")]
        real      = [c for c in pool if not c.get("_is_honeypot")]
        ranked    = honeypots + real  # honeypots on top!
        result    = self.mgr.check(ranked, jd_id="jd_001")
        assert result.is_intact is False
        assert result.alert_level == "critical"
        assert result.honeypots_in_top_20 > 0

    def test_remove_strips_honeypots(self, clean_candidates):
        pool   = self.mgr.inject(clean_candidates, jd_id="jd_001")
        ranked = sorted(pool, key=lambda c: 0 if not c.get("_is_honeypot") else 1)
        final  = self.mgr.remove(ranked)
        assert len(final) == len(clean_candidates)
        assert not any(c.get("_is_honeypot") for c in final)
        assert not any(c["id"].startswith(HONEYPOT_PREFIX) for c in final)
