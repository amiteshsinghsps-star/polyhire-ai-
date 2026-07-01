import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_rank_py_produces_valid_format(sample_candidate, honeypot_candidate, tmp_path):
    candidates_path = tmp_path / "candidates.jsonl"
    rows = [sample_candidate, honeypot_candidate]
    for i in range(2, 120):
        c = dict(sample_candidate)
        c["candidate_id"] = f"CAND_{i:07d}"
        rows.append(c)
    with open(candidates_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    out_path = tmp_path / "submission.csv"
    subprocess.run(
        [sys.executable, "rank.py", "--candidates", str(candidates_path), "--out", str(out_path)],
        check=True,
        cwd=ROOT,
    )

    with open(out_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows_out = list(reader)

    assert len(rows_out) == 100
    assert reader.fieldnames == ["candidate_id", "rank", "score", "reasoning"]
    ranks = [int(r["rank"]) for r in rows_out]
    assert sorted(ranks) == list(range(1, 101))
    assert "CAND_9999999" not in [r["candidate_id"] for r in rows_out]
    scores = [float(r["score"]) for r in rows_out]
    assert scores == sorted(scores, reverse=True)
