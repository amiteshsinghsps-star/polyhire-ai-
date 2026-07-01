"""Combines the 23 redrob_signals fields into a bounded multiplier (~0.4-1.05)."""
from __future__ import annotations
from datetime import date, datetime


def _days_since(date_str: str, today: date) -> int:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (today - d).days
    except Exception:
        return 9999


def behavioral_multiplier(signals: dict, today: date | None = None, tier_exposure_norm: float | None = None) -> float:
    today = today or date.fromisoformat("2026-06-30")
    mult = 1.0

    inactive_days = _days_since(signals.get("last_active_date", ""), today)
    open_to_work = bool(signals.get("open_to_work_flag", False))
    if inactive_days > 180:
        mult *= 0.45 if not open_to_work else 0.6
    elif inactive_days > 90:
        mult *= 0.75
    elif inactive_days > 30:
        mult *= 0.92
    else:
        mult *= 1.03 if open_to_work else 1.0

    response_rate = float(signals.get("recruiter_response_rate", 0.5))
    mult *= 0.7 + 0.4 * response_rate

    avg_hours = float(signals.get("avg_response_time_hours", 48))
    if avg_hours <= 24:
        mult *= 1.02
    elif avg_hours > 96:
        mult *= 0.95

    interview_completion = float(signals.get("interview_completion_rate", 0.7))
    mult *= 0.85 + 0.2 * interview_completion

    offer_accept = float(signals.get("offer_acceptance_rate", -1))
    if offer_accept != -1 and offer_accept < 0.2:
        mult *= 0.95

    if tier_exposure_norm is not None:
        mult *= 0.97 + 0.06 * tier_exposure_norm

    verified_count = sum([
        bool(signals.get("verified_email")),
        bool(signals.get("verified_phone")),
        bool(signals.get("linkedin_connected")),
    ])
    mult *= 0.97 + 0.01 * verified_count

    return max(0.40, min(1.05, mult))
