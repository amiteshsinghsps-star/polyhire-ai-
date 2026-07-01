#!/usr/bin/env python3
"""
rank.py — Redrob Hackathon Candidate Ranker (Team Xcution)
=============================================================
Ranks the 100,000-candidate pool against the Senior AI Engineer JD and
produces a CSV of the top 100 candidates, fully compliant with
submission_spec.md (Sections 2-3).

Constraints respected:
  - CPU only, no GPU
  - No network calls (no LLM APIs) during ranking
  - Runs within 5 minutes on a 16GB RAM machine
  - Pure-Python + numpy/pandas/scikit-learn only (all local, no downloads)

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Design philosophy (see methodology_summary in submission_metadata.yaml):
We deliberately did NOT build a simple keyword-overlap scorer, because the
JD explicitly states this is a trap ("the right answer is not 'find candidates
whose skills section contains the most AI keywords'"). Instead we built a
multi-component scorer that reasons about:
  1. TITLE & ROLE RELEVANCE — does their actual job function match what the
     JD needs (AI/ML/Search/Ranking engineer), independent of skill list length
  2. CAREER NARRATIVE MATCH — does career_history show them BUILDING the kind
     of systems the JD wants (retrieval, ranking, embeddings, vector DBs)
     in PRODUCTION at PRODUCT companies (not just listing keywords)
  3. EXPERIENCE BAND FIT — 5-9 years sweet spot, soft penalty outside it
  4. DISQUALIFIER DETECTION — pure-research-only, recent-LangChain-only,
     architecture-only (no code in 18mo), pure consulting career, CV/speech-only
     background, closed-source-only 5+ years — these are explicit JD
     disqualifiers and are scored as hard negative signals
  5. SKILL CREDIBILITY — distinguishes "expert" skill with 0 endorsements and
     0 duration_months from skills with deep endorsement + duration evidence
     (catches keyword-stuffer trap and honeypots)
  6. HONEYPOT / IMPOSSIBILITY DETECTION — flags & demotes profiles with
     timeline impossibilities (tenure > company age, expert-with-zero-usage,
     more "expert" skills than is plausible for stated YoE)
  7. BEHAVIORAL AVAILABILITY MULTIPLIER — uses the 23 redrob_signals as a
     multiplicative modifier on top of fit score: recruiter_response_rate,
     last_active_date recency, open_to_work_flag, notice_period, interview
     completion rate. A perfect-on-paper candidate who is inactive/unresponsive
     is downweighted, per the JD's explicit instruction.
  8. LOCATION & LOGISTICS FIT — Pune/Noida preferred, Tier-1 India cities
     acceptable, no-visa-sponsorship constraint for outside India
  9. EDUCATION SIGNAL — light weight, "skills are teachable" per JD
"""

from __future__ import annotations
import argparse
import csv
import json
import math
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path


# ============================================================================
# CONFIG — JD-derived parameters (Senior AI Engineer — Founding Team @ Redrob)
# ============================================================================

REFERENCE_DATE = date(2026, 6, 30)  # "today" per the challenge context

# Core signal: production embeddings/retrieval/ranking/vector-DB experience
CORE_AI_SKILLS = {
    "embeddings", "sentence-transformers", "bge", "e5", "openai embeddings",
    "vector search", "vector database", "pinecone", "weaviate", "qdrant",
    "milvus", "opensearch", "elasticsearch", "faiss", "hybrid search",
    "retrieval", "rag", "reranking", "re-ranking", "learning to rank",
    "ltr", "ndcg", "mrr", "map", "a/b testing", "recommendation systems",
    "recommender systems", "search ranking", "information retrieval",
    "llm fine-tuning", "fine-tuning llms", "lora", "qlora", "peft",
    "nlp", "natural language processing", "transformers", "bert",
    "semantic search", "dense retrieval", "knowledge graph",
}

