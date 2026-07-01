"""
Candidate dataset loader + synthesizer.

The challenge organizers provide a candidate dataset; this module loads it
from JSON/CSV/JSONL. When no dataset is present (judges cloning the repo
cold), it synthesizes a realistic candidate pool so the entire pipeline is
demoable end-to-end with zero external data.

The synthesizer generates a coherent pool: skill sets, career trajectories,
and behavioral signals are all internally consistent, so the fusion ranker
has real signal to fuse rather than random noise.
"""
from __future__ import annotations

import csv
import json
import logging
import random
from pathlib import Path
from typing import Any, Iterable

from .schemas import CandidateMetadata, CandidateProfile, EducationEntry

log = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = Path("data/candidates.json")


# ---------------------------------------------------------------------------
# Skill universe for the synthesizer
# ---------------------------------------------------------------------------

SKILL_DOMAINS: dict[str, list[str]] = {
    "backend": ["python", "java", "go", "rust", "django", "flask", "fastapi", "spring", "node", "postgresql", "redis", "kafka", "microservices", "grpc", "docker", "kubernetes"],
    "frontend": ["javascript", "typescript", "react", "angular", "vue", "next.js", "css", "tailwind", "redux", "graphql", "html", "webgl", "three.js"],
    "data": ["python", "sql", "spark", "airflow", "dbt", "snowflake", "pandas", "numpy", "airflow", "kafka", "hadoop", "tableau", "looker"],
    "ml": ["python", "pytorch", "tensorflow", "scikit-learn", "nlp", "llm", "computer vision", "deep learning", "pandas", "numpy", "transformers", "rag"],
    "devops": ["linux", "docker", "kubernetes", "terraform", "aws", "gcp", "azure", "ansible", "ci/cd", "jenkins", "prometheus", "grafana"],
    "mobile": ["swift", "kotlin", "react native", "flutter", "android", "ios", "dart"],
}

DOMAINS = list(SKILL_DOMAINS.keys())

FIRST_NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Aditya", "Ishaan", "Saanvi", "Rohan",
               "Myra", "Arjun", "Anika", "Kabir", "Navya", "Reyansh", "Aisha", "Vivaan",
               "Tara", "Dhruv", "Kiara", "Aryan", "Riya", "Karan", "Meera", "Yash",
               "Sara", "Nikhil", "Pari", "Rahul", "Ira", "Veer"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Nair", "Reddy", "Singh", "Patel", "Gupta",
              "Khan", "Das", "Mehta", "Joshi", "Bose", "Rao", "Kapoor", "Malhotra",
              "Chopra", "Banerjee", "Pillai", "Menon"]

ROLE_TITLES = {
    "junior": ["Junior Engineer", "Associate", "Graduate Trainee", "Engineer I"],
    "mid": ["Software Engineer", "Engineer II", "Analyst", "Specialist"],
    "senior": ["Senior Engineer", "Lead", "Staff Engineer", "Senior Analyst"],
    "staff": ["Staff Engineer", "Principal Engineer", "Tech Lead", "Architect"],
}

INDIAN_CITIES = [
    "Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune",
    "Nagpur", "Lucknow", "Jaipur", "Indore", "Bhopal", "Coimbatore",
    "Patna", "Vadodara", "Kochi", "Guwahati", "Dehradun", "Varanasi",
]

INSTITUTIONS = [
    "IIT Bombay", "IIT Delhi", "NIT Nagpur", "NIT Trichy", "BITS Pilani",
    "VIT Vellore", "IIIT Hyderabad", "NIT Surathkal", "Unknown College",
    "SRM University", "Manipal University", "PSG College", "Thapar University",
]

CODE_SWITCH_SNIPPETS = [
    "5 years ka anubhav in Python development.",
    "Expert in डेटा विश्लेषण and machine learning.",
    "Worked on machiene learning projects with strong developement skills.",
    "",
]

INFORMAL_SNIPPETS = [
    "Ran a small software consultancy in Nagpur for 2 years managing 3 engineers.",
    "Freelance developer, delivered 12 web projects for local businesses.",
    "Managed family textile shop with 4 staff and vendor relationships.",
    "",
]


