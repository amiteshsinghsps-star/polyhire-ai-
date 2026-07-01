"""
Bridge to polyhire-redrob/ PRD v2.0 submission ranker.

Used by SubmissionRanker (in-process scoring) and run_submission_mode (full CSV via rank.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

import numpy as np

_V2_ROOT: Path | None = None
_V2_ENGINE: tuple | None = None  # (FusionRanker, HoneypotDetector, generate_reasoning)


def polyhire_redrob_root() -> Path:
    global _V2_ROOT
    if _V2_ROOT is not None:
        return _V2_ROOT
    env = os.getenv("POLYHIRE_REDROB_ROOT", "").strip()
    if env:
        _V2_ROOT = Path(env).resolve()
    else:
        # .../services/ml-service/app/stages -> repo root
        _V2_ROOT = Path(__file__).resolve().parents[4] / "polyhire-redrob"
    return _V2_ROOT


def _ensure_import_path() -> Path:
    root = polyhire_redrob_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def _lexical_jaccard(text: str, statements: list[str]) -> float:
    text_tokens = set(text.lower().split())
    if not text_tokens:
        return 0.0
    best = 0.0
    for stmt in statements:
        stmt_tokens = set(stmt.lower().split())
        inter = len(text_tokens & stmt_tokens)
        union = len(text_tokens | stmt_tokens) or 1
        best = max(best, inter / union)
    return best


def build_embed_sim_fn(root: Path) -> Callable[..., float]:
    embed_path = root / "data" / "candidate_embeddings.npy"
    jd_path = root / "data" / "jd_statement_embeddings.npy"
    id_path = root / "data" / "candidate_id_order.json"

    if embed_path.exists() and jd_path.exists() and id_path.exists():
        matrix = np.load(embed_path)
        jd_matrix = np.load(jd_path)
        id_order = json.loads(id_path.read_text(encoding="utf-8"))
        id_to_row = {cid: i for i, cid in enumerate(id_order)}

        def sim_fn(text: str, statements: list[str], candidate_id: str | None = None) -> float:
            if candidate_id and candidate_id in id_to_row:
                row = matrix[id_to_row[candidate_id]]
                return float(np.max(jd_matrix @ row))
            return _lexical_jaccard(text, statements)

        return sim_fn

    return lambda text, statements, candidate_id=None: _lexical_jaccard(text, statements)


def get_v2_engine(pool_max_exposure: float = 1.0):
    """Lazy singleton: FusionRanker + HoneypotDetector class + reasoning fn."""
    global _V2_ENGINE
    if _V2_ENGINE is not None:
        ranker, detector_cls, gen_reasoning = _V2_ENGINE
        return ranker, detector_cls(), gen_reasoning

    root = _ensure_import_path()
    from polyhire.bharat.contextualizer import BharatContextualizer
    from polyhire.fusion import FusionRanker
    from polyhire.reasoning import generate_reasoning
    from polyhire.security.honeypot_detector import HoneypotDetector

    inst = root / "data" / "bharat" / "institution_tiers.json"
    lex = root / "data" / "bharat" / "hinglish_lexicon.json"
    bharat = BharatContextualizer(str(inst), str(lex))
    ranker = FusionRanker(build_embed_sim_fn(root), bharat, pool_max_exposure=pool_max_exposure)
    _V2_ENGINE = (ranker, HoneypotDetector, generate_reasoning)
    return ranker, HoneypotDetector(), generate_reasoning


def run_rank_py(
    candidates_path: str | Path,
    output_path: str | Path,
    *,
    top_n: int = 100,
    cwd: Path | None = None,
) -> Path:
    """Run polyhire-redrob/rank.py as subprocess (Stage 3 reproduction path)."""
    root = polyhire_redrob_root()
    rank_script = root / "rank.py"
    if not rank_script.exists():
        raise FileNotFoundError(f"polyhire-redrob rank.py not found at {rank_script}")

    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(rank_script),
        "--candidates",
        str(Path(candidates_path).resolve()),
        "--out",
        str(out),
        "--top-n",
        str(top_n),
    ]
    result = subprocess.run(cmd, cwd=str(cwd or root), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"polyhire-redrob rank.py failed (exit {result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return out