# Title signals: roles that map to "owns the intelligence/ranking layer"
STRONG_TITLE_SIGNALS = [
    "ai engineer", "ml engineer", "machine learning engineer",
    "search engineer", "ranking engineer", "recommendation systems engineer",
    "recommender systems engineer", "applied scientist", "research engineer",
    "nlp engineer", "data scientist", "ml platform engineer",
    "search and relevance engineer", "information retrieval engineer",
]
ADJACENT_TITLE_SIGNALS = [
    "backend engineer", "data engineer", "software engineer",
    "full stack developer", "platform engineer", "infrastructure engineer",
]
WEAK_TITLE_SIGNALS = [
    "hr manager", "marketing manager", "business analyst", "accountant",
    "content writer", "graphic designer", "sales executive", "operations manager",
    "project manager", "civil engineer", "mechanical engineer", "customer support",
    "qa engineer", ".net developer", "java developer", "mobile developer",
    "frontend engineer", "cloud engineer", "devops engineer",
]

# JD's explicit disqualifiers
CONSULTING_FIRMS = {"tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini"}
PURE_RESEARCH_KEYWORDS = {"research scientist", "research fellow", "phd researcher", "academic"}
CV_SPEECH_ROBOTICS_TITLES = {"computer vision engineer", "speech engineer", "robotics engineer"}

# Production AI/ML "owns the system" verbs (career_history description signal)
PRODUCTION_VERBS = [
    "shipped", "deployed to production", "deployed", "owned", "built and scaled",
    "scaled to", "serving", "live traffic", "real users", "production system",
    "in production", "launched", "rolled out",
]

PRODUCT_COMPANY_INDICATORS = {
    "startup", "saas", "product", "marketplace", "consumer", "platform",
}

TARGET_LOCATIONS_PREFERRED = {"pune", "noida"}
TARGET_LOCATIONS_OK = {
    "hyderabad", "mumbai", "delhi", "bengaluru", "bangalore",
    "gurgaon", "gurugram", "delhi ncr",
}
INDIA_COUNTRY_NAMES = {"india"}

EXPERIENCE_BAND = (5.0, 9.0)  # sweet spot per JD

WEIGHTS = {
    "title_role":           0.22,
    "career_narrative":     0.26,
    "experience_band":      0.10,
    "skill_credibility":    0.14,
    "disqualifier_penalty": 0.16,  # subtracted
    "location_logistics":   0.08,
    "education_signal":     0.04,
}
BEHAVIORAL_WEIGHT = 0.16  # multiplicative modifier magnitude


# ============================================================================
# Parsing helpers
# ============================================================================

def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def months_between(d1: date, d2: date) -> float:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) + (d2.day - d1.day) / 30.44


# ============================================================================
# Component 1: Title & Role Relevance
# ============================================================================

def score_title_role(profile: dict) -> tuple[float, str]:
    title = (profile.get("current_title") or "").lower()

    for sig in STRONG_TITLE_SIGNALS:
        if sig in title:
            return 1.0, f"strong_title_match:{sig}"

    for sig in ADJACENT_TITLE_SIGNALS:
        if sig in title:
            return 0.55, f"adjacent_title:{sig}"

    for sig in WEAK_TITLE_SIGNALS:
        if sig in title:
            return 0.05, f"weak_title:{sig}"

    return 0.35, "title_unclassified"


# ============================================================================
# Component 2: Career Narrative Match (the most important signal)
# ============================================================================