def _profile_text(profile: CandidateProfile) -> str:
    """Compose a free-text profile blurb used for embedding + reranking."""
    parts = [
        f"{profile.name or 'Candidate'} — {profile.current_title or 'Professional'}.",
        f"{profile.summary}",
        f"Skills: {', '.join(profile.skills)}.",
        f"{profile.metadata.years_experience:.0f} years experience across "
        f"{profile.metadata.num_jobs} roles; avg tenure "
        f"{profile.metadata.avg_tenure_months:.0f} months.",
    ]
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_dataset(path: str | Path | None = None) -> list[CandidateProfile]:
    """
    Load candidates from disk. Supports .json (list), .jsonl, .csv.
    If the path doesn't exist, returns a synthesized demo pool.
    """
    if path is None:
        path = DEFAULT_DATASET_PATH
    path = Path(path)

    if not path.exists():
        log.info("Dataset %s not found — synthesizing a demo candidate pool.", path)
        return synthesize_pool(n=240, seed=42)

    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open(encoding="utf-8") as f:
            raw = json.load(f)
        rows = raw if isinstance(raw, list) else raw.get("candidates", [])
    elif suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif suffix == ".csv":
        with path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        log.warning("Unsupported dataset format %s; synthesizing instead.", suffix)
        return synthesize_pool(n=240, seed=42)

    profiles = [_coerce_row(r) for r in rows]
    profiles = [p for p in profiles if p is not None]
    log.info("Loaded %d candidates from %s", len(profiles), path)
    if not profiles:
        log.warning("Dataset was empty — synthesizing a demo pool.")
        return synthesize_pool(n=240, seed=42)
    return profiles


def load_jsonl_stream(path: str | Path) -> Iterable[dict[str, Any]]:
    """
    Memory-efficient JSONL loader for the Redrob 100K candidate dataset.
    Supports .jsonl and .jsonl.gz.
    """
    p = Path(path)
    if not p.exists():
        log.warning("Candidate JSONL %s not found. Yielding empty stream.", p)
        return

    if p.suffix.lower() == ".gz":
        import gzip
        opener = lambda: gzip.open(p, "rt", encoding="utf-8")
    else:
        opener = lambda: open(p, "r", encoding="utf-8")
        
    with opener() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _coerce_row(row: dict[str, Any]) -> CandidateProfile | None:
    try:
        meta_raw = row.get("metadata", {})
        if isinstance(meta_raw, str):
            meta_raw = json.loads(meta_raw)
        meta = CandidateMetadata(
            years_experience=float(meta_raw.get("years_experience", row.get("years_experience", 0)) or 0),
            num_jobs=int(meta_raw.get("num_jobs", row.get("num_jobs", 0)) or 0),
            avg_tenure_months=float(meta_raw.get("avg_tenure_months", 0) or 0),
            title_jump_velocity=float(meta_raw.get("title_jump_velocity", 0) or 0),
            claimed_skill_count=int(meta_raw.get("claimed_skill_count", len(row.get("skills", []) or [])) or 0),
            profile_completeness=float(meta_raw.get("profile_completeness", 1.0) or 1.0),
            last_activity_days_ago=int(meta_raw.get("last_activity_days_ago", 0) or 0),
            career_trajectory_slope=float(meta_raw.get("career_trajectory_slope", 0.0) or 0.0),
            engagement_score=float(meta_raw.get("engagement_score", 0.5) or 0.5),
        )
        skills = row.get("skills", []) or []
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        profile = CandidateProfile(
            id=str(row.get("id") or row.get("candidate_id") or ""),
            name=row.get("name"),
            summary=str(row.get("summary", "")),
            skills=[str(s) for s in skills],
            current_title=row.get("current_title") or row.get("title"),
            metadata=meta,
            city=row.get("city") or row.get("location"),
            location=row.get("location") or row.get("city"),
            institution=row.get("institution"),
            degree=row.get("degree"),
        )
        edu_raw = row.get("education", [])
        if isinstance(edu_raw, list) and edu_raw:
            profile.education = [
                EducationEntry(**e) if isinstance(e, dict) else EducationEntry(institution=str(e))
                for e in edu_raw
            ]
        profile.profile_text = row.get("profile_text") or _profile_text(profile)
        if not profile.id:
            return None
        return profile
    except Exception as exc:  # noqa: BLE001
        log.warning("Skipping malformed candidate row (%s): %s", exc, row)
        return None


