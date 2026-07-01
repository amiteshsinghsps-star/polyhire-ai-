"""FastAPI routes for ResumeShield™ fraud detection."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from ..stages.resume_shield import ResumeShieldEngine

router = APIRouter(prefix="/shield", tags=["ResumeShield™"])
_engine = ResumeShieldEngine()


class ShieldRequest(BaseModel):
    candidate: dict
    jd_text: Optional[str] = ""


class ShieldBatchRequest(BaseModel):
    candidates: list[dict]
    structured_jd: dict


@router.post("/analyze")
def analyze_single(req: ShieldRequest) -> dict:
    """Analyze a single candidate for resume fraud signals."""
    assessment = _engine.analyze(req.candidate, req.jd_text or "")
    return {
        "candidate_id":      assessment.candidate_id,
        "fraud_risk_score":  assessment.fraud_risk_score,
        "fraud_label":       assessment.fraud_label,
        "fraud_flags":       assessment.fraud_flags,
        "trust_penalty":     assessment.trust_penalty,
        "recruiter_action":  assessment.recruiter_action,
        "can_proceed":       assessment.can_proceed,
        "detector_breakdown": {
            k: {
                sk: v for sk, v in det.items()
                if sk not in ("evidence", "flags", "hard_flags")
            }
            for k, det in assessment.detector_scores.items()
        },
    }


@router.post("/analyze-batch")
def analyze_batch(req: ShieldBatchRequest) -> dict:
    """Analyze a batch of candidates and inject fraud signals into each dict."""
    enriched = _engine.analyze_batch(req.candidates, req.structured_jd)
    summary = {
        "clean":      sum(1 for c in enriched if c.get("fraud_label") == "clean"),
        "suspicious": sum(1 for c in enriched if c.get("fraud_label") == "suspicious"),
        "high_risk":  sum(1 for c in enriched if c.get("fraud_label") == "high_risk"),
        "blocked":    sum(1 for c in enriched if c.get("fraud_label") == "blocked"),
    }
    return {
        "candidates":   enriched,
        "fraud_summary": summary,
        "total":        len(enriched),
    }


@router.get("/stats")
def fraud_stats() -> dict:
    """Aggregated fraud statistics. In production: queries fraud_signals table."""
    return {
        "note": "Query the fraud_signals Postgres table for historical aggregate stats.",
        "detectors": list(_engine.WEIGHTS.keys()),
        "thresholds": _engine.THRESHOLDS,
        "weights": _engine.WEIGHTS,
    }
