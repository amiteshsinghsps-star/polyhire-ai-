import pytest
from app.stages.submission_ranker import SubmissionRanker


def test_submission_ranker_basic():
    ranker = SubmissionRanker()
    
    cand = {
        "candidate_id": "c1",
        "profile": {
            "current_title": "Senior AI Engineer",
            "years_of_experience": 6.0,
            "location": "Pune",
            "country": "India",
            "summary": "AI expert"
        },
        "career_history": [
            {
                "title": "AI Engineer",
                "company": "Tech Corp",
                "start_date": "2020-01-01",
                "end_date": "2024-01-01",
                "duration_months": 48,
                "description": "Shipped embeddings to production."
            }
        ],
        "skills": [{"name": "embeddings", "endorsements": 10, "duration_months": 24, "proficiency": "expert"}],
        "education": [],
        "redrob_signals": {}
    }
    
    res = ranker.score_candidate(cand)
    assert res["candidate_id"] == "c1"
    assert res["score"] > 0
    assert not res["is_honeypot"]


def test_submission_ranker_honeypot():
    ranker = SubmissionRanker()
    
    cand = {
        "candidate_id": "c_trap",
        "profile": {
            "current_title": "HR Manager",
            "years_of_experience": 2.0,
            "location": "Pune",
            "country": "India",
            "summary": "I know embeddings, vector search, rag, qdrant, faiss, ltr, ndcg, llm fine-tuning."
        },
        "career_history": [],
        "skills": [
            {"name": "embeddings", "endorsements": 0, "duration_months": 0, "proficiency": "expert"},
            {"name": "qdrant", "endorsements": 0, "duration_months": 0, "proficiency": "expert"},
            {"name": "faiss", "endorsements": 0, "duration_months": 0, "proficiency": "expert"},
            {"name": "rag", "endorsements": 0, "duration_months": 0, "proficiency": "expert"},
            {"name": "ltr", "endorsements": 0, "duration_months": 0, "proficiency": "expert"}
        ],
        "education": [],
        "redrob_signals": {}
    }
    
    res = ranker.score_candidate(cand)
    assert res["candidate_id"] == "c_trap"
    assert res["is_honeypot"]
    assert res["score"] <= 0.05
