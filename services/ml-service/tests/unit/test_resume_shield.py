"""
Unit Tests — ResumeShield™ (6 detectors)
"""
from __future__ import annotations
import pytest
from app.stages.resume_shield import ResumeShieldEngine


class TestResumeShieldDetectors:
    engine = ResumeShieldEngine()

    # ── D1: LLM Generation Detection ─────────────────────────────────────────
    def test_clean_resume_passes(self, candidate):
        result = self.engine.analyze(candidate)
        assert result["fraud_label"] == "clean"
        assert result["fraud_risk_score"] < 0.4

    def test_ai_generated_resume_flagged(self):
        """A resume with extremely uniform sentence lengths (low burstiness) is likely LLM-written."""
        candidate = {
            "id": "ai_001",
            "summary": (
                "I am a skilled engineer. I work on many projects. I build good systems. "
                "I have strong skills. I deliver good code. I learn new things. "
                "I solve hard problems. I work in teams. I use best practices. I write tests."
            ),
            "skills": ["python", "java", "react", "node", "docker", "kubernetes"],
            "years_experience": 5,
            "title_history": [
                {"company": "Google", "start_year": 2018, "end_year": 2024, "role": "SWE"},
            ],
        }
        result = self.engine.analyze(candidate)
        assert result["fraud_risk_score"] > 0.3

    # ── D2: JD Mirroring Detection ────────────────────────────────────────────
    def test_jd_mirroring_flagged(self):
        """Candidate summary that exactly mirrors the JD should be flagged."""
        jd_skills = ["python", "fastapi", "postgresql", "docker", "kubernetes", "redis", "kafka"]
        candidate = {
            "id": "mirror_001",
            "summary": "Expert in python fastapi postgresql docker kubernetes redis kafka.",
            "skills": jd_skills,
            "years_experience": 5,
            "title_history": [],
        }
        result = self.engine.analyze(candidate, jd_skills=jd_skills)
        # High overlap should increase risk
        assert result["fraud_risk_score"] > 0.2

    # ── D3: Timeline Impossibility ────────────────────────────────────────────
    def test_overlapping_jobs_flagged(self):
        """Two full-time jobs at the same time is physically impossible."""
        candidate = {
            "id": "overlap_001",
            "summary": "Experienced engineer.",
            "skills": ["python"],
            "years_experience": 6,
            "title_history": [
                {"company": "Infosys",   "start_year": 2018, "end_year": 2022, "role": "SDE"},
                {"company": "Wipro",     "start_year": 2019, "end_year": 2023, "role": "SDE"},  # overlap!
                {"company": "Razorpay",  "start_year": 2023, "end_year": 2024, "role": "SDE"},
            ],
        }
        result = self.engine.analyze(candidate)
        assert result["fraud_risk_score"] > 0.3

    def test_clean_timeline_passes(self, candidate):
        result = self.engine.analyze(candidate)
        # Infosys 2019-2022, Razorpay 2022-2024 — no overlap
        assert result.get("timeline_flag", False) is False

    # ── D4: Skill Credibility ─────────────────────────────────────────────────
    def test_too_many_skills_flags_risk(self):
        """40+ diverse skills with 2 years experience is implausible."""
        candidate = {
            "id": "skill_001",
            "summary": "I know everything.",
            "skills": [
                "python", "java", "c++", "rust", "go", "ruby", "php", "swift", "kotlin",
                "react", "angular", "vue", "svelte", "next", "nuxt",
                "postgres", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
                "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
                "spark", "kafka", "flink", "airflow", "dbt", "mlflow", "pytorch", "tensorflow",
            ],
            "years_experience": 2,
            "title_history": [],
        }
        result = self.engine.analyze(candidate)
        assert result["fraud_risk_score"] > 0.4

    # ── Batch analysis ────────────────────────────────────────────────────────
    def test_batch_analyze_returns_all_candidates(self, clean_candidates):
        results = self.engine.analyze_batch(clean_candidates)
        assert len(results) == len(clean_candidates)
        for r in results:
            assert "fraud_risk_score" in r
            assert "fraud_label" in r

    def test_blocked_candidate_gets_penalized_score(self, fraud_candidate):
        """A known-bad candidate should have a high fraud risk score."""
        assert fraud_candidate["fraud_risk_score"] >= 0.9
        assert fraud_candidate["fraud_label"] == "blocked"

    # ── Score bounds ──────────────────────────────────────────────────────────
    def test_fraud_score_in_valid_range(self, clean_candidates):
        for c in clean_candidates:
            result = self.engine.analyze(c)
            assert 0.0 <= result["fraud_risk_score"] <= 1.0

    def test_fraud_label_one_of_valid_values(self, clean_candidates):
        valid_labels = {"clean", "suspicious", "high_risk", "blocked"}
        for c in clean_candidates:
            result = self.engine.analyze(c)
            assert result["fraud_label"] in valid_labels