def synthesize_pool(n: int = 240, seed: int = 42) -> list[CandidateProfile]:
    """
    Synthesize a realistic, internally-consistent candidate pool.

    Each candidate is anchored to a primary domain; skills, title, and
    trajectory all derive from it, so the fusion ranker has genuine
    semantic + behavioral signal to work with.
    """
    rng = random.Random(seed)
    profiles: list[CandidateProfile] = []

    for i in range(n):
        domain = rng.choice(DOMAINS)
        pool = SKILL_DOMAINS[domain]
        # Adjacent-domain bleed so cross-domain candidates exist
        if rng.random() < 0.35:
            adj = rng.choice([d for d in DOMAINS if d != domain])
            pool = pool + SKILL_DOMAINS[adj][:5]

        n_skills = rng.randint(4, min(12, len(pool)))
        skills = rng.sample(pool, n_skills)

        years = round(rng.uniform(0.5, 18.0), 1)
        num_jobs = max(1, int(years / rng.uniform(1.2, 3.0)))
        avg_tenure = round((years * 12) / max(num_jobs, 1), 1)

        # Seniority from years, with noise
        if years < 2:
            level = "junior"
        elif years < 5:
            level = "mid"
        elif years < 9:
            level = "senior"
        else:
            level = rng.choice(["senior", "staff"])
        title = rng.choice(ROLE_TITLES[level])

        # Trajectory slope: how quickly titles advanced (proxy from years/jobs)
        trajectory = round((num_jobs / max(years, 0.5)) * rng.uniform(0.3, 1.0), 3)
        engagement = round(rng.uniform(0.2, 1.0), 3)
        last_active = rng.choices([0, 5, 14, 30, 90, 180, 365], weights=[30, 20, 15, 12, 10, 8, 5])[0]
        completeness = round(rng.uniform(0.4, 1.0), 3)

        # Occasionally inject a synthetic anomaly (improbable claim density)
        title_jump = round(trajectory * rng.uniform(0.5, 2.0), 3)
        if rng.random() < 0.05:  # ~5% anomalous
            title_jump *= 4.0
            skills = skills + rng.sample(pool, min(8, len(pool)))  # inflated skill count

        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        summary = (
            f"{title} with {years:.0f} years in {domain}-adjacent work. "
            f"Strong in {', '.join(skills[:3])}."
        )

        meta = CandidateMetadata(
            years_experience=years,
            num_jobs=num_jobs,
            avg_tenure_months=avg_tenure,
            title_jump_velocity=title_jump,
            claimed_skill_count=len(skills),
            profile_completeness=completeness,
            last_activity_days_ago=last_active,
            career_trajectory_slope=trajectory,
            engagement_score=engagement,
        )
        profile = CandidateProfile(
            id=f"cand_{i:04d}",
            name=name,
            summary=summary,
            skills=skills,
            current_title=title,
            metadata=meta,
            city=rng.choice(INDIAN_CITIES),
            institution=rng.choice(INSTITUTIONS),
            degree=rng.choice(["B.Tech", "M.Tech", "B.E.", "MCA"]),
            education=[
                EducationEntry(
                    institution=rng.choice(INSTITUTIONS),
                    degree=rng.choice(["B.Tech", "M.Tech", "B.E."]),
                )
            ],
        )
        extra = " ".join(
            s for s in [rng.choice(CODE_SWITCH_SNIPPETS), rng.choice(INFORMAL_SNIPPETS)] if s
        )
        profile.profile_text = (_profile_text(profile) + " " + extra).strip()
        profiles.append(profile)

    log.info("Synthesized %d candidates (seed=%d).", len(profiles), seed)
    return profiles


def profiles_to_feature_matrix(profiles: Iterable[CandidateProfile]) -> tuple[list[str], "list[CandidateProfile]", Any]:
    """
    Build the anomaly-detector feature matrix in ANOMALY_FEATURES column order.
    Returns (candidate_ids, profiles, matrix).
    """
    import numpy as np

    from .stages.anomaly_detector import ANOMALY_FEATURES

    profiles = list(profiles)
    ids = [p.id for p in profiles]
    rows = []
    for p in profiles:
        m = p.metadata
        rows.append(
            [
                m.years_experience,
                m.num_jobs,
                m.avg_tenure_months,
                m.title_jump_velocity,
                m.claimed_skill_count,
                m.profile_completeness,
            ]
        )
    matrix = np.asarray(rows, dtype=np.float64) if rows else np.zeros((0, len(ANOMALY_FEATURES)))
    return ids, profiles, matrix
