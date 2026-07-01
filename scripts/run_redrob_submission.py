#!/usr/bin/env python3
"""
Run Redrob hackathon submission (Phase B) from repo root.

  python scripts/run_redrob_submission.py
  python scripts/run_redrob_submission.py --candidates polyhire-redrob/data/candidates.jsonl.gz

Delegates to polyhire-redrob/rank.py (PRD v2.0). Same command judges reproduce at Stage 3.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLYHIRE_REDROB = REPO_ROOT / "polyhire-redrob"


def main() -> int:
    parser = argparse.ArgumentParser(description="PolyHire AI — Redrob submission CSV generator")
    parser.add_argument(
        "--candidates",
        default=str(POLYHIRE_REDROB / "data" / "candidates.jsonl"),
        help="Path to candidates.jsonl or .jsonl.gz",
    )
    parser.add_argument(
        "--out",
        default=str(POLYHIRE_REDROB / "team_xcution.csv"),
        help="Output CSV path",
    )
    parser.add_argument("--top-n", type=int, default=100)
    args = parser.parse_args()

    cand = Path(args.candidates)
    if not cand.is_file() and Path(str(cand) + ".gz").is_file():
        cand = Path(str(cand) + ".gz")
    if not cand.is_file():
        print(
            f"ERROR: Candidate file not found: {args.candidates}\n"
            "Download the 100K pool from Redrob and save to polyhire-redrob/data/candidates.jsonl.gz",
            file=sys.stderr,
        )
        return 1

    sys.path.insert(0, str(REPO_ROOT / "services" / "ml-service"))
    from app.stages.v2_ranker_bridge import run_rank_py

    try:
        out = run_rank_py(cand, args.out, top_n=args.top_n)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Submission CSV written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