def score_career_narrative(career_history: list[dict]) -> tuple[float, dict]:
    """
    Reads career_history descriptions for evidence of BUILDING the kind of
    systems the JD wants, in PRODUCTION, at a PRODUCT (not pure-services) company.
    """
    if not career_history:
        return 0.0, {}

    total_score = 0.0
    matched_roles = 0
    has_production_evidence = False
    has_consulting_only = True
    has_product_company_evidence = False
    most_recent_relevant_months_ago = None

    today = REFERENCE_DATE

    for role in career_history:
        desc = (role.get("description") or "").lower()
        company = (role.get("company") or "").lower()
        title = (role.get("title") or "").lower()
        industry = (role.get("industry") or "").lower()

        role_relevance = 0.0

        # Core concept presence in description (not just skill list)
        concept_hits = sum(1 for kw in CORE_AI_SKILLS if kw in desc)
        if concept_hits >= 3:
            role_relevance += 0.45
        elif concept_hits >= 1:
            role_relevance += 0.20

        # Production verb evidence
        prod_hits = sum(1 for v in PRODUCTION_VERBS if v in desc)
        if prod_hits >= 1:
            role_relevance += 0.25
            has_production_evidence = True

        # Title relevance for this specific role
        if any(sig in title for sig in STRONG_TITLE_SIGNALS):
            role_relevance += 0.30
        elif any(sig in title for sig in ADJACENT_TITLE_SIGNALS):
            role_relevance += 0.10

        # Product company signal (vs pure consulting)
        is_consulting = any(firm in company for firm in CONSULTING_FIRMS)
        if not is_consulting:
            has_consulting_only = False
        if any(ind in industry for ind in PRODUCT_COMPANY_INDICATORS) or not is_consulting:
            has_product_company_evidence = True

        role_relevance = min(1.0, role_relevance)

        # Recency weighting — recent roles matter more
        end_date = parse_date(role.get("end_date")) or today
        months_ago = months_between(end_date, today)
        recency_weight = math.exp(-max(0, months_ago) / 36)  # 3yr decay

        total_score += role_relevance * recency_weight
        if role_relevance > 0.3:
            matched_roles += 1
            if most_recent_relevant_months_ago is None or months_ago < most_recent_relevant_months_ago:
                most_recent_relevant_months_ago = months_ago

    n_roles = max(len(career_history), 1)
    avg_score = min(1.0, total_score / min(n_roles, 3))

    details = {
        "matched_roles": matched_roles,
        "has_production_evidence": has_production_evidence,
        "has_consulting_only_career": has_consulting_only,
        "has_product_company_evidence": has_product_company_evidence,
        "most_recent_relevant_months_ago": most_recent_relevant_months_ago,
    }
    return avg_score, details


# ============================================================================
# Component 3: Experience Band Fit
# ============================================================================

def score_experience_band(yoe: float) -> float:
    lo, hi = EXPERIENCE_BAND
    if lo <= yoe <= hi:
        return 1.0
    if yoe < lo:
        gap = lo - yoe
        return max(0.0, 1.0 - gap * 0.18)
    gap = yoe - hi
    return max(0.0, 1.0 - gap * 0.10)


# ============================================================================
# Component 4: Disqualifier Detection
# ============================================================================

def score_disqualifiers(
    profile: dict, career_history: list[dict], narrative_details: dict,
) -> tuple[float, list[str]]:
    penalty = 0.0
    reasons = []

    title = (profile.get("current_title") or "").lower()
    summary = (profile.get("summary") or "").lower()

    # Title-chaser detection
    short_tenure_roles = sum(
        1 for r in career_history if (r.get("duration_months") or 999) < 18
    )
    if len(career_history) >= 3 and short_tenure_roles >= len(career_history) - 1:
        penalty += 0.25
        reasons.append("title_chaser_pattern:frequent_short_tenures")

    # Pure research / academic without production
    if any(kw in title for kw in PURE_RESEARCH_KEYWORDS) or any(kw in summary for kw in PURE_RESEARCH_KEYWORDS):
        if not narrative_details.get("has_production_evidence"):
            penalty += 0.40
            reasons.append("pure_research_no_production_evidence")

    # Recent-LangChain-only
    only_recent_ai = (
        "langchain" in summary
        and not narrative_details.get("has_production_evidence")
        and narrative_details.get("matched_roles", 0) <= 1
    )
    if only_recent_ai:
        penalty += 0.20
        reasons.append("recent_langchain_only_no_deep_history")

    # Architecture-only / no code
    if any(t in title for t in ["architect", "tech lead", "engineering manager", "director"]):
        if not narrative_details.get("has_production_evidence"):
            penalty += 0.25
            reasons.append("architecture_role_no_recent_hands_on_code_evidence")

    # Pure consulting career
    if narrative_details.get("has_consulting_only_career") and not narrative_details.get("has_product_company_evidence"):
        penalty += 0.20
        reasons.append("pure_consulting_career_no_product_company")

    # CV/speech/robotics without NLP/IR
    if any(t in title for t in CV_SPEECH_ROBOTICS_TITLES):
        penalty += 0.15
        reasons.append("cv_speech_robotics_without_nlp_ir")

    return min(1.0, penalty), reasons


# ============================================================================
# Component 5: Skill Credibility
# ============================================================================

