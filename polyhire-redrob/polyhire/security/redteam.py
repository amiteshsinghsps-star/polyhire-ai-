"""
Adversarial Honeypot Red-Team Suite for PolyHire.

Generates synthetic borderline/mutated candidate profiles designed to probe
the HoneypotDetector's blind spots. Each mutation strategy attacks a specific
detection boundary without triggering the obvious impossibility rules.

Run as a module:
    python -m polyhire.security.redteam

Output: prints a per-strategy detection report and writes redteam_report.md.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from .honeypot_detector import HoneypotDetector, build_company_first_seen


# ─── Mutation Strategies ────────────────────────────────────────────────────

def _base_clean_candidate(n: int) -> dict[str, Any]:
    """Template of a fully clean, plausible candidate."""
    return {
        "candidate_id": f"REDTEAM_{n:05d}",
        "profile": {
            "anonymized_name": f"Candidate {n}",
            "headline": "ML Engineer",
            "location": "Pune",
            "years_of_experience": 5,
            "current_title": "Machine Learning Engineer",
            "current_company": f"LegitCorp_{n}",
        },
        "career_history": [
            {
                "company": f"LegitCorp_{n}",
                "title": "ML Engineer",
                "start_date": "2021-01-01",
                "end_date": None,
                "duration_months": 65,
                "is_current": True,
                "description": "Built production retrieval systems using vector search.",
            },
            {
                "company": f"EarlyCorp_{n}",
                "title": "Software Engineer",
                "start_date": "2017-06-01",
                "end_date": "2021-01-01",
                "duration_months": 43,
                "is_current": False,
                "description": "Developed backend services.",
            },
        ],
        "education": [
            {
                "institution": "NIT Pune",
                "degree": "B.Tech",
                "field_of_study": "CS",
                "start_year": 2013,
                "end_year": 2017,
            }
        ],
        "skills": [
            {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 60},
            {"name": "FAISS", "proficiency": "intermediate", "endorsements": 5, "duration_months": 30},
        ],
        "redrob_signals": {
            "profile_completeness_score": 80,
            "open_to_work_flag": True,
            "last_active_date": "2026-06-20",
        },
    }


def _strategy_keyword_stuffing(n: int, threshold_expert_count: int = 4) -> dict:
    """Sub-threshold keyword stuffing: just below expert count rule (rule 2 fires at >= 5)."""
    c = _base_clean_candidate(n)
    # Add exactly 4 expert skills with ≤2 months — one below the 5-skill threshold
    c["skills"] = [
        {"name": skill, "proficiency": "expert", "endorsements": 0, "duration_months": 2}
        for skill in ["Python", "Go", "Rust", "C++"][:threshold_expert_count]
    ]
    return c


def _strategy_plausible_fabricated_timeline(n: int) -> dict:
    """Career timeline with no individual impossibility but suspiciously clean overlaps."""
    c = _base_clean_candidate(n)
    # Tenure gap of exactly 0 months between every role — borderline plausible
    c["career_history"] = [
        {
            "company": f"Corp_{n}_A",
            "title": "ML Engineer",
            "start_date": "2023-01-01",
            "end_date": None,
            "duration_months": 41,
            "is_current": True,
            "description": "production ranking system",
        },
        {
            "company": f"Corp_{n}_B",
            "title": "Software Engineer",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01",
            "duration_months": 36,
            "is_current": False,
            "description": "backend development",
        },
        {
            "company": f"Corp_{n}_C",
            "title": "Junior Developer",
            "start_date": "2017-01-01",
            "end_date": "2020-01-01",
            "duration_months": 36,
            "is_current": False,
            "description": "junior dev",
        },
    ]
    c["profile"]["years_of_experience"] = 9
    return c


def _strategy_institution_tier_gaming(n: int) -> dict:
    """IIT claim with nearly empty profile otherwise."""
    c = _base_clean_candidate(n)
    c["education"] = [
        {
            "institution": "IIT Bombay",
            "degree": "B.Tech",
            "field_of_study": "CS",
            "start_year": 2015,
            "end_year": 2019,
        }
    ]
    # Gutted career history — minimal experience
    c["career_history"] = [
        {
            "company": f"Startup_{n}",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "end_date": None,
            "duration_months": 72,
            "is_current": True,
            "description": "general software work",
        }
    ]
    c["skills"] = [
        {"name": "Python", "proficiency": "intermediate", "endorsements": 2, "duration_months": 24}
    ]
    return c


def _strategy_hollow_jd_mirror(n: int, jd_keywords: list[str] | None = None) -> dict:
    """Score-maximising but semantically hollow: verbatim JD keyword repetition."""
    jd_keywords = jd_keywords or [
        "retrieval", "ranking", "embeddings", "vector database", "production",
        "NDCG", "MRR", "search", "recommendation", "fine-tuning",
    ]
    blob = " ".join(jd_keywords * 5)
    c = _base_clean_candidate(n)
    for role in c["career_history"]:
        role["description"] = blob  # pure keyword stuffing, no narrative
    c["profile"]["summary"] = blob
    return c


def _strategy_engagement_inflation(n: int) -> dict:
    """Very high recruiter-engagement metrics with an otherwise weak profile."""
    c = _base_clean_candidate(n)
    c["skills"] = [
        {"name": "Excel", "proficiency": "intermediate", "endorsements": 1, "duration_months": 12}
    ]
    c["career_history"] = [
        {
            "company": f"Agency_{n}",
            "title": "HR Coordinator",
            "start_date": "2020-01-01",
            "end_date": None,
            "duration_months": 77,
            "is_current": True,
            "description": "coordination work",
        }
    ]
    c["redrob_signals"].update({
        "profile_views_received_30d": 9999,
        "recruiter_response_rate": 1.0,
        "applications_submitted_30d": 50,
        "interview_completion_rate": 1.0,
        "offer_acceptance_rate": 1.0,
        "saved_by_recruiters_30d": 200,
    })
    return c


# ─── Strategy Registry ───────────────────────────────────────────────────────

STRATEGIES: dict[str, Any] = {
    "sub_threshold_keyword_stuffing": _strategy_keyword_stuffing,
    "plausible_fabricated_timeline":  _strategy_plausible_fabricated_timeline,
    "institution_tier_gaming":        _strategy_institution_tier_gaming,
    "hollow_jd_mirror":               _strategy_hollow_jd_mirror,
    "engagement_inflation":           _strategy_engagement_inflation,
}


# ─── Harness ─────────────────────────────────────────────────────────────────

def run_adversarial_suite(
    detector: HoneypotDetector | None = None,
    n_per_strategy: int = 200,
    out_report: str | None = "redteam_report.md",
) -> dict[str, dict]:
    """Run every mutation strategy and report detection rates per strategy.

    Parameters
    ----------
    detector:
        Pre-built HoneypotDetector. If None, one is instantiated with an
        empty company_first_seen (worst-case for rule 1).
    n_per_strategy:
        How many synthetic candidates to generate per strategy.
    out_report:
        Path to write the markdown report. None = skip file write.

    Returns
    -------
    Dict: strategy_name -> {detected: int, evaded: int, detection_rate: float,
                            evaded_rules_breakdown: dict}
    """
    detector = detector or HoneypotDetector(company_first_seen={})

    results: dict[str, dict] = {}

    for strategy_name, factory_fn in STRATEGIES.items():
        detected = 0
        evaded = 0
        rule_freq: dict[str, int] = {}

        for i in range(n_per_strategy):
            candidate = factory_fn(i)
            result = detector.check(candidate)
            if result.is_honeypot:
                detected += 1
                for rule in result.triggered_rules:
                    rule_freq[rule] = rule_freq.get(rule, 0) + 1
            else:
                evaded += 1

        results[strategy_name] = {
            "detected":        detected,
            "evaded":          evaded,
            "detection_rate":  round(detected / n_per_strategy, 4),
            "triggered_rules": rule_freq,
        }

    if out_report:
        _write_report(results, n_per_strategy, out_report)

    return results


def _write_report(results: dict, n_per_strategy: int, path: str) -> None:
    lines = [
        "# PolyHire Honeypot Red-Team Report",
        "",
        f"**n_per_strategy:** {n_per_strategy}  ",
        "**Purpose:** Adversarial probe of HoneypotDetector blind spots.  ",
        "**Interpretation:** Higher detection_rate = detector catches this attack.  ",
        "  Lower rate = known blind spot requiring hardening.",
        "",
        "| Strategy | Detected | Evaded | Detection Rate | Status |",
        "|-|-|-|-|-|",
    ]
    for name, r in results.items():
        dr = r["detection_rate"]
        status = "PASS" if dr >= 0.80 else ("WARN" if dr >= 0.40 else "FAIL")
        lines.append(
            f"| {name} | {r['detected']} | {r['evaded']} | {dr:.0%} | {status} |"
        )

    lines += ["", "## Triggered Rules Breakdown", ""]
    for name, r in results.items():
        lines.append(f"### {name}")
        if r["triggered_rules"]:
            for rule, count in sorted(r["triggered_rules"].items(), key=lambda x: -x[1]):
                lines.append(f"- `{rule}`: {count} times")
        else:
            lines.append("- No rules triggered (all evaded).")
        lines.append("")

    lines += [
        "## Hardening Recommendations",
        "",
        "Strategies with detection_rate < 80% represent known gaps.",
        "Suggested fixes:",
        "",
        "- **sub_threshold_keyword_stuffing**: Lower rule-2 threshold from 5 to 4.",
        "- **hollow_jd_mirror**: Add semantic coherence check (description ÷ unique_words ratio).",
        "- **engagement_inflation**: Cap signal contribution to final score at a hard ceiling.",
        "- **institution_tier_gaming**: Require minimum career substance alongside tier-1 claim.",
        "- **plausible_fabricated_timeline**: Add round-number tenure check (see timeline.py).",
    ]

    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[redteam] report written to {path}", file=sys.stderr)


# ─── CLI entry-point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PolyHire Honeypot Red-Team Suite")
    parser.add_argument("--n", type=int, default=200, help="Candidates per strategy")
    parser.add_argument("--out", default="redteam_report.md", help="Output markdown report path")
    args = parser.parse_args()

    results = run_adversarial_suite(n_per_strategy=args.n, out_report=args.out)

    print("\n=== Adversarial Red-Team Results ===")
    for name, r in results.items():
        status = "PASS" if r["detection_rate"] >= 0.80 else ("WARN" if r["detection_rate"] >= 0.40 else "FAIL")
        print(f"  [{status}] {name:<40} detection={r['detection_rate']:.0%}")
