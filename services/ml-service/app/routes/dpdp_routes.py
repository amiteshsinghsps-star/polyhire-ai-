"""FastAPI routes for DPDP Compliance Layer."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..stages.dpdp_layer import DPDPComplianceEngine

router = APIRouter(prefix="/dpdp", tags=["DPDP Compliance"])
_engine = DPDPComplianceEngine()


class ConsentRequest(BaseModel):
    candidate_id: str
    purpose: str
    consent_given: bool = True
    data_fields_accessed: list[str] = []
    jd_id: Optional[str] = None


class ErasureRequest(BaseModel):
    candidate_id: str
    reason: str = "data_subject_request"
    requester: str = "candidate"


class JDValidateRequest(BaseModel):
    jd_text: str


@router.post("/consent")
def record_consent(req: ConsentRequest) -> dict:
    """Record processing consent for a candidate. DPDP §6."""
    return _engine.consent.record_processing(
        candidate_id=req.candidate_id,
        purpose=req.purpose,
        consent_given=req.consent_given,
        data_fields_accessed=req.data_fields_accessed,
        jd_id=req.jd_id,
    )


@router.delete("/erasure/{candidate_id}")
def request_erasure(candidate_id: str, reason: str = "data_subject_request") -> dict:
    """
    Right to erasure — cascade delete across all stores. DPDP §12.
    Production: also issues DELETE to Postgres + Qdrant point delete.
    """
    return _engine.erasure.request_erasure(candidate_id, reason=reason)


@router.get("/transparency/{candidate_id}")
def get_transparency(candidate_id: str) -> dict:
    """
    Algorithmic transparency report for a candidate. DPDP §12.
    Returns all ranking events the candidate was involved in.
    """
    report = _engine.transparency.export_for_candidate(candidate_id)
    if report["total_evaluations"] == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No transparency records found for candidate {candidate_id}",
        )
    return report


@router.get("/consent-history/{candidate_id}")
def consent_history(candidate_id: str) -> dict:
    history = _engine.consent.get_consent_history(candidate_id)
    return {"candidate_id": candidate_id, "history": history, "count": len(history)}


@router.post("/validate-jd")
def validate_jd(req: JDValidateRequest) -> dict:
    """
    Validate a JD for prohibited attributes (DPDP §8 data minimisation).
    Returns violations + suggestions to fix.
    """
    return _engine.validate_jd(req.jd_text)


@router.get("/compliance-summary")
def compliance_summary() -> dict:
    """Overall DPDP compliance dashboard summary."""
    return _engine.get_compliance_summary()


@router.get("/pending-erasures")
def pending_erasures() -> dict:
    pending = _engine.erasure.get_pending_erasures()
    return {"pending": pending, "count": len(pending)}
