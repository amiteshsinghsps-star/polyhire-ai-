"""Template-grounded, hallucination-safe reasoning generator."""
from __future__ import annotations

CAVEAT_LABELS = {
    "pure_research_career": "limited production deployment history",
    "recent_llm_only_experience": "recent AI exposure is LLM-tooling only, no deeper IR/ML history",
    "leadership_drift": "primarily in an architecture/leadership role recently",
    "pure_consulting_career": "career entirely within consulting/services firms",
    "no_nlp_ir_exposure": "background is CV/speech/robotics, limited NLP/IR exposure",
    "no_external_validation": "no public/open-source validation of technical depth",
}


def _role_family_phrase(candidate: dict) -> str:
    return candidate.get("profile", {}).get("current_title", "professional")


def _top_evidence_phrase(candidate: dict) -> str:
    history = candidate.get("career_history", [])
    if not history:
        return "a relevant technical background"
    desc = sorted(history, key=lambda r: r.get("start_date", ""), reverse=True)[0].get("description", "")
    if not desc:
        return f"experience at {history[0].get('company', 'their current company')}"
    first_sentence = desc.split(".")[0].strip()
    return first_sentence[:140].rstrip(",;") if first_sentence else "relevant production experience"


def generate_reasoning(candidate: dict, score_breakdown: dict) -> str:
    years = candidate.get("profile", {}).get("years_of_experience", 0) or 0
    role_family = _role_family_phrase(candidate)
    evidence = _top_evidence_phrase(candidate)
    location = candidate.get("profile", {}).get("location", "")
    signals = candidate.get("redrob_signals", {})

    behavioral_clause = ""
    if score_breakdown["behavioral_multiplier"] >= 1.0:
        behavioral_clause = "strong recent engagement; "
    elif score_breakdown["behavioral_multiplier"] <= 0.6:
        behavioral_clause = "limited recent platform activity — verify availability; "

    location_clause = f"{location}-based. " if location else ""

    caveat_clause = ""
    if score_breakdown["triggered_rules"]:
        worst = score_breakdown["triggered_rules"][0]
        caveat_clause = f"Note: {CAVEAT_LABELS.get(worst, worst)}."
    elif (signals.get("notice_period_days") or 0) > 60:
        caveat_clause = f"Notice period {signals.get('notice_period_days')} days."

    sentence = f"{years:.1f}y {role_family} — {evidence}. {behavioral_clause}{location_clause}{caveat_clause}".strip()
    sentence = " ".join(sentence.split())
    return sentence[:300]


def deduplicate_reasoning(rows: list[dict]) -> list[dict]:
    seen: dict[str, int] = {}
    for row in rows:
        key = row["reasoning"][:60].lower()
        if key in seen:
            history = row["_candidate"].get("career_history", [])
            if len(history) > 1:
                alt = history[1].get("description", "").split(".")[0][:140]
                row["reasoning"] = f"{row['reasoning'].split('.')[0]}; also {alt}."
        seen[key] = seen.get(key, 0) + 1
    return rows
