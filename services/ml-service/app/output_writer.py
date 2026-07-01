"""
Submission output writer.

Emits the ranked shortlist in the organizers' predefined submission format
to output/ranked_shortlist.json — the required submission artifact.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings
from .schemas import SubmissionEntry, SubmissionOutput


def write_ranked_output(
    result: dict[str, Any] | Any,
    path: str | Path | None = None,
) -> Path:
    """
    Write the ranked shortlist to disk in the submission format.

    Accepts either a raw dict (PipelineResult.model_dump()) or a PipelineResult
    pydantic instance. Returns the path written.
    """
    settings = get_settings()
    out_path = Path(path) if path else (settings.output_dir / "ranked_shortlist.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(result, "model_dump"):
        data = result.model_dump()
    else:
        data = dict(result)

    shortlist_entries = [
        SubmissionEntry(
            rank=int(r["rank"]),
            candidate_id=str(r["candidate_id"]),
            relevance_score=round(float(r["score"]), 4),
            justification=str(r.get("explanation", "")),
        ).model_dump()
        for r in data.get("ranked_shortlist", [])
    ]

    output = SubmissionOutput(
        generated_at=datetime.now(timezone.utc).isoformat(),
        job_description=data.get("structured_jd", {}),
        shortlist=shortlist_entries,
    )

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(output.model_dump(), f, indent=2, ensure_ascii=False)

    return out_path


def write_submission_csv(
    top_candidates: list[dict[str, Any]], 
    path: str | Path | None = None
) -> Path:
    """
    Write the ranked shortlist to a CSV file per the Redrob hackathon spec.
    """
    import csv
    settings = get_settings()
    out_path = Path(path) if path else Path(settings.submission_output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, c in enumerate(top_candidates):
            rank = i + 1
            writer.writerow([
                c.get("candidate_id"), 
                rank, 
                f"{c.get('score', 0.0):.4f}", 
                c.get("reasoning", "")
            ])
            
    return out_path
