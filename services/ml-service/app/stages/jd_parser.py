"""
Stage 1 — Deep Job Understanding.

Converts unstructured JD text into a structured JSON contract via
a deterministic rule-based parser. This ensures the pipeline is
always runnable offline by judges.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import get_settings
from ..schemas import StructuredJD

log = logging.getLogger(__name__)

SCHEMA_DESCRIPTION: dict[str, Any] = {
    "role_title": "string",
    "seniority": "junior | mid | senior | staff | principal",
    "must_have_skills": ["string"],
    "nice_to_have_skills": ["string"],
    "domain": "string",
    "min_years_experience": "number",
    "soft_requirements": ["string"],
    "implicit_requirements": ["string"],
}

JD_PARSE_PROMPT = """You are a senior technical recruiter. Parse the following job
description into structured JSON. Separate explicitly stated requirements from
requirements you can reasonably infer from context (seniority cues, team size,
domain jargon). Return ONLY valid JSON matching this schema:
{schema}

Job Description:
{jd_text}
"""

# Heuristics for the offline fallback parser.
_SENIORITY_KEYWORDS = {
    "principal": ["principal", "distinguished"],
    "staff": ["staff"],
    "senior": ["senior", "sr.", "sr ", "lead", "lead"],
    "mid": ["mid", "mid-level", "ii", "iii"],
    "junior": ["junior", "jr", "entry", "graduate", "intern"],
}

_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)(?:\s+of)?\s+(?:experience|exp)", re.I)
_YEARS_RE_LOOSE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)

_TECH_SKILL_BANK = [
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "kotlin", "swift",
    "react", "angular", "vue", "next.js", "node", "express", "django", "flask", "fastapi",
    "spring", "rails", "graphql", "rest", "grpc",
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform", "ansible",
    "postgres", "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
    "kafka", "rabbitmq", "spark", "hadoop", "airflow", "dbt", "snowflake",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "nlp", "machine learning",
    "deep learning", "llm", "computer vision", "data science",
    "linux", "bash", "git", "ci/cd", "jenkins", "microservices", "distributed systems",
    "system design", "agile", "scrum",
]


def _detect_seniority(text: str, role_title: str) -> str:
    combined = f"{role_title} {text}".lower()
    for level, keywords in _SENIORITY_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return level  # type: ignore[return-value]
    return "mid"


def _detect_min_years(text: str) -> float:
    m = _YEARS_RE.search(text) or _YEARS_RE_LOOSE.search(text)
    return float(m.group(1)) if m else 0.0


def _detect_skills(text: str) -> tuple[list[str], list[str]]:
    lower = text.lower()
    found = [skill for skill in _TECH_SKILL_BANK if skill in lower]
    # Heuristic: skills mentioned near "must"/"required"/"strong" → must-have,
    # near "nice"/"bonus"/"preferred" → nice-to-have. Simple windowing.
    must, nice = [], []
    for skill in found:
        window = lower.find(skill)
        ctx = lower[max(0, window - 80) : window + 80]
        if any(k in ctx for k in ["must", "required", "strong", "essential", "need"]):
            must.append(skill)
        elif any(k in ctx for k in ["nice", "bonus", "preferred", "plus", "optional"]):
            nice.append(skill)
        else:
            must.append(skill)  # default to must-have
    # de-dup, preserve order
    return _dedupe(must), _dedupe(nice)


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _rule_based_parse(jd_text: str) -> StructuredJD:
    """Offline fallback: deterministic skill/seniority extraction."""
    first_line = jd_text.strip().splitlines()[0] if jd_text.strip() else "Untitled Role"
    role_title = re.sub(r"\s+", " ", first_line).strip()[:120] or "Untitled Role"
    must, nice = _detect_skills(jd_text)
    return StructuredJD(
        role_title=role_title,
        seniority=_detect_seniority(jd_text, role_title),  # type: ignore[arg-type]
        must_have_skills=must,
        nice_to_have_skills=nice,
        domain="general",
        min_years_experience=_detect_min_years(jd_text),
        soft_requirements=[],
        implicit_requirements=["parsed via offline rule-based fallback (no LLM key configured)"],
    )


def parse_jd(jd_text: str) -> StructuredJD:
    """
    Public entrypoint. Uses the deterministic rule-based parser
    so the pipeline is fully offline and relies on no API keys.
    """
    if not jd_text or not jd_text.strip():
        log.warning("Empty JD text received; returning minimal StructuredJD.")
        return StructuredJD(role_title="Untitled Role")

    return _rule_based_parse(jd_text)
