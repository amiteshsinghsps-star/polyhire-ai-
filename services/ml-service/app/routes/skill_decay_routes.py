"""FastAPI routes for SkillDecay™ Graph."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..stages.skill_decay import SkillDecayAnalyzer

router = APIRouter(prefix="/skill-decay", tags=["SkillDecay™"])
_analyzer = SkillDecayAnalyzer()


class SkillDecayRequest(BaseModel):
    candidate: dict
    structured_jd: dict


class BatchSkillDecayRequest(BaseModel):
    candidates: list[dict]
    structured_jd: dict


@router.post("/analyze")
def analyze_skill_decay(req: SkillDecayRequest) -> dict:
    """Compute time-decayed skill relevance for a single candidate against a JD."""
    return _analyzer.analyze(req.candidate, req.structured_jd)


@router.post("/enrich-batch")
def enrich_batch(req: BatchSkillDecayRequest) -> dict:
    """Replace static skill_overlap_ratio with temporal version for a full shortlist."""
    enriched = _analyzer.enrich_candidates(req.candidates, req.structured_jd)
    return {"candidates": enriched, "count": len(enriched)}
