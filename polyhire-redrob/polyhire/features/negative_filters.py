import re
import jd_profile as jd


def negative_filter_penalty(candidate: dict) -> tuple[float, list[str]]:
    triggered: list[str] = []
    history = candidate.get("career_history", [])
    industries = {(r.get("industry") or "").lower() for r in history}
    companies = {(r.get("company") or "").lower() for r in history}
    descriptions = " ".join((r.get("description") or "") for r in history).lower()

    if history and industries.issubset({"academia", "research", "education"}):
        triggered.append("pure_research_career")

    sorted_hist = sorted(history, key=lambda r: r.get("start_date", ""), reverse=True)
    if sorted_hist:
        most_recent = sorted_hist[0]
        recent_desc = (most_recent.get("description") or "").lower()
        recent_is_llm_only = bool(re.search(r"langchain|prompt engineering|llm wrapper", recent_desc))
        older_has_ir_ml = any(
            re.search(
                r"retrieval|ranking|embeddings|recommendation|search index|ml pipeline",
                (r.get("description") or "").lower(),
            )
            for r in sorted_hist[1:]
        )
        if recent_is_llm_only and not older_has_ir_ml and (most_recent.get("duration_months") or 0) < 12:
            triggered.append("recent_llm_only_experience")

    if sorted_hist:
        most_recent = sorted_hist[0]
        title = (most_recent.get("title") or "").lower()
        is_leadership = any(re.search(p, title) for p in jd.LEADERSHIP_TITLES)
        long_tenure = (most_recent.get("duration_months") or 0) >= 18
        hands_on = bool(
            re.search(r"wrote|built|implemented|shipped|coded|developed", (most_recent.get("description") or "").lower())
        )
        if is_leadership and long_tenure and not hands_on:
            triggered.append("leadership_drift")

    if companies and companies.issubset(jd.CONSULTING_FIRMS):
        triggered.append("pure_consulting_career")

    cv_speech_robotics = any(
        re.search(r"computer vision|speech recognition|robotics", (r.get("description") or "").lower())
        for r in history
    )
    nlp_ir_exposure = bool(re.search(r"nlp|natural language|retrieval|search|ranking|embeddings", descriptions))
    if cv_speech_robotics and not nlp_ir_exposure and history:
        triggered.append("no_nlp_ir_exposure")

    yoe = candidate.get("profile", {}).get("years_of_experience", 0) or 0
    github_score = candidate.get("redrob_signals", {}).get("github_activity_score", -1)
    has_certs = bool(candidate.get("certifications"))
    if yoe >= 5 and github_score <= 0 and not has_certs:
        triggered.append("no_external_validation")

    penalty = sum(jd.NEGATIVE_FILTER_PENALTIES[r] for r in triggered)
    return min(jd.WEIGHTS["negative_filter_cap"], penalty), triggered
