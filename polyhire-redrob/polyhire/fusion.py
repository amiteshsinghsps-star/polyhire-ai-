"""The central fusion formula — combines all components per PRD §8.1."""
from __future__ import annotations
import jd_profile as jd
from .features.skill_match import skill_match_score
from .features.role_relevance import role_relevance_score
from .features.experience_fit import experience_fit_score
from .features.location_logistics import location_logistics_score
from .features.negative_filters import negative_filter_penalty
from .behavioral.signal_fusion import behavioral_multiplier
from .bharat.contextualizer import BharatContextualizer
from .bharat.tier_normalizer import classify_tier, normalize_exposure_signal


class FusionRanker:
    def __init__(self, embed_sim_fn, bharat: BharatContextualizer, pool_max_exposure: float = 1.0):
        self.embed_sim_fn = embed_sim_fn
        self.bharat = bharat
        self.pool_max_exposure = max(pool_max_exposure, 1.0)
        self.w = jd.WEIGHTS

    def score(self, candidate: dict) -> dict:
        cid = candidate["candidate_id"]

        def embed_for_candidate(text: str, statements: list[str]) -> float:
            return self.embed_sim_fn(text, statements, cid)

        skill = skill_match_score(candidate, embed_for_candidate)
        role, recent_relevant = role_relevance_score(candidate, embed_for_candidate)
        years = candidate.get("profile", {}).get("years_of_experience", 0) or 0
        experience = experience_fit_score(years)
        signals = candidate.get("redrob_signals", {})
        location = location_logistics_score(candidate.get("profile", {}), signals)
        penalty, triggered_rules = negative_filter_penalty(candidate)

        base_score = (
            self.w["skill_match"] * skill
            + self.w["role_relevance"] * role
            + self.w["experience_fit"] * experience
            + self.w["location_logistics"] * location
            - penalty
        )
        base_score = max(0.0, base_score)

        tier = classify_tier(candidate.get("profile", {}).get("location", ""))
        raw_exposure = float(signals.get("profile_views_received_30d", 0) or 0)
        tier_norm = normalize_exposure_signal(raw_exposure, tier, self.pool_max_exposure)

        behavioral_mult = behavioral_multiplier(signals, tier_exposure_norm=tier_norm)
        bharat_mult = self.bharat.adjustment(candidate)

        final_score = base_score * behavioral_mult * bharat_mult

        return dict(
            candidate_id=candidate["candidate_id"],
            final_score=round(min(1.0, final_score), 6),
            skill_match=round(skill, 4),
            role_relevance=round(role, 4),
            experience_fit=round(experience, 4),
            location_logistics=round(location, 4),
            negative_penalty=round(penalty, 4),
            triggered_rules=triggered_rules,
            behavioral_multiplier=round(behavioral_mult, 4),
            bharat_adjustment=round(bharat_mult, 4),
            recent_relevant_role=recent_relevant,
        )
