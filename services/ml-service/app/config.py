"""
Centralized configuration for the ML service.

All tunables + feature flags live here so the pipeline never reads os.environ
directly outside this module. Loaded once at import time.

Design: CPU-only, offline-first. No GPU, no external API keys required.
Every stage has a deterministic fallback that works with zero downloads.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # --- Vector DB mode (always CPU/in-process) ---
    # "memory" = FAISS in-process (default, zero config)
    qdrant_mode: str = field(default_factory=lambda: os.getenv("QDRANT_MODE", "memory"))

    # --- Feature flags ---
    enable_voice_input: bool = field(default_factory=lambda: _env_bool("ENABLE_VOICE_INPUT", True))
    enable_hindi_translation: bool = field(
        default_factory=lambda: _env_bool("ENABLE_HINDI_TRANSLATION", True)
    )
    enable_bias_detection: bool = field(
        default_factory=lambda: _env_bool("ENABLE_BIAS_DETECTION", True)
    )
    enable_skill_gap_reports: bool = field(
        default_factory=lambda: _env_bool("ENABLE_SKILL_GAP_REPORTS", True)
    )
    enable_anomaly_detection: bool = field(
        default_factory=lambda: _env_bool("ENABLE_ANOMALY_DETECTION", True)
    )
    enable_llm_explainability: bool = field(
        default_factory=lambda: _env_bool("ENABLE_LLM_EXPLAINABILITY", True)
    )

    # --- Bharat Intelligence Layer (BIL §1-4) ---
    enable_bharat_intelligence: bool = field(
        default_factory=lambda: _env_bool("ENABLE_BHARAT_INTELLIGENCE", True)
    )
    enable_indictrans2: bool = field(
        default_factory=lambda: _env_bool("ENABLE_INDICTRANS2", False)
    )
    bharat_tier_override: str = field(
        default_factory=lambda: os.getenv("BHARAT_TIER_OVERRIDE", "auto")
    )

    # --- Pipeline hyperparameters ---
    retrieval_top_k: int = field(default_factory=lambda: _env_int("RETRIEVAL_TOP_K", 100))
    rerank_top_k: int = field(default_factory=lambda: _env_int("RERANK_TOP_K", 30))
    shortlist_size: int = field(default_factory=lambda: _env_int("SHORTLIST_SIZE", 20))
    near_miss_band_size: int = field(default_factory=lambda: _env_int("NEAR_MISS_BAND_SIZE", 20))

    # --- Submission Mode (Redrob Hackathon) ---
    submission_mode: bool = field(default_factory=lambda: _env_bool("SUBMISSION_MODE", False))
    submission_candidates_path: str = field(
        default_factory=lambda: os.getenv(
            "SUBMISSION_CANDIDATES_PATH",
            "polyhire-redrob/data/candidates.jsonl",
        )
    )
    submission_output_path: str = field(
        default_factory=lambda: os.getenv(
            "SUBMISSION_OUTPUT_PATH",
            "polyhire-redrob/team_xcution.csv",
        )
    )
    submission_top_k: int = field(default_factory=lambda: _env_int("SUBMISSION_TOP_K", 100))
    polyhire_redrob_root: str = field(default_factory=lambda: os.getenv("POLYHIRE_REDROB_ROOT", ""))
    submission_ranker_backend: str = field(
        default_factory=lambda: os.getenv("SUBMISSION_RANKER_BACKEND", "v2")
    )

    # --- Paths ---
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2])
    output_dir: Path = field(default_factory=lambda: Path("output"))
    data_dir: Path = field(default_factory=lambda: Path("data"))

    @property
    def ml_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.data_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
