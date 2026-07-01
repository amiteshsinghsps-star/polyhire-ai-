"""CSV output writer per submission_spec.md format.

write_submission_csv  -> exactly 4 spec-mandated cols, passes validate_submission.py
write_debug_csv       -> all columns including advanced features (Shapley, conformal, stability)
"""
from __future__ import annotations

import csv
from pathlib import Path

# Submission spec: exactly these 4 columns in this order
_SUBMISSION_COLUMNS = ["candidate_id", "rank", "score", "reasoning"]

# Advanced debug columns (written only to debug CSV)
_DEBUG_EXTRA = [
    "_final_score",
    "rank_stability",
    "top_contributor",
    "shapley_breakdown",
    "confidence_interval",
]


def write_submission_csv(rows: list[dict], out_path: str | Path) -> None:
    """Write the spec-valid submission CSV with exactly 4 columns.

    Silently ignores any extra keys in rows so the file always passes
    validate_submission.py regardless of which advanced flags were set.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_SUBMISSION_COLUMNS)
        for row in rows:
            writer.writerow([
                row["candidate_id"],
                row["rank"],
                row["score"],
                row["reasoning"],
            ])


def write_debug_csv(rows: list[dict], out_path: str | Path) -> None:
    """Write a full debug CSV containing base + advanced columns.

    Only columns that are actually populated on at least one row are written.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    active_extra = [
        col for col in _DEBUG_EXTRA
        if any(col in row for row in rows)
    ]
    fieldnames = _SUBMISSION_COLUMNS + active_extra

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in fieldnames})
