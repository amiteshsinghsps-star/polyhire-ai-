import re
import jd_profile as jd


def title_family_match(title: str) -> bool:
    if not title:
        return False
    return any(re.search(p, title, re.IGNORECASE) for p in jd.ML_AI_TITLE_FAMILY)


def role_relevance_score(candidate: dict, embed_sim_fn) -> tuple[float, bool]:
    titles = [candidate.get("profile", {}).get("current_title", "")]
    titles += [r.get("title", "") for r in candidate.get("career_history", [])]
    title_hit = any(title_family_match(t) for t in titles)

    history = sorted(candidate.get("career_history", []), key=lambda r: r.get("start_date", ""), reverse=True)
    recent_relevant = bool(history) and title_family_match(history[0].get("title", ""))

    descriptions = " ".join(r.get("description", "") for r in candidate.get("career_history", [])[:3])
    description_sim = embed_sim_fn(descriptions, jd.MUST_HAVE_CAPABILITY_STATEMENTS)

    if not title_hit:
        return min(0.05, description_sim * 0.3), recent_relevant

    score = 0.5 * description_sim + (0.3 if recent_relevant else 0.0) + 0.2
    return min(1.0, score), recent_relevant
