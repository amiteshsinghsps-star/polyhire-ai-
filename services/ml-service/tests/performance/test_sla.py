"""
Performance / SLA Benchmark Tests
===================================
SLA targets (from PRD v3.0):
  - Stage 1 (JD Parse):      < 2s
  - Stage 2 (Embedding):     < 500ms
  - Stage 4 (Retrieval):     < 300ms  (Qdrant with fallback to FAISS)
  - Stage 5 (Rerank):        < 2s     (top-30 candidates)
  - Stage 6 (Shield):        < 100ms  (heuristics only)
  - Full pipeline (E2E):     < 10s    (fallback mode, no LLM)

Run: pytest tests/performance/ -v -s
"""
from __future__ import annotations
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.stages.resume_shield import ResumeShieldEngine
from app.stages.diverse_hire import JDCleaner, DiversityScoreCalculator
from app.security.prompt_guard import PromptInjectionSanitizer
from app.security.honeypot import HoneypotManager
from tests.conftest import make_candidate


client = TestClient(app)


def _elapsed(fn, *args, **kwargs) -> tuple[float, object]:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return time.perf_counter() - t0, result


# ── Stage-level SLAs ────────────────────────────────────────────────────────

class TestPromptGuardSLA:
    guard = PromptInjectionSanitizer()

    def test_sanitize_under_10ms(self, jd_text):
        elapsed, _ = _elapsed(self.guard.sanitize, jd_text)
        assert elapsed < 0.010, f"PromptGuard too slow: {elapsed:.3f}s (SLA <10ms)"

    def test_sanitize_large_input_under_50ms(self):
        large_text = "Python developer with experience. " * 300
        elapsed, _ = _elapsed(self.guard.sanitize, large_text)
        assert elapsed < 0.050, f"PromptGuard large input too slow: {elapsed:.3f}s (SLA <50ms)"


class TestResumeShieldSLA:
    engine = ResumeShieldEngine()
    candidates = [make_candidate(f"c{i}") for i in range(50)]

    def test_single_candidate_under_5ms(self, candidate):
        elapsed, _ = _elapsed(self.engine.analyze, candidate)
        assert elapsed < 0.005, f"ResumeShield single too slow: {elapsed:.3f}s (SLA <5ms)"

    def test_batch_50_candidates_under_200ms(self):
        elapsed, _ = _elapsed(self.engine.analyze_batch, self.candidates)
        assert elapsed < 0.200, f"ResumeShield batch-50 too slow: {elapsed:.3f}s (SLA <200ms)"


class TestDiverseHireSLA:
    analyzer = JDCleaner()
    scorer   = DiversityScoreCalculator()

    def test_jd_analysis_under_10ms(self, jd_text):
        elapsed, _ = _elapsed(self.analyzer.clean, jd_text)
        assert elapsed < 0.010, f"JDCleaner too slow: {elapsed:.3f}s (SLA <10ms)"

    def test_diversity_score_50_candidates_under_20ms(self):
        candidates = [make_candidate(f"c{i}", city=f"City{i}") for i in range(50)]
        elapsed, _ = _elapsed(self.scorer.score_pool, candidates)
        assert elapsed < 0.020, f"DiversityScoreCalculator too slow: {elapsed:.3f}s (SLA <20ms)"


class TestHoneypotSLA:
    mgr = HoneypotManager()

    def test_inject_50_candidates_under_5ms(self):
        candidates = [make_candidate(f"c{i}") for i in range(50)]
        elapsed, _ = _elapsed(self.mgr.inject, candidates, jd_id="jd_perf")
        assert elapsed < 0.005, f"Honeypot inject too slow: {elapsed:.3f}s (SLA <5ms)"

    def test_check_50_candidates_under_5ms(self):
        candidates = [make_candidate(f"c{i}") for i in range(50)]
        pool   = self.mgr.inject(candidates, jd_id="jd_perf")
        elapsed, _ = _elapsed(self.mgr.check, pool, jd_id="jd_perf")
        assert elapsed < 0.005, f"Honeypot check too slow: {elapsed:.3f}s (SLA <5ms)"


# ── End-to-end SLA ──────────────────────────────────────────────────────────

class TestEndToEndSLA:
    def test_pipeline_run_under_10s_fallback_mode(self, jd_text):
        """Full pipeline with all fallbacks active must complete within 10 seconds."""
        elapsed, resp = _elapsed(client.post, "/pipeline/run", json={"text": jd_text})
        assert resp.status_code == 200, f"Pipeline failed: {resp.text}"
        assert elapsed < 10.0, f"Full pipeline too slow: {elapsed:.2f}s (SLA <10s)"


class TestSubmissionSLA:
    def test_submission_ranker_under_3ms_per_candidate(self):
        from app.stages.submission_ranker import SubmissionRanker
        ranker = SubmissionRanker()
        cands = [make_candidate(f"c{i}") for i in range(1000)]
        
        # Redrob schema is slightly different, but the ranker handles both gracefully or falls back
        # Let's map it quickly
        mapped = [{"candidate_id": c["id"], "profile": {"summary": c.get("summary", "")}} for c in cands]
        
        t0 = time.perf_counter()
        for c in mapped:
            ranker.score_candidate(c)
        elapsed = time.perf_counter() - t0
        
        avg_ms = (elapsed / 1000) * 1000
        # For 100K candidates in 5 mins (300s) -> 3ms max per candidate
        assert avg_ms < 3.0, f"SubmissionRanker too slow: {avg_ms:.2f}ms per candidate (SLA <3ms)"

    def test_index_rebuild_under_5s(self):
        elapsed, resp = _elapsed(client.post, "/index/rebuild")
        assert resp.status_code == 200
        assert elapsed < 5.0, f"Index rebuild too slow: {elapsed:.2f}s (SLA <5s)"
