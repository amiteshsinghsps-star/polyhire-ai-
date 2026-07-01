"""
Enterprise Feature Routes (§23).

REST endpoints for all 8 enterprise features, mounted under /enterprise/ in the
ML service. These are consumed by the gateway's /api/enterprise/* routes.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .stages.uncertainty import UncertaintyEstimator
from .stages.counterfactual import CounterfactualEngine
from .stages.portfolio_optimizer import PortfolioOptimizer
from .stages.audit_logger import AuditLogger
from .stages.diversity_reranker import DiversityReranker
from .stages.passive_matcher import PassiveTalentMiner
from .stages.interview_questions import InterviewQuestionGenerator
from .stages.drift_monitor import DriftMonitor
from .pipeline import get_pipeline

log = logging.getLogger(__name__)

router = APIRouter(prefix="/enterprise", tags=["enterprise"])

# ---- Singleton instances ----

_uncertainty: UncertaintyEstimator | None = None
_counterfactual: CounterfactualEngine | None = None
_portfolio: PortfolioOptimizer | None = PortfolioOptimizer()
_audit: AuditLogger | None = None
_diversity: DiversityReranker | None = None
_passive_miner: PassiveTalentMiner | None = None
_interview_gen: InterviewQuestionGenerator | None = None
_drift_monitor: DriftMonitor | None = None


def _get_audit() -> AuditLogger:
    global _audit
    if _audit is None:
        _audit = AuditLogger(db_path="data/polyhire_audit.db")
    return _audit


def _get_interview_gen() -> InterviewQuestionGenerator:
    global _interview_gen
    if _interview_gen is None:
        _interview_gen = InterviewQuestionGenerator()
    return _interview_gen


# ---- Request / Response models ----

class UncertaintyRequest(BaseModel):
    candidate_id: str
    features: dict[str, float]


class CounterfactualRequest(BaseModel):
    candidate_id: str
    current_features: dict[str, float]
    target_score: float = 0.8
    num_counterfactuals: int = 3


class PortfolioRequest(BaseModel):
    score_matrix: dict[str, dict[str, float]]  # {candidate_id: {role_id: score}}
    slots_per_role: dict[str, int]


class AuditVerifyRequest(BaseModel):
    jd_id: str


class DiversifyRequest(BaseModel):
    candidate_ids: list[str]
    relevance_scores: list[float]
    embeddings: list[list[float]]  # candidate embeddings
    lambda_param: float = 0.7
    top_k: int = 20


class InterviewQuestionsRequest(BaseModel):
    candidate_id: str
    role_title: str
    claimed_skills: list[str]
    uncertain_skills: list[str] = []


class DriftCheckRequest(BaseModel):
    current_features: list[dict[str, float]]


class DisparateImpactRequest(BaseModel):
    jd_id: str
    group_assignments: dict[str, str]  # {candidate_id: group_value}


# ---- §23.1 Uncertainty ----

@router.post("/uncertainty")
def get_uncertainty(payload: UncertaintyRequest) -> dict[str, Any]:
    import numpy as np

    global _uncertainty
    if _uncertainty is None:
        _uncertainty = UncertaintyEstimator()
    if not _uncertainty._fitted:
        return {
            "candidate_id": payload.candidate_id,
            "warning": "Uncertainty estimator not yet fitted. Run pipeline first.",
            "bands": [],
        }
    X = np.array([[payload.features.get(f, 0) for f in [
        "embedding_similarity", "rerank_score", "years_experience_match",
        "skill_overlap_ratio", "recency_of_activity", "career_trajectory_slope",
        "engagement_score", "trust_score",
    ]]])
    bands = _uncertainty.predict_with_bounds(X)
    return {"candidate_id": payload.candidate_id, "bands": bands}


# ---- §23.2 Counterfactual ----

@router.post("/counterfactual/{candidate_id}")
def get_counterfactual(candidate_id: str, payload: CounterfactualRequest) -> dict[str, Any]:
    global _counterfactual
    pipeline = get_pipeline()
    if _counterfactual is None:
        _counterfactual = CounterfactualEngine(
            fusion_model=getattr(pipeline.fusion, "_model", None),
        )
    results = _counterfactual.explain(
        candidate_row=payload.current_features,
        target_score=payload.target_score,
        total_cfs=payload.num_counterfactuals,
    )
    human_readable = [_counterfactual.to_human_readable(r) for r in results]
    return {
        "candidate_id": candidate_id,
        "counterfactuals": results,
        "human_readable": human_readable,
    }


# ---- §23.3 Portfolio optimization ----

@router.post("/portfolio/optimize")
def optimize_portfolio(payload: PortfolioRequest) -> dict[str, Any]:
    import pandas as pd

    df = pd.DataFrame(payload.score_matrix).T
    assignments = _portfolio.optimize(df, payload.slots_per_role)
    comparison = _portfolio.compare_to_naive(df, payload.slots_per_role)
    return {"assignments": assignments, "comparison": comparison}


# ---- §23.4 Audit trail ----

@router.get("/audit/{jd_id}")
def get_audit_trail(jd_id: str) -> dict[str, Any]:
    audit = _get_audit()
    trail = audit.get_trail(jd_id)
    return {"jd_id": jd_id, "entries": trail, "count": len(trail)}


@router.get("/audit/{jd_id}/verify")
def verify_audit(jd_id: str) -> dict[str, Any]:
    audit = _get_audit()
    valid = audit.verify_chain_integrity(jd_id)
    return {"jd_id": jd_id, "chain_valid": valid}


@router.post("/audit/disparate-impact")
def disparate_impact(payload: DisparateImpactRequest) -> dict[str, Any]:
    audit = _get_audit()
    report = audit.get_disparate_impact_report(payload.jd_id, payload.group_assignments)
    return report


# ---- §23.5 Diversity re-ranking ----

@router.post("/diversify")
def diversify_shortlist(payload: DiversifyRequest) -> dict[str, Any]:
    import numpy as np

    global _diversity
    if _diversity is None:
        _diversity = DiversityReranker(lambda_param=payload.lambda_param)
    embeddings = np.array(payload.embeddings)
    scores = np.array(payload.relevance_scores)
    result = _diversity.rerank(
        embeddings, scores, payload.candidate_ids, payload.top_k,
    )
    original_order = payload.candidate_ids[:payload.top_k]
    diversified_order = [r["candidate_id"] for r in result]
    report = _diversity.diversity_report(original_order, diversified_order)
    return {"ranked": result, "diversity_report": report}


# ---- §23.6 Passive talent matches ----

@router.get("/talent-pool/passive-matches")
def get_passive_matches(threshold: float = 0.85) -> dict[str, Any]:
    global _passive_miner
    if _passive_miner is None:
        pipeline = get_pipeline()
        _passive_miner = PassiveTalentMiner(embedder=pipeline.embedder)
    candidates = [p.model_dump() for p in pipeline._profiles]  # noqa: SLF001
    flags = _passive_miner.scan_candidate_pool(candidates, threshold=threshold)
    return {"flags": flags, "count": len(flags)}


# ---- §23.7 Interview questions ----

@router.post("/interview-questions")
def get_interview_questions(payload: InterviewQuestionsRequest) -> dict[str, Any]:
    gen = _get_interview_gen()
    questions = gen.generate(
        role_title=payload.role_title,
        claimed_skills=payload.claimed_skills,
        uncertain_skills=payload.uncertain_skills,
    )
    return {
        "candidate_id": payload.candidate_id,
        "questions": questions,
    }


# ---- §23.8 Drift status ----

@router.get("/drift-status")
def get_drift_status() -> dict[str, Any]:
    global _drift_monitor
    if _drift_monitor is None:
        _drift_monitor = DriftMonitor()
    latest = _drift_monitor.get_latest()
    if latest is None:
        return {
            "drift_detected": False,
            "drifted_features": [],
            "recommendation": "No drift check has been run yet. Submit a JD first.",
        }
    return latest
