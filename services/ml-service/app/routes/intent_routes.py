"""FastAPI routes for CandidateIntent™ Engine."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from ..stages.candidate_intent import CandidateIntentEngine

router = APIRouter(prefix="/intent", tags=["CandidateIntent™"])
_engine = CandidateIntentEngine()


class IntentRequest(BaseModel):
    candidate: dict
    structured_jd: Optional[dict] = None


class BatchIntentRequest(BaseModel):
    candidates: list[dict]
    structured_jd: Optional[dict] = None


@router.post("/score")
def score_intent(req: IntentRequest) -> dict:
    """Score a single candidate's mobility / outreach readiness."""
    result = _engine.score(req.candidate, req.structured_jd)
    return {
        "candidate_id":           result.candidate_id,
        "composite_intent_score": result.composite_intent_score,
        "intent_label":           result.intent_label,
        "contact_timing_advice":  result.contact_timing_advice,
        "days_until_peak_window": result.days_until_peak_window,
        "sub_signals": {
            "tenure_risk":          result.tenure_risk,
            "platform_recency":     result.platform_recency,
            "career_velocity":      result.career_velocity,
            "market_context":       result.market_context,
            "life_event_proximity": result.life_event_proximity,
        },
        "sub_signal_detail": result.sub_signals,
    }


@router.post("/score-batch")
def score_batch(req: BatchIntentRequest) -> dict:
    """Enrich and re-sort a ranked shortlist with intent scores."""
    enriched = _engine.score_batch(req.candidates, req.structured_jd)
    return {"candidates": enriched, "count": len(enriched)}


@router.post("/priority-matrix")
def priority_matrix(req: BatchIntentRequest) -> dict:
    """Build the 2×2 Fit × Intent priority matrix from a shortlist."""
    enriched = _engine.score_batch(req.candidates, req.structured_jd)
    return _engine.build_priority_matrix(enriched)
