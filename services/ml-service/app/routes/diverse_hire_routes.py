"""FastAPI routes for DiverseHire™ — bias detection + diversity intelligence."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from ..stages.diverse_hire import DiverseHireEngine

router = APIRouter(prefix="/diverse-hire", tags=["DiverseHire™"])
_engine = DiverseHireEngine()


class AnalyzeJDRequest(BaseModel):
    jd_text: str


class ScoreShortlistRequest(BaseModel):
    candidates: list[dict]
    jd_text: Optional[str] = ""


class FullReportRequest(BaseModel):
    jd_text: str
    candidates: list[dict]


@router.post("/analyze-jd")
def analyze_jd(req: AnalyzeJDRequest) -> dict:
    """
    Analyze a JD for gendered language and exclusionary patterns.
    Returns: gender_language, jd_cleaner, overall_jd_bias_score.
    """
    return _engine.analyze_jd(req.jd_text)


@router.post("/score-shortlist")
def score_shortlist(req: ScoreShortlistRequest) -> dict:
    """
    Score a shortlist for institution diversity (Shannon entropy).
    Returns: institution_bias, diversity_score, recommendation.
    """
    return _engine.score_shortlist(req.candidates)


@router.post("/clean-jd")
def clean_jd(req: AnalyzeJDRequest) -> dict:
    """
    Return a cleaned version of the JD with exclusionary language removed.
    Rule-based rewrite — no LLM required.
    """
    return _engine.jd_cleaner.clean(req.jd_text)


@router.post("/full-report")
def full_report(req: FullReportRequest) -> dict:
    """
    Combined JD analysis + shortlist diversity report.
    Ideal for the DiverseHire™ dashboard tab.
    """
    return _engine.full_report(req.jd_text, req.candidates)


@router.get("/word-lists")
def word_lists() -> dict:
    """Return the gendered word lists in use (for transparency)."""
    from ..stages.diverse_hire import MASCULINE_CODED, FEMININE_CODED, NEUTRAL_REPLACEMENTS
    return {
        "masculine_coded_words": sorted(list(MASCULINE_CODED)),
        "feminine_coded_words":  sorted(list(FEMININE_CODED)),
        "neutral_replacements":  NEUTRAL_REPLACEMENTS,
        "source": "Gaucher, Friesen, Kay (2011) + India-specific additions",
    }
