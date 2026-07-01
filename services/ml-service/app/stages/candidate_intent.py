"""
CandidateIntent™ Engine — Stage 10 (post-ranking enrichment)
=============================================================
Computes a calibrated "mobility score" (0-1) predicting how likely
a candidate is to respond to recruiter outreach RIGHT NOW.

Orthogonal to fit score:
  High fit + High intent  → Q1 Contact Now
  High fit + Low intent   → Q2 Nurture pipeline
  Low fit  + High intent  → Q3 Future role
  Low fit  + Low intent   → Q4 Archive

Five India-calibrated sub-signals:
  1. tenure_risk_score       — how close to the "itch point" in current role
  2. platform_recency_score  — recent engagement on professional platforms
  3. career_velocity_score   — momentum (promotions, certs, portfolio updates)
  4. market_context_score    — sector-level hiring activity + city tier
  5. life_event_proximity    — graduation, fiscal year end, project completion

Fully heuristic — no model weights to download. Graceful on sparse data.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# ── India-specific tenure norms (months) ─────────────────────────────────────

INDIA_TENURE_NORMS_MONTHS: dict[str, int] = {
    "tech_startup":    18,
    "product_company": 24,
    "enterprise_mnc":  36,
    "service_company": 30,
    "unknown":         22,
}
ITCH_WINDOW_MONTHS = 6


# ── Sub-signal 1: Tenure Risk ─────────────────────────────────────────────────

def compute_tenure_risk_score(
    current_role_start: datetime,
    company_type: str = "unknown",
    reference_time: Optional[datetime] = None,
) -> dict:
    now = reference_time or datetime.now(timezone.utc)
    tenure_months = (now - current_role_start).days / 30.44
    median = INDIA_TENURE_NORMS_MONTHS.get(company_type, 22)
    distance = abs(tenure_months - median)
    sigma = ITCH_WINDOW_MONTHS
    raw = math.exp(-(distance ** 2) / (2 * sigma ** 2))
    if tenure_months > median:
        raw = min(1.0, raw * 1.15)
    if tenure_months < 6:
        raw *= 0.3
    if tenure_months > 48:
        raw *= max(0.1, 1 - (tenure_months - 48) / 36)
    return {
        "tenure_months": round(tenure_months, 1),
        "median_for_company_type": median,
        "distance_from_median_months": round(distance, 1),
        "tenure_risk_score": round(min(1.0, max(0.0, raw)), 4),
        "interpretation": _tenure_interp(tenure_months, median),
    }


def _tenure_interp(months: float, median: float) -> str:
    if months < 6:
        return "Too new — unlikely to move in the next 3 months"
    if abs(months - median) < ITCH_WINDOW_MONTHS:
        return "At peak mobility window — high probability of active consideration"
    if months > median + ITCH_WINDOW_MONTHS:
        return "Past median tenure — could be deeply embedded or actively looking"
    return "Approaching mobility window — good time to build relationship"


# ── Sub-signal 2: Platform Recency ───────────────────────────────────────────

def compute_platform_recency_score(
    last_active_at: datetime,
    profile_update_at: Optional[datetime] = None,
    recent_views: int = 0,
    job_page_visits: int = 0,
    reference_time: Optional[datetime] = None,
) -> dict:
    now = reference_time or datetime.now(timezone.utc)
    days_since = (now - last_active_at).days
    base = math.exp(-days_since / 30)
    update_bonus = 0.0
    if profile_update_at:
        d = (now - profile_update_at).days
        update_bonus = 0.35 if d <= 7 else (0.20 if d <= 30 else (0.10 if d <= 90 else 0))
    intent_bonus = min(0.30, job_page_visits * 0.05 + recent_views * 0.01)
    raw = min(1.0, base + update_bonus + intent_bonus)
    return {
        "days_since_active": days_since,
        "platform_recency_score": round(raw, 4),
        "intent_signals_detected": job_page_visits > 0 or (
            profile_update_at is not None and (now - profile_update_at).days <= 14
        ),
    }


# ── Sub-signal 3: Career Velocity ────────────────────────────────────────────

def compute_career_velocity_score(
    title_history: list[dict],
    recent_certifications: Optional[list[dict]] = None,
    portfolio_updates: Optional[list[dict]] = None,
    reference_time: Optional[datetime] = None,
) -> dict:
    now = reference_time or datetime.now(timezone.utc)
    recent_certifications = recent_certifications or []
    portfolio_updates = portfolio_updates or []
    cutoff = now - timedelta(days=365)

    def _after_cutoff(date_str: str) -> bool:
        try:
            dt = datetime.fromisoformat(str(date_str)).replace(tzinfo=timezone.utc)
            return dt >= cutoff
        except Exception:
            return False

    promotions = sum(1 for r in title_history if _after_cutoff(r.get("start_date", "")))
    certs = sum(1 for c in recent_certifications if _after_cutoff(c.get("issued_at", "")))
    portfolio = sum(1 for p in portfolio_updates if _after_cutoff(p.get("updated_at", "")))
    velocity = min(1.0, (promotions * 0.40 + certs * 0.35 + portfolio * 0.25) / 1.5)
    return {
        "recent_promotions": promotions,
        "recent_certifications": certs,
        "recent_portfolio_updates": portfolio,
        "career_velocity_score": round(velocity, 4),
        "is_high_velocity": velocity >= 0.60,
    }


# ── Sub-signal 4: Market Context ─────────────────────────────────────────────

_SECTOR_DEMAND: dict[str, float] = {
    "ml": 0.88, "backend": 0.82, "devops": 0.79,
    "data": 0.76, "frontend": 0.71, "unknown": 0.65,
}
_TIER_MULTIPLIER: dict[str, float] = {
    "tier_1": 1.00, "tier_2": 1.12, "tier_3": 1.18, "unknown": 1.05,
}


def compute_market_context_score(candidate_domain: str, candidate_location: str = "unknown") -> dict:
    base = _SECTOR_DEMAND.get(candidate_domain, _SECTOR_DEMAND["unknown"])
    # Soft import — bharat module may not be available in all deployments
    tier = "unknown"
    try:
        from .bharat.tier_normalizer import classify_city_tier  # type: ignore
        tier = classify_city_tier(candidate_location)
    except Exception:
        pass
    mult = _TIER_MULTIPLIER.get(tier, 1.05)
    return {
        "candidate_domain": candidate_domain,
        "sector_demand_index": base,
        "location_tier": tier,
        "tier_mobility_multiplier": mult,
        "market_context_score": round(min(1.0, base * mult), 4),
    }


# ── Sub-signal 5: Life Event Proximity ───────────────────────────────────────

def compute_life_event_proximity_score(
    graduation_month: Optional[int] = None,
    fiscal_year_end_proximity_days: int = 999,
    project_completion_signals: int = 0,
    reference_time: Optional[datetime] = None,
) -> dict:
    now = reference_time or datetime.now(timezone.utc)
    events: list[tuple[str, float]] = []
    if graduation_month and (now.month - graduation_month) % 12 <= 3:
        events.append(("graduation_proximity", 0.30))
    if fiscal_year_end_proximity_days <= 90:
        events.append(("fiscal_year_proximity", round(0.25 * (1 - fiscal_year_end_proximity_days / 90), 3)))
    if project_completion_signals > 0:
        events.append(("project_completion", min(0.20, project_completion_signals * 0.10)))
    total = sum(v for _, v in events)
    return {
        "life_event_proximity_score": round(min(1.0, total), 4),
        "contributing_events": [k for k, _ in events],
        "fiscal_year_end_days": fiscal_year_end_proximity_days,
    }


# ── Intent Score dataclass ────────────────────────────────────────────────────

@dataclass
class IntentScore:
    candidate_id:           str
    composite_intent_score: float
    tenure_risk:            float
    platform_recency:       float
    career_velocity:        float
    market_context:         float
    life_event_proximity:   float
    intent_label:           str   # "hot" | "warm" | "cool" | "dormant"
    contact_timing_advice:  str
    days_until_peak_window: Optional[int]
    sub_signals:            dict = field(default_factory=dict)


# ── Master Engine ─────────────────────────────────────────────────────────────

class CandidateIntentEngine:
    """
    CandidateIntent™ — post-ranking enrichment layer.
    Call score_batch() after fusion ranking to add intent dimension.
    """

    WEIGHTS = {
        "tenure_risk":          0.28,
        "platform_recency":     0.25,
        "career_velocity":      0.22,
        "market_context":       0.15,
        "life_event_proximity": 0.10,
    }

    _ADVICE = {
        "hot":     "Contact within 24h — candidate is at peak mobility. Lead with a specific opportunity.",
        "warm":    "Engage this week with a personalized message. Share the role, invite a conversation.",
        "cool":    "Add to nurture pipeline. Send value-add content. Revisit in 60 days.",
        "dormant": "Do not contact now. Set a 90-day reminder and re-score before outreach.",
    }

    def score(self, candidate: dict, structured_jd: Optional[dict] = None) -> IntentScore:  # noqa: ARG002
        now = datetime.now(timezone.utc)

        # Sub-signal 1 — tenure risk
        history = candidate.get("title_history") or [{}]
        last_role = history[-1]
        start_raw = last_role.get("start_date") or last_role.get("start_year")
        if start_raw:
            try:
                if isinstance(start_raw, int):
                    role_start = datetime(start_raw, 1, 1, tzinfo=timezone.utc)
                else:
                    role_start = datetime.fromisoformat(str(start_raw)).replace(tzinfo=timezone.utc)
            except Exception:
                role_start = now - timedelta(days=22 * 30)
        else:
            yoe = candidate.get("years_experience", 3)
            role_count = max(len(history), 1)
            approx_days = int((yoe * 365) / role_count)
            role_start = now - timedelta(days=approx_days)

        t1 = compute_tenure_risk_score(role_start, last_role.get("company_type", "unknown"), now)

        # Sub-signal 2 — platform recency
        last_active_str = candidate.get("last_active_at", "")
        try:
            last_active = datetime.fromisoformat(last_active_str).replace(tzinfo=timezone.utc)
        except Exception:
            last_active = now - timedelta(days=90)

        profile_update_str = candidate.get("profile_updated_at")
        profile_update: Optional[datetime] = None
        if profile_update_str:
            try:
                profile_update = datetime.fromisoformat(profile_update_str).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        t2 = compute_platform_recency_score(
            last_active, profile_update,
            recent_views=candidate.get("recent_profile_views", 0),
            job_page_visits=candidate.get("recent_job_page_visits", 0),
            reference_time=now,
        )

        # Sub-signal 3 — career velocity
        t3 = compute_career_velocity_score(
            candidate.get("title_history", []),
            candidate.get("recent_certifications", []),
            candidate.get("portfolio_updates", []),
            now,
        )

        # Sub-signal 4 — market context
        t4 = compute_market_context_score(
            candidate.get("cluster", "unknown"),
            candidate.get("city", "unknown"),
        )

        # Sub-signal 5 — life events
        next_fy = datetime(now.year if now.month < 4 else now.year + 1, 4, 1, tzinfo=timezone.utc)
        fy_days = (next_fy - now).days
        t5 = compute_life_event_proximity_score(
            graduation_month=candidate.get("graduation_month"),
            fiscal_year_end_proximity_days=fy_days,
            project_completion_signals=candidate.get("project_completion_signals", 0),
            reference_time=now,
        )

        composite = round(min(1.0, max(0.0,
            self.WEIGHTS["tenure_risk"]          * t1["tenure_risk_score"] +
            self.WEIGHTS["platform_recency"]     * t2["platform_recency_score"] +
            self.WEIGHTS["career_velocity"]      * t3["career_velocity_score"] +
            self.WEIGHTS["market_context"]       * t4["market_context_score"] +
            self.WEIGHTS["life_event_proximity"] * t5["life_event_proximity_score"]
        )), 4)

        label = "dormant"
        for lbl, thr in [("hot", 0.72), ("warm", 0.50), ("cool", 0.30)]:
            if composite >= thr:
                label = lbl
                break

        days_until_peak: Optional[int] = None
        if label in ("cool", "dormant"):
            med = INDIA_TENURE_NORMS_MONTHS.get(last_role.get("company_type", "unknown"), 22)
            current = t1["tenure_months"]
            if current < med - ITCH_WINDOW_MONTHS:
                days_until_peak = int((med - ITCH_WINDOW_MONTHS - current) * 30)

        return IntentScore(
            candidate_id=candidate.get("id", "unknown"),
            composite_intent_score=composite,
            tenure_risk=t1["tenure_risk_score"],
            platform_recency=t2["platform_recency_score"],
            career_velocity=t3["career_velocity_score"],
            market_context=t4["market_context_score"],
            life_event_proximity=t5["life_event_proximity_score"],
            intent_label=label,
            contact_timing_advice=self._ADVICE[label],
            days_until_peak_window=days_until_peak,
            sub_signals={"tenure": t1, "recency": t2, "velocity": t3, "market": t4, "life_event": t5},
        )

    def score_batch(self, candidates: list[dict], structured_jd: Optional[dict] = None) -> list[dict]:
        """Enrich and re-sort: primary key = fit score tier, secondary = intent."""
        for c in candidates:
            intent = self.score(c, structured_jd)
            c["intent_score"]          = intent.composite_intent_score
            c["intent_label"]          = intent.intent_label
            c["contact_timing_advice"] = intent.contact_timing_advice
            c["days_until_peak"]       = intent.days_until_peak_window
            c["intent_sub_signals"]    = intent.sub_signals
        return sorted(candidates, key=lambda c: (-round(c.get("fusion_score", 0), 1), -c["intent_score"]))

    def build_priority_matrix(self, candidates: list[dict]) -> dict:
        FIT_THR    = 0.65
        INTENT_THR = 0.50
        m: dict[str, list[str]] = {"Q1_contact_now": [], "Q2_nurture": [], "Q3_future_role": [], "Q4_archive": []}
        for c in candidates:
            fit    = c.get("fusion_score", 0)
            intent = c.get("intent_score", 0)
            cid    = c.get("id", c.get("candidate_id", "?"))
            if fit >= FIT_THR and intent >= INTENT_THR:
                m["Q1_contact_now"].append(cid)
            elif fit >= FIT_THR:
                m["Q2_nurture"].append(cid)
            elif intent >= INTENT_THR:
                m["Q3_future_role"].append(cid)
            else:
                m["Q4_archive"].append(cid)
        return {**m, "summary": {k.replace("Q1_", "").replace("Q2_", "").replace("Q3_", "").replace("Q4_", "") + "_count": len(v) for k, v in m.items()}}
