"""
Unit Tests — DPDP Compliance Layer
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.stages.dpdp_layer import (
    ConsentLedger,
    DataMinimizationValidator,
    AlgorithmicTransparencyLog,
)


class TestConsentLedger:
    """§5 DPDP Act — Consent before processing."""

    def test_consent_record_has_required_fields(self):
        ledger = ConsentLedger()
        record = ledger.create_record(
            candidate_id="c001",
            purpose="job_matching",
            data_categories=["resume", "contact_info"],
        )
        assert record["candidate_id"] == "c001"
        assert record["purpose"] == "job_matching"
        assert record["status"] == "active"
        assert "granted_at" in record
        assert "expiry_at" in record

    def test_consent_expiry_is_in_future(self):
        from datetime import datetime, timezone
        ledger = ConsentLedger()
        record = ledger.create_record("c001", "job_matching", ["resume"])
        expiry = datetime.fromisoformat(record["expiry_at"])
        now    = datetime.now(timezone.utc)
        assert expiry > now

    def test_revoked_consent_is_marked_inactive(self):
        ledger = ConsentLedger()
        record = ledger.create_record("c002", "job_matching", ["resume"])
        revoked = ledger.revoke(record["consent_id"])
        assert revoked["status"] == "revoked"
        assert "revoked_at" in revoked

    def test_consent_is_serializable_to_dict(self):
        ledger = ConsentLedger()
        record = ledger.create_record("c003", "job_matching", ["resume"])
        import json
        json.dumps(record)  # Must not raise


class TestDataMinimizationValidator:
    """§8 DPDP Act — JD must not request protected attributes."""

    validator = DataMinimizationValidator()

    @pytest.mark.parametrize("protected_jd", [
        "We are looking for a male engineer aged 25-30",
        "Candidate must be Hindu and from North India",
        "Looking for married candidates only",
        "Must have Indian passport — no foreigners",
        "Prefer candidates with no disability",
    ])
    def test_protected_attribute_jd_flagged(self, protected_jd):
        result = self.validator.validate(protected_jd)
        assert result["contains_protected_attributes"] is True
        assert len(result["violations"]) > 0

    def test_compliant_jd_passes(self, jd_text):
        result = self.validator.validate(jd_text)
        assert result["contains_protected_attributes"] is False
        assert result["violations"] == []

    def test_violation_includes_category(self, ):
        jd = "We prefer male candidates aged 25-35 for this role."
        result = self.validator.validate(jd)
        categories = [v["category"] for v in result["violations"]]
        assert "gender" in categories or "age" in categories


class TestAlgorithmicTransparencyLog:
    """§12 DPDP Act — Candidates can request algorithm explanation."""

    def test_log_entry_has_required_fields(self):
        log = AlgorithmicTransparencyLog()
        entry = log.record(
            candidate_id="c001",
            jd_id="jd_abc",
            rank=3,
            fusion_score=0.82,
            feature_contributions={"embedding_similarity": 0.30, "trust_score": 0.20},
        )
        assert entry["candidate_id"] == "c001"
        assert entry["jd_id"] == "jd_abc"
        assert entry["rank"] == 3
        assert "algorithm_version" in entry
        assert "timestamp" in entry

    def test_transparency_report_is_human_readable(self):
        log = AlgorithmicTransparencyLog()
        entry = log.record(
            candidate_id="c001",
            jd_id="jd_abc",
            rank=3,
            fusion_score=0.82,
            feature_contributions={"embedding_similarity": 0.30, "skill_overlap_ratio": 0.25},
        )
        report = log.generate_report(entry)
        assert isinstance(report, str)
        assert len(report) > 50
        # Should mention the candidate and rank
        assert "c001" in report or "rank" in report.lower()
