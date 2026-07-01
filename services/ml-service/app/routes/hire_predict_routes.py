"""FastAPI routes for HirePredict™ Outcome Loop."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..stages.hire_predict import HirePredictStore, HirePredictModel

router = APIRouter(prefix="/hire-predict", tags=["HirePredict™"])

_store = HirePredictStore()
_model = HirePredictModel(_store)


class OutcomeFeedback(BaseModel):
    jd_id:        str
    candidate_id: str
    hired:        bool
    retained_30d: Optional[bool] = None
    features:     dict = {}


class PredictRequest(BaseModel):
    candidates: list[dict]
    jd_id:      Optional[str] = None


@router.post("/feedback")
def submit_feedback(req: OutcomeFeedback) -> dict:
    """Submit a hire outcome. Triggers model retraining if enough data collected."""
    result = _store.save_outcome(
        jd_id=req.jd_id,
        candidate_id=req.candidate_id,
        hired=req.hired,
        features=req.features,
        retained_30d=req.retained_30d,
    )
    # Auto-retrain when we cross the threshold
    n = _store.count_outcomes()
    from ..stages.hire_predict import MIN_SAMPLES_TO_TRAIN
    if n >= MIN_SAMPLES_TO_TRAIN and n % 5 == 0:
        train_result = _model.train()
        result["retrain_triggered"] = train_result
    return result


@router.post("/predict")
def predict_outcomes(req: PredictRequest) -> dict:
    """Attach hire_probability to each candidate in the shortlist."""
    enriched = _model.predict(req.candidates)
    return {"candidates": enriched, "model_trained": _model._trained}


@router.post("/train")
def force_train() -> dict:
    """Force model retraining (call after submitting batch feedback)."""
    return _model.train()


@router.get("/accuracy")
def accuracy_report() -> dict:
    """Model accuracy report + outcome collection progress."""
    return _model.accuracy_report()


@router.get("/outcomes/{jd_id}")
def get_outcomes(jd_id: str) -> dict:
    """Get all recorded outcomes for a specific JD."""
    outcomes = _store.load_outcomes_for_jd(jd_id)
    if not outcomes:
        raise HTTPException(status_code=404, detail=f"No outcomes found for jd_id={jd_id}")
    return {"jd_id": jd_id, "outcomes": outcomes, "count": len(outcomes)}
