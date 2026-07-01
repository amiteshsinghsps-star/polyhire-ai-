#!/usr/bin/env python3
"""
Seed the candidate database with the challenge dataset or a synthetic pool.

Usage:
    python scripts/seed_dataset.py                          # synthesizes 240 candidates
    python scripts/seed_dataset.py --dataset data/candidates.json  # load from file
    python scripts/seed_dataset.py --n 500                   # synthesize 500 candidates
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "ml-service"))

from app.dataset import load_dataset, synthesize_pool
from app.schemas import CandidateProfile


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the PolyHire candidate pool.")
    parser.add_argument("--dataset", default=None, help="Path to candidate dataset (JSON/JSONL/CSV).")
    parser.add_argument("--n", type=int, default=240, help="Number of synthetic candidates to generate.")
    parser.add_argument("--output", default="data/candidates.json", help="Output path.")
    args = parser.parse_args()

    if args.dataset:
        profiles = load_dataset(args.dataset)
    else:
        profiles = synthesize_pool(n=args.n, seed=42)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize: drop profile_text (recomputed at runtime) and flatten metadata.
    rows = []
    for p in profiles:
        d = p.model_dump()
        d.pop("profile_text", None)
        rows.append(d)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"candidates": rows, "count": len(rows)}, f, indent=2, ensure_ascii=False)

    print(f"✓ Wrote {len(profiles)} candidates to {out_path}")
    print(f"  Domains: backend, frontend, data, ml, devops, mobile")
    print(f"  ~5%% flagged as anomalous for trust-score testing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
