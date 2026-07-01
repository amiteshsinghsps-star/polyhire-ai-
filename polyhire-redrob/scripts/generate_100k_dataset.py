#!/usr/bin/env python3
"""
generate_100k_dataset.py — Synthesises a realistic 100,000-candidate dataset
for PolyHire Redrob Track 1.

Run from polyhire-redrob/:
    python scripts/generate_100k_dataset.py --out data/candidates.jsonl

Design
------
Candidates are drawn from 8 persona archetypes modelled on the JD:
  A. Strong match   (ML engineer, vector search, Pune/Noida, 5-9 YoE)
  B. Good match     (ML/AI title, embeddings experience, Tier-1 cities)
  C. Adjacent match (Data scientist, NLP, good YoE)
  D. Weak match     (Backend engineer with some ML)
  E. Near-miss      (Research, good skills but pure academia)
  F. Consultant     (TCS/Infosys background, some ML buzzwords)
  G. Leadership     (Tech lead / manager with historical ML)
  H. Honeypot       (Planted fabricated/impossible profiles for detector)

Percentages: A=3%, B=7%, C=15%, D=30%, E=15%, F=15%, G=10%, H=5%
Total: 100,000 candidates with realistic redrob_signals, career_history, etc.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# ─── Helpers ─────────────────────────────────────────────────────────────────

_COMPANIES_TIER1 = [
    "Google", "Meta", "Microsoft", "Amazon", "Apple", "Netflix",
    "OpenAI", "Anthropic", "Flipkart", "Swiggy", "Zomato",
    "PhonePe", "Razorpay", "Groww", "CRED", "Meesho", "Juspay",
]
_COMPANIES_TIER2 = [
    "Infosys", "TCS", "Wipro", "HCL", "Accenture", "Cognizant",
    "Capgemini", "Tech Mahindra", "Mphasis", "L&T Infotech",
]
_COMPANIES_STARTUP = [
    "Recur Club", "Vyapar", "Fampay", "Slice", "Unacademy",
    "BharatPe", "Lenskart", "Nykaa", "Delhivery", "Ather Energy",
    "Postman", "HashedIn", "ThoughtWorks", "Sigmoid", "Scaler",
]

_LOCATIONS_TIER1 = ["Pune", "Noida"]
_LOCATIONS_TIER2 = ["Bengaluru", "Hyderabad", "Mumbai", "Gurgaon", "Delhi", "Chennai"]
_LOCATIONS_TIER3 = ["Ahmedabad", "Kolkata", "Jaipur", "Indore", "Coimbatore", "Kochi"]

_SKILLS_STRONG = [
    "Python", "FAISS", "Elasticsearch", "vector search", "transformers",
    "scikit-learn", "PyTorch", "sentence-transformers", "LangChain",
    "ranking systems", "recommendation systems", "embeddings",
    "NDCG", "A/B testing", "Spark", "Kafka",
]
_SKILLS_WEAK = [
    "Excel", "SQL", "Tableau", "PowerPoint", "Java", "C#", "PHP",
    "WordPress", "Selenium", "Manual Testing", "SAP",
]

_TITLES_ML = [
    "Machine Learning Engineer", "Applied Scientist", "AI Engineer",
    "Research Engineer", "NLP Engineer", "Search Engineer",
    "Ranking Engineer", "Data Scientist", "ML Platform Engineer",
]
_TITLES_ADJACENT = [
    "Backend Engineer", "Data Engineer", "Software Engineer",
    "Platform Engineer", "Analytics Engineer",
]
_TITLES_LEADERSHIP = [
    "Tech Lead", "Engineering Manager", "Principal Engineer",
    "Staff Engineer", "Director of Engineering", "Head of ML",
]
_TITLES_CONSULTING = [
    "Senior Consultant", "Associate Consultant", "IT Analyst",
    "System Engineer", "Module Lead", "Project Manager",
]

_INSTITUTIONS_TIER1 = [
    "IIT Bombay", "IIT Delhi", "IIT Madras", "IIT Kanpur",
    "IISc Bangalore", "BITS Pilani",
]
_INSTITUTIONS_TIER2 = [
    "NIT Trichy", "NIT Warangal", "NIT Surathkal", "IIIT Hyderabad",
    "NIT Calicut", "VIT Vellore",
]
_INSTITUTIONS_TIER3 = [
    "Pune University", "Mumbai University", "Anna University",
    "Osmania University", "Jadavpur University",
]


def _rand_date(rng: random.Random, start_year: int, end_year: int) -> str:
    d = date(start_year, 1, 1) + timedelta(days=rng.randint(0, (end_year - start_year) * 365))
    return d.strftime("%Y-%m-%d")


def _rand_yoe_from_start(rng: random.Random, start_year: int, ref_year: int = 2026) -> float:
    return max(0.5, round(ref_year - start_year + rng.uniform(-0.5, 0.5), 1))


def _skills_block(rng: random.Random, strong_n: int = 3, weak_n: int = 1) -> list[dict]:
    skills = []
    chosen_strong = rng.sample(_SKILLS_STRONG, min(strong_n, len(_SKILLS_STRONG)))
    for s in chosen_strong:
        skills.append({
            "name": s,
            "proficiency": rng.choice(["expert", "advanced"]),
            "endorsements": rng.randint(5, 40),
            "duration_months": rng.randint(18, 84),
        })
    chosen_weak = rng.sample(_SKILLS_WEAK, min(weak_n, len(_SKILLS_WEAK)))
    for s in chosen_weak:
        skills.append({
            "name": s,
            "proficiency": rng.choice(["intermediate", "beginner"]),
            "endorsements": rng.randint(0, 5),
            "duration_months": rng.randint(6, 36),
        })
    return skills


def _career_block(rng: random.Random, titles: list[str], companies: list[str],
                  n_roles: int = 2, start_year: int = 2018) -> tuple[list[dict], float]:
    roles = []
    current_year = start_year
    for i in range(n_roles):
        duration = rng.randint(12, 48)
        end_year_float = current_year + duration / 12
        is_current = (i == n_roles - 1)
        roles.append({
            "company": rng.choice(companies),
            "title": rng.choice(titles),
            "start_date": f"{current_year}-{rng.randint(1,12):02d}-01",
            "end_date": None if is_current else f"{int(end_year_float)}-{rng.randint(1,12):02d}-01",
            "duration_months": duration,
            "is_current": is_current,
            "industry": "Technology",
            "company_size": rng.choice(["51-200", "201-500", "501-1000", "1001-5000"]),
            "description": rng.choice([
                "Built and operated a production embeddings-based retrieval system at scale.",
                "Designed and deployed recommendation engine using FAISS and transformers.",
                "Developed vector search infrastructure handling millions of queries per day.",
                "Led offline evaluation framework using NDCG, MRR and A/B testing.",
                "Implemented hybrid sparse-dense retrieval pipeline using BM25 and DPR.",
                "Maintained large-scale data pipelines for ranking model feature store.",
                "Built ML model serving infrastructure with <50ms p99 latency.",
                "Developed NLP models for information extraction and semantic search.",
            ])
        })
        current_year = int(end_year_float) + (0 if is_current else 0)
        current_year += rng.randint(0, 1)

    total_months = sum(r["duration_months"] for r in roles)
    return roles, total_months / 12.0


def _edu_block(rng: random.Random, institution_pool: list[str]) -> list[dict]:
    start = rng.randint(2010, 2018)
    end = start + rng.choice([3, 4])
    return [{
        "institution": rng.choice(institution_pool),
        "degree": rng.choice(["B.Tech", "M.Tech", "M.S.", "B.E."]),
        "field_of_study": rng.choice(["Computer Science", "Electronics", "Information Technology"]),
        "start_year": start,
        "end_year": end,
        "grade": str(round(rng.uniform(6.5, 9.5), 1)),
        "tier": (
            "tier_1" if institution_pool is _INSTITUTIONS_TIER1
            else "tier_2" if institution_pool is _INSTITUTIONS_TIER2
            else "tier_3"
        ),
    }]


def _signals_block(rng: random.Random, active: bool = True, high_engagement: bool = False) -> dict:
    return {
        "profile_completeness_score": rng.randint(60, 100),
        "signup_date": _rand_date(rng, 2020, 2024),
        "last_active_date": (
            _rand_date(rng, 2026, 2026) if active
            else _rand_date(rng, 2024, 2025)
        ),
        "open_to_work_flag": rng.random() > (0.2 if active else 0.5),
        "profile_views_received_30d": rng.randint(50, 300) if high_engagement else rng.randint(0, 80),
        "applications_submitted_30d": rng.randint(2, 15),
        "recruiter_response_rate": round(rng.uniform(0.4, 1.0), 2),
        "avg_response_time_hours": rng.randint(2, 72),
        "skill_assessment_scores": {"Python": rng.randint(60, 99)},
        "connection_count": rng.randint(100, 800),
        "endorsements_received": rng.randint(10, 100),
        "notice_period_days": rng.choice([0, 15, 30, 60, 90]),
        "expected_salary_range_inr_lpa": {"min": rng.randint(20, 60), "max": rng.randint(40, 100)},
        "preferred_work_mode": rng.choice(["remote", "hybrid", "onsite"]),
        "willing_to_relocate": rng.random() > 0.4,
        "github_activity_score": rng.randint(10, 90),
        "search_appearance_30d": rng.randint(10, 200),
        "saved_by_recruiters_30d": rng.randint(0, 20),
        "interview_completion_rate": round(rng.uniform(0.5, 1.0), 2),
        "offer_acceptance_rate": round(rng.uniform(0.5, 1.0), 2),
        "verified_email": rng.random() > 0.1,
        "verified_phone": rng.random() > 0.2,
        "linkedin_connected": rng.random() > 0.15,
    }


# ─── Persona factories ───────────────────────────────────────────────────────

def make_persona_A(rng: random.Random, n: int) -> dict:
    """Strong match: ML engineer, vector/IR experience, Pune/Noida, 5-9 YoE."""
    start_year = 2026 - rng.randint(5, 9)
    roles, actual_yoe = _career_block(rng, _TITLES_ML, _COMPANIES_TIER1 + _COMPANIES_STARTUP,
                                      n_roles=rng.choice([2, 3]), start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": f"ML Engineer specializing in vector search and retrieval",
            "summary": "Built production retrieval systems using FAISS, transformers, and embedding models.",
            "location": rng.choice(_LOCATIONS_TIER1),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_ML),
            "current_company": rng.choice(_COMPANIES_TIER1),
            "current_company_size": "501-1000",
            "current_industry": "Technology",
        },
        "career_history": roles,
        "education": _edu_block(rng, _INSTITUTIONS_TIER1),
        "skills": _skills_block(rng, strong_n=5, weak_n=0),
        "redrob_signals": _signals_block(rng, active=True, high_engagement=True),
    }


def make_persona_B(rng: random.Random, n: int) -> dict:
    """Good match: ML/AI title, embeddings experience, Tier-1 cities."""
    start_year = 2026 - rng.randint(4, 8)
    roles, actual_yoe = _career_block(rng, _TITLES_ML, _COMPANIES_TIER1 + _COMPANIES_STARTUP,
                                      n_roles=2, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": rng.choice(_TITLES_ML),
            "summary": "Developed and deployed ML models for search and ranking tasks.",
            "location": rng.choice(_LOCATIONS_TIER2),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_ML),
            "current_company": rng.choice(_COMPANIES_STARTUP),
            "current_company_size": "201-500",
            "current_industry": "Technology",
        },
        "career_history": roles,
        "education": _edu_block(rng, rng.choice([_INSTITUTIONS_TIER1, _INSTITUTIONS_TIER2])),
        "skills": _skills_block(rng, strong_n=4, weak_n=1),
        "redrob_signals": _signals_block(rng, active=True, high_engagement=rng.random() > 0.5),
    }


def make_persona_C(rng: random.Random, n: int) -> dict:
    """Adjacent match: Data scientist, NLP experience."""
    start_year = 2026 - rng.randint(4, 9)
    roles, actual_yoe = _career_block(rng, _TITLES_ADJACENT, _COMPANIES_STARTUP + _COMPANIES_TIER2,
                                      n_roles=2, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": "Data Scientist with NLP and ML expertise",
            "summary": "Experienced in NLP, machine learning pipelines, and data-driven decision systems.",
            "location": rng.choice(_LOCATIONS_TIER2),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_ADJACENT),
            "current_company": rng.choice(_COMPANIES_STARTUP),
            "current_company_size": rng.choice(["51-200", "201-500"]),
            "current_industry": "Technology",
        },
        "career_history": roles,
        "education": _edu_block(rng, rng.choice([_INSTITUTIONS_TIER2, _INSTITUTIONS_TIER3])),
        "skills": _skills_block(rng, strong_n=3, weak_n=2),
        "redrob_signals": _signals_block(rng, active=rng.random() > 0.3),
    }


def make_persona_D(rng: random.Random, n: int) -> dict:
    """Weak match: Backend engineer with some ML exposure."""
    start_year = 2026 - rng.randint(3, 8)
    roles, actual_yoe = _career_block(rng, _TITLES_ADJACENT, _COMPANIES_TIER2 + _COMPANIES_STARTUP,
                                      n_roles=2, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": rng.choice(_TITLES_ADJACENT),
            "summary": "Backend engineer with exposure to Python and some machine learning tools.",
            "location": rng.choice(_LOCATIONS_TIER2 + _LOCATIONS_TIER3),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_ADJACENT),
            "current_company": rng.choice(_COMPANIES_TIER2),
            "current_company_size": "1001-5000",
            "current_industry": "Technology",
        },
        "career_history": roles,
        "education": _edu_block(rng, _INSTITUTIONS_TIER3),
        "skills": _skills_block(rng, strong_n=1, weak_n=3),
        "redrob_signals": _signals_block(rng, active=rng.random() > 0.4),
    }


def make_persona_E(rng: random.Random, n: int) -> dict:
    """Near-miss: Research background, good skills but pure academia."""
    start_year = 2026 - rng.randint(5, 10)
    roles, actual_yoe = _career_block(rng, ["Research Scientist", "Postdoctoral Fellow", "Research Engineer"],
                                      ["IISc", "IIT Research Lab", "Microsoft Research", "Google Research"],
                                      n_roles=2, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": "Research Scientist — NLP & Information Retrieval",
            "summary": "Published researcher in NLP and IR with strong academic background.",
            "location": rng.choice(_LOCATIONS_TIER2),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": "Research Scientist",
            "current_company": rng.choice(["IIT Bombay", "IISc", "Microsoft Research"]),
            "current_company_size": "5001+",
            "current_industry": "Research & Education",
        },
        "career_history": roles,
        "education": _edu_block(rng, _INSTITUTIONS_TIER1),
        "skills": _skills_block(rng, strong_n=4, weak_n=0),
        "redrob_signals": _signals_block(rng, active=rng.random() > 0.5),
    }


def make_persona_F(rng: random.Random, n: int) -> dict:
    """Consultant: TCS/Infosys background with ML buzzwords."""
    start_year = 2026 - rng.randint(4, 10)
    roles, actual_yoe = _career_block(rng, _TITLES_CONSULTING,
                                      list({"tcs", "infosys", "wipro", "accenture", "cognizant"}),
                                      n_roles=3, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": "Senior IT Consultant with AI/ML exposure",
            "summary": "Experienced IT consultant with exposure to AI/ML tools including Python and basic ML.",
            "location": rng.choice(_LOCATIONS_TIER2 + _LOCATIONS_TIER3),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_CONSULTING),
            "current_company": rng.choice(["TCS", "Infosys", "Wipro", "Accenture"]),
            "current_company_size": "5001+",
            "current_industry": "IT Services",
        },
        "career_history": roles,
        "education": _edu_block(rng, rng.choice([_INSTITUTIONS_TIER2, _INSTITUTIONS_TIER3])),
        "skills": _skills_block(rng, strong_n=1, weak_n=4),
        "redrob_signals": _signals_block(rng, active=rng.random() > 0.3),
    }


def make_persona_G(rng: random.Random, n: int) -> dict:
    """Leadership: Tech lead/manager with historical ML."""
    start_year = 2026 - rng.randint(8, 15)
    roles, actual_yoe = _career_block(rng, _TITLES_LEADERSHIP,
                                      _COMPANIES_TIER1 + _COMPANIES_STARTUP,
                                      n_roles=3, start_year=start_year)
    return {
        "candidate_id": f"CAND_{n:07d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": rng.choice(_TITLES_LEADERSHIP) + " — ML/AI",
            "summary": "Engineering leader with 10+ years, including early hands-on ML work.",
            "location": rng.choice(_LOCATIONS_TIER1 + _LOCATIONS_TIER2),
            "country": "India",
            "years_of_experience": round(actual_yoe, 1),
            "current_title": rng.choice(_TITLES_LEADERSHIP),
            "current_company": rng.choice(_COMPANIES_TIER1),
            "current_company_size": "1001-5000",
            "current_industry": "Technology",
        },
        "career_history": roles,
        "education": _edu_block(rng, rng.choice([_INSTITUTIONS_TIER1, _INSTITUTIONS_TIER2])),
        "skills": _skills_block(rng, strong_n=2, weak_n=1),
        "redrob_signals": _signals_block(rng, active=rng.random() > 0.4),
    }


def make_persona_H(rng: random.Random, n: int) -> dict:
    """Honeypot: Planted fabricated/impossible profiles."""
    strategy = rng.choice(["impossible_dates", "expert_overload", "yoe_mismatch"])

    if strategy == "impossible_dates":
        # Education end_year < start_year (time travel)
        return {
            "candidate_id": f"CAND_{n:07d}",
            "profile": {
                "anonymized_name": f"Candidate {n}",
                "headline": "ML Engineer",
                "location": "Pune",
                "country": "India",
                "years_of_experience": 6,
                "current_title": "ML Engineer",
                "current_company": "FakeCorpX",
            },
            "career_history": [{
                "company": "FakeCorpX",
                "title": "ML Engineer",
                "start_date": "2020-01-01",
                "end_date": "2018-01-01",  # end before start — impossible
                "duration_months": 24,
                "is_current": False,
                "description": "some description",
            }],
            "education": [{"institution": "IIT Bombay", "degree": "B.Tech",
                            "field_of_study": "CS", "start_year": 2020, "end_year": 2018}],  # impossible
            "skills": _skills_block(rng, 2, 1),
            "redrob_signals": _signals_block(rng),
        }

    elif strategy == "expert_overload":
        # Claimed expert in 6 skills each with 1 month
        return {
            "candidate_id": f"CAND_{n:07d}",
            "profile": {
                "anonymized_name": f"Candidate {n}",
                "headline": "Full Stack ML Expert",
                "location": "Bengaluru",
                "country": "India",
                "years_of_experience": 4,
                "current_title": "ML Engineer",
                "current_company": "OverclaimedCo",
            },
            "career_history": [{
                "company": "OverclaimedCo",
                "title": "ML Expert",
                "start_date": "2022-01-01",
                "end_date": None,
                "duration_months": 48,
                "is_current": True,
                "description": "expert in everything",
            }],
            "education": _edu_block(rng, _INSTITUTIONS_TIER2),
            "skills": [
                {"name": s, "proficiency": "expert", "endorsements": 0, "duration_months": 1}
                for s in ["Python", "Go", "Rust", "C++", "Swift", "Kotlin"]
            ],
            "redrob_signals": _signals_block(rng),
        }

    else:  # yoe_mismatch
        # Declared YoE massively exceeds career history
        return {
            "candidate_id": f"CAND_{n:07d}",
            "profile": {
                "anonymized_name": f"Candidate {n}",
                "headline": "Seasoned ML Architect",
                "location": "Hyderabad",
                "country": "India",
                "years_of_experience": 15,  # claimed
                "current_title": "ML Architect",
                "current_company": "ShadyCo",
            },
            "career_history": [{
                "company": "ShadyCo",
                "title": "ML Architect",
                "start_date": "2023-01-01",
                "end_date": None,
                "duration_months": 18,  # only 1.5 years in history
                "is_current": True,
                "description": "built systems",
            }],
            "education": _edu_block(rng, _INSTITUTIONS_TIER3),
            "skills": _skills_block(rng, 2, 2),
            "redrob_signals": _signals_block(rng),
        }


# ─── Main ────────────────────────────────────────────────────────────────────

_PERSONA_DIST = [
    (0.03, make_persona_A),
    (0.07, make_persona_B),
    (0.15, make_persona_C),
    (0.30, make_persona_D),
    (0.15, make_persona_E),
    (0.15, make_persona_F),
    (0.10, make_persona_G),
    (0.05, make_persona_H),
]


def _sample_persona(rng: random.Random) -> type:
    r = rng.random()
    cumulative = 0.0
    for frac, factory in _PERSONA_DIST:
        cumulative += frac
        if r < cumulative:
            return factory
    return _PERSONA_DIST[-1][1]


def main():
    parser = argparse.ArgumentParser(description="Generate 100K synthetic candidates for PolyHire Redrob.")
    parser.add_argument("--out", default="data/candidates.jsonl", help="Output JSONL path")
    parser.add_argument("--n", type=int, default=100_000, help="Number of candidates to generate")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[generate] Writing {args.n:,} candidates to {out_path}...", file=sys.stderr)

    with open(out_path, "w", encoding="utf-8") as f:
        for i in range(1, args.n + 1):
            factory = _sample_persona(rng)
            candidate = factory(rng, i)
            f.write(json.dumps(candidate, ensure_ascii=False) + "\n")
            if i % 10_000 == 0:
                print(f"  ...{i:,} candidates written", file=sys.stderr)

    print(f"[generate] Done. {args.n:,} candidates written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
