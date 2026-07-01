#!/usr/bin/env python3
"""Generate mini candidate pool and run rank.py smoke test."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Matches tests/conftest.py sample_candidate (YoE must align with career_history sum)
BASE_CANDIDATE = {
    "candidate_id": "CAND_0000001",
    "profile": {
        "anonymized_name": "Test Candidate",
        "headline": "ML Engineer",
        "summary": "Built production retrieval systems using embeddings and FAISS.",
        "location": "Pune",
        "country": "India",
        "years_of_experience": 4.0,
        "current_title": "Machine Learning Engineer",
        "current_company": "Acme",
        "current_company_size": "201-500",
        "current_industry": "Technology",
    },
    "career_history": [{
        "company": "Acme",
        "title": "Machine Learning Engineer",
        "start_date": "2021-01-01",
        "end_date": None,
        "duration_months": 48,
        "is_current": True,
        "industry": "Technology",
        "company_size": "201-500",
        "description": "Built and operated a production vector search retrieval system using FAISS, serving 2M users.",
    }],
    "education": [{
        "institution": "IIT Bombay",
        "degree": "B.Tech",
        "field_of_study": "CS",
        "start_year": 2014,
        "end_year": 2018,
        "grade": "8.5",
        "tier": "tier_1",
    }],
    "skills": [
        {"name": "Python", "proficiency": "expert", "endorsements": 20, "duration_months": 72},
        {"name": "FAISS", "proficiency": "advanced", "endorsements": 10, "duration_months": 36},
    ],
    "redrob_signals": {
        "profile_completeness_score": 90,
        "signup_date": "2022-01-01",
        "last_active_date": "2026-06-25",
        "open_to_work_flag": True,
        "profile_views_received_30d": 40,
        "applications_submitted_30d": 3,
        "recruiter_response_rate": 0.8,
        "avg_response_time_hours": 10,
        "skill_assessment_scores": {"Python": 95},
        "connection_count": 300,
        "endorsements_received": 30,
        "notice_period_days": 20,
        "expected_salary_range_inr_lpa": {"min": 30, "max": 45},
        "preferred_work_mode": "hybrid",
        "willing_to_relocate": True,
        "github_activity_score": 60,
        "search_appearance_30d": 50,
        "saved_by_recruiters_30d": 5,
        "interview_completion_rate": 0.9,
        "offer_acceptance_rate": 1.0,
        "verified_email": True,
        "verified_phone": True,
        "linkedin_connected": True,
    },
}


if __name__ == "__main__":
    rows = []
    for i in range(150):
        c = json.loads(json.dumps(BASE_CANDIDATE))
        c["candidate_id"] = f"CAND_{i:07d}"
        rows.append(c)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pool = tmp_path / "mini_pool.jsonl"
        out_csv = tmp_path / "sub.csv"
        with pool.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        subprocess.run(
            [sys.executable, "rank.py", "--candidates", str(pool), "--out", str(out_csv)],
            check=True,
            cwd=ROOT,
        )
        subprocess.run(
            [sys.executable, "validate_submission.py", str(out_csv), str(pool)],
            check=True,
            cwd=ROOT,
        )
    print("Smoke test passed")
