"""
Bharat Intelligence Layer — FastAPI routes.

Exposed via the gateway for frontend transparency panels. Each endpoint maps to
one BIL module so the recruiter UI can show exactly what was adjusted and why.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from .stages.bharat.tier_normalizer import (
    TierCityEngagementNormalizer,
    classify_city_tier,
)
from .stages.bharat.institution_intelligence import (
    IndiaInstitutionIntelligence,
    NIRF_INSTITUTION_SCORES,
    _normalize_name,
)
from .stages.bharat.code_switch_parser import CodeSwitchResumeParser
from .stages.bharat.informal_sector_translator import InformalSectorTranslator

router = APIRouter(prefix="/bharat", tags=["Bharat Intelligence"])

_tier_norm = TierCityEngagementNormalizer()
_inst_iq = IndiaInstitutionIntelligence()
_code_switch = CodeSwitchResumeParser(use_indictrans2=False)
_informal = InformalSectorTranslator()


# ── Request / response models ──────────────────────────────────────────────


class TierNormRequest(BaseModel):
    engagement_score: float
    recency_score: float
    city: Optional[str] = None


class InstitutionRequest(BaseModel):
    institution: str
    degree: Optional[str] = None


class CodeSwitchRequest(BaseModel):
    text: str
    existing_skills: list[str] = []
    skill_pool: list[str] = []


class InformalSectorRequest(BaseModel):
    profile_text: str
    existing_skills: list[str] = []


# ── §BIL-1: Tier-city normalization ────────────────────────────────────────


@router.post("/tier-normalize")
def tier_normalize(req: TierNormRequest) -> dict[str, Any]:
    """Returns normalized engagement and recency scores for a given city."""
    result = _tier_norm.normalize(
        engagement_score=req.engagement_score,
        recency_score=req.recency_score,
        city=req.city,
    )
    return {
        "city": req.city,
        "tier": result.city_tier,
        "original_engagement": result.original_engagement_score,
        "normalized_engagement": result.normalized_engagement_score,
        "original_recency": result.original_recency_score,
        "normalized_recency": result.normalized_recency_score,
        "adjustment_applied": result.adjustment_applied,
        "engagement_delta": result.engagement_delta,
    }


@router.get("/classify-city")
def classify_city(city: str) -> dict[str, str]:
    """Classify a city into Tier 1, 2, or 3."""
    return {"city": city, "tier": classify_city_tier(city)}


# ── §BIL-2: Institution scoring ────────────────────────────────────────────


@router.post("/institution-score")
def institution_score(req: InstitutionRequest) -> dict[str, Any]:
    """Returns NIRF-based institution tier score."""
    result = _inst_iq.score_candidate(req.institution, req.degree)
    return {
        "institution": req.institution,
        "normalized_name": result.institution_name,
        "score": result.final_score,
        "match_type": result.match_type,
        "in_nirf_database": result.in_nirf_database,
        "degree_bonus": result.degree_bonus,
    }


@router.get("/nirf-lookup")
def nirf_lookup(name: str) -> dict[str, Any]:
    """Search the NIRF institution database."""
    query = _normalize_name(name)
    matches = [
        {"institution": k, "score": v}
        for k, v in NIRF_INSTITUTION_SCORES.items()
        if query in k or k in query
    ]
    return {"query": name, "matches": sorted(matches, key=lambda x: -x["score"])[:10]}


# ── §BIL-3: Code-switch parsing ────────────────────────────────────────────


@router.post("/code-switch-parse")
def code_switch_parse(req: CodeSwitchRequest) -> dict[str, Any]:
    """Normalize code-switched resume text and extract additional skills."""
    result = _code_switch.parse(
        text=req.text,
        existing_skills=req.existing_skills,
        skill_pool=set(req.skill_pool),
    )
    return {
        "normalized_text": result.normalized_text,
        "has_devanagari": result.has_devanagari,
        "has_hinglish": result.has_hinglish,
        "has_other_indic": result.has_other_indic,
        "code_switch_detected": result.code_switch_detected,
        "original_skills": result.original_skills,
        "new_skills_found": result.new_skills_found,
        "augmented_skills": result.augmented_skills,
        "translation_used": result.translation_used,
    }


# ── §BIL-4: Informal sector translation ────────────────────────────────────


@router.post("/informal-sector-translate")
def informal_sector_translate(req: InformalSectorRequest) -> dict[str, Any]:
    """Translate informal sector experience to formal skill signals."""
    result = _informal.translate(req.profile_text, req.existing_skills)
    return {
        "informal_sector_score": result.informal_sector_score,
        "detected_patterns": result.detected_patterns,
        "translated_skills": result.translated_skills,
        "high_confidence_skills": result.high_confidence_skills,
        "added_to_skills": result.added_to_candidate_skills,
        "explanation": result.explanation,
    }
