"""HoneypotDetector — rule-based internal-consistency checker (hard-exclude before scoring).

Optionally accepts an AuditLogger so every flag is persisted to the audit trail
without callers needing to instrument the loop themselves.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .audit_logger import AuditLogger


@dataclass
class HoneypotResult:
    candidate_id: str
    is_honeypot: bool
    triggered_rules: list[str] = field(default_factory=list)


def build_company_first_seen(candidates: list[dict]) -> dict[str, int]:
    first_seen: dict[str, int] = {}
    for c in candidates:
        for role in c.get("career_history", []):
            company = role.get("company")
            start = role.get("start_date")
            if not company or not start:
                continue
            try:
                year = int(start[:4])
            except (ValueError, TypeError):
                continue
            if company not in first_seen or year < first_seen[company]:
                first_seen[company] = year
    return first_seen


class HoneypotDetector:
    def __init__(
        self,
        company_first_seen: dict[str, int] | None = None,
        audit_logger: "AuditLogger | None" = None,
    ) -> None:
        self.company_first_seen = company_first_seen or {}
        self._audit = audit_logger

    def check(self, candidate: dict) -> HoneypotResult:
        cid = candidate["candidate_id"]
        rules: list[str] = []

        # Rule 1 — tenure predates company founding
        for role in candidate.get("career_history", []):
            company = role.get("company")
            start = role.get("start_date")
            if company in self.company_first_seen and start:
                try:
                    start_year = int(start[:4])
                except (ValueError, TypeError):
                    continue
                if start_year < self.company_first_seen[company] - 1:
                    rules.append("tenure_vs_founding_mismatch")
                    break

        # Rule 2 — claimed expert in ≥5 skills each with ≤2 months experience
        expert_low_duration = sum(
            1 for s in candidate.get("skills", [])
            if s.get("proficiency") == "expert" and (s.get("duration_months") or 0) <= 2
        )
        if expert_low_duration >= 5:
            rules.append("proficiency_duration_impossibility")

        # Rule 3 — declared YoE exceeds sum of career history by >2 years
        yoe = candidate.get("profile", {}).get("years_of_experience", 0) or 0
        history_years = sum(
            (r.get("duration_months") or 0) for r in candidate.get("career_history", [])
        ) / 12.0
        if yoe - history_years > 2.0:
            rules.append("yoe_history_mismatch")

        # Rule 4 — education end_year < start_year (time travel)
        for edu in candidate.get("education", []):
            sy, ey = edu.get("start_year"), edu.get("end_year")
            if sy and ey and ey < sy:
                rules.append("education_year_impossibility")
                break

        # Rule 5 — multiple simultaneous "current" roles
        current_count = sum(1 for r in candidate.get("career_history", []) if r.get("is_current"))
        if current_count > 1:
            rules.append("multiple_current_roles")

        # Rule 6 — role end_date before start_date
        for r in candidate.get("career_history", []):
            if r.get("end_date") and r.get("start_date") and r["end_date"] < r["start_date"]:
                rules.append("date_order_impossibility")
                break

        result = HoneypotResult(candidate_id=cid, is_honeypot=len(rules) > 0, triggered_rules=rules)

        # Emit to audit trail if logger is wired in
        if result.is_honeypot and self._audit is not None:
            self._audit.log_honeypot(cid, rules)

        return result

    def filter_pool(
        self, candidates: list[dict]
    ) -> tuple[list[dict], list[HoneypotResult]]:
        flagged: list[HoneypotResult] = []
        clean: list[dict] = []
        for c in candidates:
            result = self.check(c)
            if result.is_honeypot:
                flagged.append(result)
            else:
                clean.append(c)
        return clean, flagged
