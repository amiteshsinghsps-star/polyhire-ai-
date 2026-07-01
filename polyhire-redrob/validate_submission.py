#!/usr/bin/env python3
"""Validate submission CSV format against candidates pool."""
from __future__ import annotations
import csv
import gzip
import json
import sys
from pathlib import Path


def load_candidate_ids(path: str) -> set[str]:
    opener = gzip.open if path.endswith(".gz") else open
    ids: set[str] = set()
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ids.add(json.loads(line)["candidate_id"])
    return ids


def validate(csv_path: str, candidates_path: str) -> list[str]:
    errors: list[str] = []
    pool_ids = load_candidate_ids(candidates_path)

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["candidate_id", "rank", "score", "reasoning"]:
            errors.append(f"Invalid header: {reader.fieldnames}")
        rows = list(reader)

    if len(rows) != 100:
        errors.append(f"Expected 100 rows, got {len(rows)}")

    ranks = [int(r["rank"]) for r in rows]
    if sorted(ranks) != list(range(1, 101)):
        errors.append("Ranks must be 1-100 each used exactly once")

    seen_ids: set[str] = set()
    prev_score = float("inf")
    for r in rows:
        cid = r["candidate_id"]
        if cid not in pool_ids:
            errors.append(f"Unknown candidate_id: {cid}")
        if cid in seen_ids:
            errors.append(f"Duplicate candidate_id: {cid}")
        seen_ids.add(cid)
        score = float(r["score"])
        if score > prev_score + 1e-9:
            errors.append(f"Score not non-increasing at rank {r['rank']}")
        prev_score = score
        if not r["reasoning"].strip():
            errors.append(f"Empty reasoning at rank {r['rank']}")

    return errors


def main():
    if len(sys.argv) < 3:
        print("Usage: python validate_submission.py submission.csv candidates.jsonl")
        sys.exit(1)
    errors = validate(sys.argv[1], sys.argv[2])
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    print("PASS: submission format valid")


if __name__ == "__main__":
    main()