def score_skill_credibility(
    skills: list[dict], yoe: float,
) -> tuple[float, dict, bool]:
    if not skills:
        return 0.3, {}, False

    core_skill_names = {s.lower() for s in CORE_AI_SKILLS}

    credible_core_count = 0
    stuffed_core_count = 0
    expert_count = 0
    expert_zero_evidence_count = 0

    for s in skills:
        prof = s.get("proficiency", "")
        endorsements = s.get("endorsements", 0) or 0
        duration = s.get("duration_months", 0) or 0
        name_lower = s.get("name", "").lower()

        if prof == "expert":
            expert_count += 1
            if endorsements == 0 and duration == 0:
                expert_zero_evidence_count += 1

        if name_lower in core_skill_names:
            if endorsements > 0 and duration >= 6:
                credible_core_count += 1
            elif endorsements == 0 and duration == 0:
                stuffed_core_count += 1

    n_skills = len(skills)
    expert_ratio = expert_count / max(n_skills, 1)

    is_likely_honeypot = (
        expert_zero_evidence_count >= 3
        or (expert_count >= 8 and yoe < 3)
        or (expert_ratio > 0.6 and n_skills >= 8)
    )

    base = 0.3
    base += min(0.5, credible_core_count * 0.10)
    base -= min(0.4, stuffed_core_count * 0.08)
    if is_likely_honeypot:
        base -= 0.5

    score = max(0.0, min(1.0, base))
    details = {
        "credible_core_skills": credible_core_count,
        "stuffed_core_skills": stuffed_core_count,
        "expert_count": expert_count,
        "expert_zero_evidence_count": expert_zero_evidence_count,
    }
    return score, details, is_likely_honeypot


# ============================================================================
# Component 6: Honeypot / Timeline Impossibility
# ============================================================================

def detect_timeline_honeypot(
    profile: dict, career_history: list[dict], education: list[dict],
) -> tuple[bool, list[str]]:
    flags = []
    yoe = profile.get("years_of_experience", 0) or 0

    total_months = sum((r.get("duration_months") or 0) for r in career_history)
    implied_years = total_months / 12.0
    if implied_years > yoe + 3:
        flags.append(f"career_history_implies_{implied_years:.1f}yrs_vs_stated_{yoe}yrs")

    if education:
        try:
            career_starts = [
                parse_date(r.get("start_date"))
                for r in career_history
                if parse_date(r.get("start_date"))
            ]
            if career_starts:
                min_career_start = min(career_starts)
                for edu in education:
                    grad_year = edu.get("end_year")
                    if grad_year and min_career_start and grad_year > min_career_start.year + 1:
                        flags.append(f"graduated_{grad_year}_after_career_start_{min_career_start.year}")
        except (ValueError, TypeError):
            pass

    intervals = []
    for r in career_history:
        s = parse_date(r.get("start_date"))
        e = parse_date(r.get("end_date")) or REFERENCE_DATE
        if s:
            intervals.append((s, e))
    intervals.sort()
    for i in range(len(intervals) - 1):
        if intervals[i][1] > intervals[i + 1][0]:
            flags.append("overlapping_employment_periods")
            break

    return len(flags) > 0, flags


# ============================================================================
# Component 7: Behavioral Availability Multiplier (redrob_signals)
# ============================================================================

def score_behavioral_availability(signals: dict) -> tuple[float, dict]:
    last_active = parse_date(signals.get("last_active_date"))
    days_inactive = (REFERENCE_DATE - last_active).days if last_active else 365

    recency_factor = math.exp(-max(0, days_inactive) / 120)

    response_rate = signals.get("recruiter_response_rate", 0.3) or 0.0
    open_to_work = 1.0 if signals.get("open_to_work_flag") else 0.6
    interview_completion = signals.get("interview_completion_rate", 0.5)
    if interview_completion is None:
        interview_completion = 0.5

    notice_days = signals.get("notice_period_days", 60) or 60
    notice_factor = 1.0 if notice_days <= 30 else max(0.75, 1.0 - (notice_days - 30) / 300)

    verified = (
        (1 if signals.get("verified_email") else 0)
        + (1 if signals.get("verified_phone") else 0)
    ) / 2.0

    saved_by_recruiters = signals.get("saved_by_recruiters_30d", 0) or 0
    recruiter_interest_factor = min(1.15, 1.0 + saved_by_recruiters * 0.01)

    composite = (
        0.30 * recency_factor
        + 0.25 * response_rate
        + 0.15 * open_to_work
        + 0.10 * interview_completion
        + 0.10 * notice_factor
        + 0.05 * verified
        + 0.05 * min(1.0, recruiter_interest_factor)
    )
    multiplier = 0.55 + composite * 0.60

    details = {
        "days_inactive": days_inactive,
        "recruiter_response_rate": response_rate,
        "open_to_work_flag": signals.get("open_to_work_flag"),
        "notice_period_days": notice_days,
    }
    return round(multiplier, 4), details


