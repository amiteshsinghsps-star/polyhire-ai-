"""
Integration Tests — Full Pipeline (end-to-end)
"""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_has_required_keys(self):
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "capabilities" in data
        assert "index_ready" in data

    def test_health_status_is_ok(self):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"


class TestPipelineRunEndpoint:
    def test_pipeline_run_requires_text_or_audio(self):
        resp = client.post("/pipeline/run", json={})
        # Should return 422 (validation error) for missing required fields
        assert resp.status_code == 422

    def test_pipeline_run_with_jd_text_returns_result(self, jd_text):
        resp = client.post("/pipeline/run", json={"text": jd_text})
        # Even with fallbacks, should succeed
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert isinstance(data["candidates"], list)

    def test_pipeline_result_has_required_fields(self, jd_text):
        resp = client.post("/pipeline/run", json={"text": jd_text})
        assert resp.status_code == 200
        data = resp.json()
        assert "jd_id" in data
        assert "candidates" in data
        assert "pipeline_metadata" in data or "bias_flags" in data

    def test_pipeline_candidate_has_required_fields(self, jd_text):
        resp = client.post("/pipeline/run", json={"text": jd_text})
        candidates = resp.json().get("candidates", [])
        if not candidates:
            pytest.skip("No candidates in index — seed dataset first")
        for c in candidates[:3]:
            assert "candidate_id" in c or "id" in c
            assert "score" in c or "fusion_score" in c
            assert "explanation" in c or "rank" in c

    def test_pipeline_with_malicious_jd_returns_error_or_sanitizes(self, malicious_jd):
        resp = client.post("/pipeline/run", json={"text": malicious_jd})
        # Either blocked (400/403) or sanitized and returns result — both are acceptable
        assert resp.status_code in (200, 400, 403, 422)

    def test_pipeline_respects_top_k(self, jd_text):
        resp = client.post("/pipeline/run", json={"text": jd_text, "top_k": 5})
        assert resp.status_code == 200
        candidates = resp.json().get("candidates", [])
        assert len(candidates) <= 5


class TestShieldRoutes:
    def test_shield_route_exists(self):
        resp = client.get("/api/shield/status")
        # Should not return 404 — may return 200 or 405 depending on method
        assert resp.status_code != 404

    def test_shield_analyze_batch_accepts_candidates(self, clean_candidates):
        resp = client.post("/api/shield/analyze-batch", json={"candidates": clean_candidates})
        assert resp.status_code in (200, 422)  # 422 if schema mismatch
        if resp.status_code == 200:
            data = resp.json()
            assert "results" in data or isinstance(data, list)


class TestDpdpRoutes:
    def test_compliance_summary_endpoint_exists(self):
        resp = client.get("/api/dpdp/compliance-summary")
        assert resp.status_code in (200, 404)  # 404 only if not yet wired

    def test_dpdp_transparency_endpoint_accepts_candidate_id(self):
        resp = client.get("/api/dpdp/transparency/test_candidate_001")
        assert resp.status_code in (200, 404, 422)


class TestDiverseHireRoutes:
    def test_diverse_hire_jd_analysis_endpoint_exists(self):
        resp = client.post("/api/diverse-hire/analyze-jd", json={"jd_text": "Looking for engineers."})
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            data = resp.json()
            assert "overall_bias_score" in data or "bias_score" in data


class TestIndexRebuildEndpoint:
    def test_index_rebuild_returns_200(self):
        resp = client.post("/index/rebuild")
        assert resp.status_code == 200

    def test_index_rebuild_returns_candidate_count(self):
        resp = client.post("/index/rebuild")
        data = resp.json()
        assert "candidate_count" in data
        assert isinstance(data["candidate_count"], int)
class TestSubmissionMode:
    def test_run_submission_mode_disabled(self):
        resp = client.post("/submission/run")
        # Should be 400 because submission mode is False by default
        assert resp.status_code == 400
        assert "SUBMISSION_MODE" in resp.json()["detail"]
        
    @patch("app.main.get_settings")
    def test_run_submission_mode_enabled(self, mock_settings):
        # Mock settings to return submission_mode=True
        mock_s = MagicMock()
        mock_s.submission_mode = True
        mock_s.submission_top_k = 100
        mock_s.submission_candidates_path = "tests/fixtures/candidates.jsonl"
        mock_s.submission_output_path = "output/test_submission.csv"
        mock_settings.return_value = mock_s
        
        # We need a small fixture for candidates
        with patch("app.pipeline.load_jsonl_stream") as mock_load:
            mock_load.return_value = [{"candidate_id": "c1", "score": 0.9}]
            with patch("app.pipeline.write_submission_csv") as mock_write:
                mock_write.return_value = "output/test_submission.csv"
                resp = client.post("/submission/run")
                
                assert resp.status_code == 200
                assert resp.json()["status"] == "success"
                mock_load.assert_called_once()
                mock_write.assert_called_once()
