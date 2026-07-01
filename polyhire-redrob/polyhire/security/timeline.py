"""
Timeline Consistency Diagnostic — population-level data health checks.

Checks
------
1. round_number_tenure_check: Flags candidates with suspiciously round tenures.
   Real career data has messy fractional tenures; templated/fabricated data
   clusters on exact integers (12, 24, 36, 48 months).

2. inter_arrival_plausibility: Checks whether gaps between consecutive roles
   are suspiciously uniform (all exactly 0 or 1 month), which is a signature
   of generated rather than organic data.

3. benford_population_check: Population-level Benford's law check on numeric
   fields (years_of_experience). IMPORTANT: used at DATASET level only —
   never as a per-candidate honeypot score (that would be a statistical misuse).

Run as a module:
    python -m polyhire.security.timeline --candidates data/candidates.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence


# ─── Feature 1: Round-number tenure check ───────────────────────────────────

def round_tenure_score(candidate: dict) -> float:
    """Return fraction of this candidate's role tenures that are suspiciously round.

    'Round' = divisible by 12 (exactly N years) or by 6 (half-year).
    Returns 0.0 for candidates with no history.
    """
    tenures = [
        r.get("duration_months", 0) or 0
        for r in candidate.get("career_history", [])
    ]
    tenures = [t for t in tenures if t > 0]
    if not tenures:
        return 0.0
    n_round = sum(1 for t in tenures if t % 6 == 0)
    return round(n_round / len(tenures), 4)


def population_round_tenure_report(candidates: list[dict]) -> dict:
    """Report round-tenure statistics across the full candidate pool."""
    scores = [round_tenure_score(c) for c in candidates]
    fully_round = sum(1 for s in scores if s == 1.0)
    mostly_round = sum(1 for s in scores if s >= 0.75)
    return {
        "n_candidates": len(candidates),
        "fully_round_pct": round(fully_round / max(len(candidates), 1), 4),
        "mostly_round_pct": round(mostly_round / max(len(candidates), 1), 4),
        "mean_round_score": round(sum(scores) / max(len(scores), 1), 4),
        "interpretation": (
            "SYNTHETIC_SUSPECTED" if fully_round / max(len(candidates), 1) > 0.60
            else "ORGANIC_PLAUSIBLE"
        ),
    }


# ─── Feature 2: Inter-arrival plausibility ──────────────────────────────────

def _parse_yyyymm(date_str: str | None) -> int | None:
    """Parse YYYY-MM-DD to an integer month count from epoch (2000-01)."""
    if not date_str:
        return None
    try:
        y, m = int(date_str[:4]), int(date_str[5:7])
        return (y - 2000) * 12 + m
    except Exception:
        return None


def inter_arrival_gaps(candidate: dict) -> list[int]:
    """Return sorted list of gap months between consecutive role end→next start."""
    roles = sorted(
        [r for r in candidate.get("career_history", []) if r.get("start_date")],
        key=lambda r: r["start_date"],
    )
    gaps = []
    for i in range(len(roles) - 1):
        end = _parse_yyyymm(roles[i].get("end_date"))
        start = _parse_yyyymm(roles[i + 1].get("start_date"))
        if end is not None and start is not None:
            gaps.append(max(0, start - end))
    return gaps


def population_inter_arrival_report(candidates: list[dict]) -> dict:
    """Report on suspicious uniformity of career-transition gaps."""
    all_gaps: list[int] = []
    zero_gap_candidates = 0

    for c in candidates:
        gaps = inter_arrival_gaps(c)
        all_gaps.extend(gaps)
        if gaps and all(g == 0 for g in gaps):
            zero_gap_candidates += 1

    gap_counts = Counter(all_gaps)
    most_common = gap_counts.most_common(5)

    return {
        "n_transitions": len(all_gaps),
        "zero_gap_pct": round(gap_counts.get(0, 0) / max(len(all_gaps), 1), 4),
        "all_zero_gap_candidates_pct": round(
            zero_gap_candidates / max(len(candidates), 1), 4
        ),
        "most_common_gaps": [{"gap_months": g, "count": cnt} for g, cnt in most_common],
        "interpretation": (
            "SYNTHETIC_SUSPECTED"
            if gap_counts.get(0, 0) / max(len(all_gaps), 1) > 0.80
            else "ORGANIC_PLAUSIBLE"
        ),
    }


# ─── Feature 3: Benford's Law population check ──────────────────────────────
# IMPORTANT: population-level only — do NOT use per candidate.

_BENFORD_EXPECTED = {
    1: 0.3010, 2: 0.1761, 3: 0.1249, 4: 0.0969,
    5: 0.0792, 6: 0.0669, 7: 0.0580, 8: 0.0512, 9: 0.0458,
}


def benford_first_digit_check(values: list[float]) -> dict:
    """Benford's Law check on a list of numeric values.

    Parameters
    ----------
    values:
        List of positive numeric values (e.g. years_of_experience across full pool).

    Returns
    -------
    Dict with observed frequencies, chi-squared statistic, and interpretation.

    WARNING: This is a POPULATION-LEVEL diagnostic. Do not run per-candidate.
    """
    first_digits = []
    for v in values:
        s = str(int(abs(v))).lstrip("0")
        if s:
            first_digits.append(int(s[0]))

    if not first_digits:
        return {"error": "no valid values"}

    n = len(first_digits)
    observed = Counter(first_digits)
    obs_freq = {d: observed.get(d, 0) / n for d in range(1, 10)}

    # Chi-squared goodness-of-fit
    chi2 = sum(
        n * (obs_freq.get(d, 0) - _BENFORD_EXPECTED[d]) ** 2 / _BENFORD_EXPECTED[d]
        for d in range(1, 10)
    )

    return {
        "n_values": n,
        "chi2_statistic": round(chi2, 4),
        "chi2_critical_p01": 20.09,  # chi2 df=8, p=0.01
        "benford_violated": chi2 > 20.09,
        "observed_freq": {d: round(obs_freq.get(d, 0), 4) for d in range(1, 10)},
        "expected_freq": _BENFORD_EXPECTED,
        "interpretation": (
            "POPULATION_SYNTHETIC_SUSPECTED (chi2 > critical, dataset may be generated)"
            if chi2 > 20.09
            else "BENFORD_CONSISTENT (dataset appears organically distributed)"
        ),
    }


# ─── Full diagnostic runner ──────────────────────────────────────────────────

def run_timeline_diagnostics(candidates: list[dict]) -> dict:
    """Run all three checks and return a combined report dict."""
    yoe_values = [
        float(c.get("profile", {}).get("years_of_experience", 0) or 0)
        for c in candidates
        if c.get("profile", {}).get("years_of_experience")
    ]

    return {
        "round_tenure":    population_round_tenure_report(candidates),
        "inter_arrival":   population_inter_arrival_report(candidates),
        "benford_yoe":     benford_first_digit_check(yoe_values),
        "dataset_verdict": _overall_verdict(
            population_round_tenure_report(candidates),
            population_inter_arrival_report(candidates),
            benford_first_digit_check(yoe_values),
        ),
    }


def _overall_verdict(tenure: dict, arrival: dict, benford: dict) -> str:
    flags = [
        tenure.get("interpretation") == "SYNTHETIC_SUSPECTED",
        arrival.get("interpretation") == "SYNTHETIC_SUSPECTED",
        benford.get("benford_violated", False),
    ]
    n_flags = sum(flags)
    if n_flags >= 2:
        return "DATASET_LIKELY_SYNTHETIC"
    elif n_flags == 1:
        return "DATASET_PARTIALLY_SUSPECT"
    return "DATASET_APPEARS_ORGANIC"


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PolyHire Timeline Consistency Diagnostics")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", default="timeline_diagnostic.json", help="Output JSON path")
    args = parser.parse_args()

    print(f"[timeline] Loading {args.candidates}...", file=sys.stderr)
    candidates = []
    with open(args.candidates, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    candidates.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    print(f"[timeline] Loaded {len(candidates)} candidates.", file=sys.stderr)
    report = run_timeline_diagnostics(candidates)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[timeline] Report written to {out_path}", file=sys.stderr)

    print("\n=== Timeline Diagnostic Summary ===")
    print(f"  Round tenure:   {report['round_tenure']['interpretation']}")
    print(f"  Inter-arrival:  {report['inter_arrival']['interpretation']}")
    print(f"  Benford check:  {report['benford_yoe'].get('interpretation', 'N/A')}")
    print(f"  VERDICT:        {report['dataset_verdict']}")