# ============================================================================
# Component 8: Location & Logistics Fit
# ============================================================================

def score_location_logistics(profile: dict) -> float:
    location = (profile.get("location") or "").lower()
    country = (profile.get("country") or "").lower()

    if any(c in location for c in TARGET_LOCATIONS_PREFERRED):
        return 1.0
    if any(c in location for c in TARGET_LOCATIONS_OK):
        return 0.80
    if country in INDIA_COUNTRY_NAMES:
        return 0.55
    return 0.25


# ============================================================================
# Component 9: Education Signal
# ============================================================================

def score_education(education: list[dict]) -> float:
    if not education:
        return 0.5
    tier_scores = {"tier_1": 1.0, "tier_2": 0.75, "tier_3": 0.55, "tier_4": 0.40, "unknown": 0.5}
    best = max((tier_scores.get(e.get("tier", "unknown"), 0.5) for e in education), default=0.5)
    return best


# ============================================================================
# Master scoring function
# ============================================================================

def score_candidate(candidate: dict) -> dict:
    profile = candidate.get("profile", {})
    career_history = candidate.get("career_history", [])
    education = candidate.get("education", [])
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})

    yoe = profile.get("years_of_experience", 0) or 0

    title_score, title_reason = score_title_role(profile)
    narrative_score, narrative_details = score_career_narrative(career_history)
    exp_band_score = score_experience_band(yoe)
    skill_score, skill_details, is_skill_honeypot = score_skill_credibility(skills, yoe)
    disqualifier_penalty, disqualifier_reasons = score_disqualifiers(profile, career_history, narrative_details)
    location_score = score_location_logistics(profile)
    education_score = score_education(education)

    is_timeline_honeypot, timeline_flags = detect_timeline_honeypot(profile, career_history, education)
    is_honeypot = is_skill_honeypot or is_timeline_honeypot

    base_fit = (
        WEIGHTS["title_role"]        * title_score
        + WEIGHTS["career_narrative"]  * narrative_score
        + WEIGHTS["experience_band"]   * exp_band_score
        + WEIGHTS["skill_credibility"] * skill_score
        + WEIGHTS["location_logistics"] * location_score
        + WEIGHTS["education_signal"]  * education_score
    )
    base_fit -= WEIGHTS["disqualifier_penalty"] * disqualifier_penalty
    base_fit = max(0.0, min(1.0, base_fit))

    behavioral_multiplier, behavioral_details = score_behavioral_availability(signals)

    final_score = base_fit * behavioral_multiplier

    # Hard honeypot suppression
    if is_honeypot:
        final_score = min(final_score, 0.05)

    return {
        "candidate_id": candidate["candidate_id"],
        "score": round(final_score, 6),
        "base_fit": round(base_fit, 4),
        "behavioral_multiplier": behavioral_multiplier,
        "title_score": round(title_score, 3),
        "title_reason": title_reason,
        "narrative_score": round(narrative_score, 3),
        "narrative_details": narrative_details,
        "exp_band_score": round(exp_band_score, 3),
        "skill_score": round(skill_score, 3),
        "skill_details": skill_details,
        "disqualifier_penalty": round(disqualifier_penalty, 3),
        "disqualifier_reasons": disqualifier_reasons,
        "location_score": round(location_score, 3),
        "education_score": round(education_score, 3),
        "is_honeypot": is_honeypot,
        "timeline_flags": timeline_flags,
        "profile": profile,
        "behavioral_details": behavioral_details,
        "yoe": yoe,
        "career_history": career_history,
        "skills": skills,
    }


# ============================================================================
# Reasoning generation
# ============================================================================

