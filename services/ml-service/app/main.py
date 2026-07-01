"""
PolyHire ML Service — FastAPI entrypoint.

Exposes the candidate-discovery pipeline over a small REST surface that the
Node gateway consumes. Boots, lazily warms the index on first request, and
exposes health + capability endpoints so the gateway can adapt its UI to
whichever bonus models are available in this build.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .pipeline import get_pipeline
from .schemas import PipelineInput, PipelineResult
from .enterprise_routes import router as enterprise_router
from .bharat_routes import router as bharat_router
from .routes.intent_routes import router as intent_router
from .routes.skill_decay_routes import router as skill_decay_router
from .routes.hire_predict_routes import router as hire_predict_router
from .routes.shield_routes import router as shield_router
from .routes.dpdp_routes import router as dpdp_router
from .routes.diverse_hire_routes import router as diverse_hire_router
# v3.0 Security Layer
from .security.prompt_guard import PromptInjectionSanitizer
from .security.hallucination_guard import HallucinationGuard
from .security.honeypot import HoneypotManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("polyhire.ml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("PolyHire ML service starting up.")
    log.info("Feature flags: voice=%s, hindi=%s, bias=%s, skill_gap=%s, anomaly=%s, explain=%s",
             settings.enable_voice_input, settings.enable_hindi_translation,
             settings.enable_bias_detection, settings.enable_skill_gap_reports,
             settings.enable_anomaly_detection, settings.enable_llm_explainability)
    # Warm the index eagerly so the first JD request is fast.
    try:
        if not settings.submission_mode:
            pipeline = get_pipeline()
            n = pipeline.warm_index()
            log.info("Candidate index warmed with %d profiles.", n)
        else:
            log.info("SUBMISSION_MODE=True: Skipping index warming, vector DB, and GPU init.")
    except Exception as exc:  # noqa: BLE001
        log.error("Index warm-up failed at boot: %s", exc)
    yield
    log.info("PolyHire ML service shutting down.")


app = FastAPI(
    title="PolyHire AI — ML Service v3.0",
    description=(
        "Intelligent candidate discovery pipeline (Track 1 — India Runs by Redrob AI). "
        "v3.0: ResumeShield™ + DPDP Compliance + Vector Security + DiverseHire™"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# ── CORS Hardening (§5 Security PRD) ──────────────────────────────────────
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,      # NEVER use ["*"] in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    max_age=600,
)


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    pipeline = get_pipeline()
    return {
        "status": "ok",
        "index_ready": pipeline._index_ready,  # noqa: SLF001 — introspection for the gateway
        "candidate_count": len(pipeline._profiles),  # noqa: SLF001
        "backend": pipeline.retriever.backend_name,
        "capabilities": {
            "voice_input": pipeline.voice.is_available(),
            "hindi_translation": pipeline.translator.is_available(),
            "bias_detection": not pipeline.bias.is_fallback,
            "skill_gap_reports": pipeline.skill_gap.is_available(),
            "anomaly_detection": not pipeline.anomaly.is_fallback,
            "llm_explainability": bool(settings.groq_api_key),
            "embedding_model_loaded": not pipeline.embedder.is_fallback,
            "reranker_model_loaded": not pipeline.reranker.is_fallback,
            "fusion_ranker_trained": pipeline.fusion.is_trained,
            "bharat_intelligence": settings.enable_bharat_intelligence,
        },
        "fallbacks_active": {
            "embedder": pipeline.embedder.is_fallback,
            "reranker": pipeline.reranker.is_fallback,
            "bias": pipeline.bias.is_fallback,
            "anomaly": pipeline.anomaly.is_fallback,
        },
    }


@app.post("/pipeline/run", response_model=PipelineResult)
def run_pipeline(payload: PipelineInput) -> PipelineResult:
    log.info("Pipeline run: text=%dB audio=%s lang=%s",
             len(payload.text or ""), bool(payload.audio_path), payload.language)
    try:
        return get_pipeline().run(payload)
    except Exception as exc:  # noqa: BLE001 — surface a clean 500 to the gateway
        log.exception("Pipeline run failed.")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc


@app.post("/pipeline/run-stream")
async def run_pipeline_stream(payload: PipelineInput):
    """
    Server-sent events stream of stage progress + final result.
    The Node gateway can either call /pipeline/run (blocking) or proxy this
    stream for finer-grained progress. Kept thin on purpose.
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    queue: asyncio.Queue[tuple[str, str | None, float | None] | None] = asyncio.Queue()

    def on_stage(stage: str, message: str | None, progress: float | None) -> None:
        queue.put_nowait((stage, message, progress))

    async def producer():
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: get_pipeline().run(payload, on_stage=on_stage))
        await queue.put(("result", result.model_dump_json(), None))
        await queue.put(None)

    task = asyncio.create_task(producer())

    async def event_gen():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                stage, message, progress = item
                yield f"data: {json.dumps({'stage': stage, 'message': message, 'progress': progress})}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.post("/index/rebuild")
def rebuild_index(dataset_path: str | None = None) -> dict[str, object]:
    """Force a re-warm of the candidate index (e.g. after loading a new dataset)."""
    pipeline = get_pipeline()
    pipeline._index_ready = False  # noqa: SLF001
    n = pipeline.warm_index(dataset_path=dataset_path)
    return {"status": "ok", "candidate_count": n, "backend": pipeline.retriever.backend_name}


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "PolyHire AI ML Service", "docs": "/docs", "health": "/health"}


# Mount enterprise feature routes (§23)
app.include_router(enterprise_router)

# Mount Bharat Intelligence Layer routes (BIL §1-4)
app.include_router(bharat_router)

# ── v2.0 Feature Expansion ────────────────────────────────────────────────────
# F1: CandidateIntent™ — mobility scoring
app.include_router(intent_router)

# F2: SkillDecay™ — temporal skill relevance
app.include_router(skill_decay_router)

# F3: HirePredict™ — closed feedback loop
app.include_router(hire_predict_router)

# ── v3.0 Feature Expansion ────────────────────────────────────────────────────
# G1: ResumeShield™ — AI-generated resume & fraud detection
app.include_router(shield_router)

# G2: DPDP Compliance Layer — India data protection law
app.include_router(dpdp_router)

# G3: DiverseHire™ — bias elimination + diversity intelligence
app.include_router(diverse_hire_router)


# ── Hackathon Submission Mode ─────────────────────────────────────────────────
@app.post("/submission/run")
def run_submission() -> dict[str, Any]:
    """
    Run the hackathon submission mode (CPU-only, no network, 100K JSONL to CSV).
    """
    settings = get_settings()
    if not settings.submission_mode:
        raise HTTPException(
            status_code=400, 
            detail="SUBMISSION_MODE is not enabled in configuration."
        )
    
    try:
        pipeline = get_pipeline()
        out_path = pipeline.run_submission_mode()
        return {
            "status": "success",
            "message": "Submission ranked and CSV generated successfully.",
            "output_file": str(out_path)
        }
    except Exception as exc:
        log.exception("Submission mode run failed.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