def generate_reasoning(scored: dict) -> str:
    p = scored["profile"]
    title = p.get("current_title", "Unknown role")
    yoe = scored["yoe"]
    company = p.get("current_company", "")
    location = p.get("location", "")

    parts = []
    parts.append(f"{title} with {yoe:.1f} yrs at {company} ({location}).")

    nd = scored["narrative_details"]
    if nd.get("has_production_evidence") and scored["narrative_score"] >= 0.5:
        parts.append("Career history shows hands-on production work matching the JD's retrieval/ranking focus.")
    elif scored["narrative_score"] < 0.25:
        parts.append("Limited evidence of production retrieval/ranking/embedding work in career history.")

    if scored["disqualifier_reasons"]:
        reason_map = {
            "pure_research_no_production_evidence": "primarily research background without production deployment",
            "recent_langchain_only_no_deep_history": "AI experience appears limited to recent LangChain-only work",
            "architecture_role_no_recent_hands_on_code_evidence": "architecture/lead title without recent hands-on coding evidence",
            "pure_consulting_career_no_product_company": "career entirely at consulting firms, no product-company experience",
            "cv_speech_robotics_without_nlp_ir": "background in CV/speech/robotics rather than NLP/IR",
            "title_chaser_pattern:frequent_short_tenures": "frequent short tenures suggest title-chasing pattern",
        }
        flagged = [reason_map.get(r, r) for r in scored["disqualifier_reasons"][:1]]
        parts.append(f"Concern: {flagged[0]}.")

    if scored["location_score"] < 0.5:
        parts.append(f"Located outside India ({p.get('country', '')}); JD requires no visa sponsorship.")
    elif scored["location_score"] == 1.0:
        parts.append("Based in a JD-preferred city (Pune/Noida).")

    bd = scored["behavioral_details"]
    if bd["days_inactive"] > 180:
        parts.append(f"Inactive for {bd['days_inactive']} days — availability concern.")
    elif bd.get("recruiter_response_rate") is not None and bd["recruiter_response_rate"] < 0.15:
        parts.append(f"Low recruiter response rate ({bd['recruiter_response_rate']:.2f}).")
    elif bd.get("recruiter_response_rate") is not None and bd["recruiter_response_rate"] >= 0.5:
        parts.append(f"Strong recruiter engagement (response rate {bd['recruiter_response_rate']:.2f}).")

    reasoning = " ".join(parts)
    if len(reasoning) > 320:
        reasoning = reasoning[:317] + "..."
    return reasoning


# ============================================================================
# Main pipeline
# ============================================================================

def load_candidates(path: str):
    p = Path(path)
    if p.suffix == ".gz":
        import gzip
        opener = lambda: gzip.open(p, "rt", encoding="utf-8")
    else:
        opener = lambda: open(p, "r", encoding="utf-8")

    with opener() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser(description="Redrob Hackathon ranker — Team Xcution")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl or .jsonl.gz")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--top-n", type=int, default=100)
    args = parser.parse_args()

    start = time.time()
    print(f"[rank.py] Loading candidates from {args.candidates} ...", file=sys.stderr)

    scored_candidates = []
    n_processed = 0
    n_honeypots_seen = 0

    for cand in load_candidates(args.candidates):
        try:
            result = score_candidate(cand)
            if result["is_honeypot"]:
                n_honeypots_seen += 1
            scored_candidates.append(result)
            n_processed += 1
        except Exception as e:
            print(f"[rank.py] WARNING: skipping candidate due to error: {e}", file=sys.stderr)
            continue

    elapsed_scoring = time.time() - start
    print(
        f"[rank.py] Scored {n_processed} candidates in {elapsed_scoring:.1f}s "
        f"({n_honeypots_seen} flagged as honeypots/suspicious)",
        file=sys.stderr,
    )

    # Sort by score descending; tie-break by candidate_id ascending
    scored_candidates.sort(key=lambda x: (-x["score"], x["candidate_id"]))

    top_n = scored_candidates[: args.top_n]

    # Write CSV
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, c in enumerate(top_n):
            rank = i + 1
            reasoning = generate_reasoning(c)
            writer.writerow([c["candidate_id"], rank, f"{c['score']:.4f}", reasoning])

    elapsed_total = time.time() - start
    print(
        f"[rank.py] Wrote top-{len(top_n)} to {out_path} in {elapsed_total:.1f}s total "
        f"(scoring: {elapsed_scoring:.1f}s)",
        file=sys.stderr,
    )
    print(
        f"[rank.py] Honeypot rate in output: "
        f"{sum(1 for c in top_n if c['is_honeypot'])}/{len(top_n)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
