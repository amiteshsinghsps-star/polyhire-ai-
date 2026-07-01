"""
Honeypot Integrity System
=========================
Plants N fake "honeypot" candidates in every ranking pool before scoring.
These candidates have deliberately terrible profiles — they should ALWAYS rank
in the bottom 10%.

If any honeypot surfaces in the top-20 after LightGBM fusion:
  → The ranking system is being gamed (embedding injection / model manipulation)
  → Alert is raised + logged
  → Result is flagged for manual review

Integration (pipeline.py):
  from .security.honeypot import HoneypotManager
  mgr = HoneypotManager()
  pool_with_hp = mgr.inject(pool, jd_id)
  ranked = lightgbm_fusion(pool_with_hp, ...)
  integrity = mgr.check(ranked, jd_id)
  final = mgr.remove(ranked)
"""

from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_TEMPLATES: list[dict] = [
    {
        "skills": [],
        "years_experience": 0,
        "summary": "I am a professional with skills in many things.",
        "bharat_tier": "tier_3",
        "institution_tier_score": 0.1,
        "trust_score": 0.05,
        "fraud_risk_score": 0.0,
        "title_history": [],
        "education": [],
        "recency_of_activity": 0.05,
        "career_trajectory_slope": 0.0,
        "engagement_score": 0.05,
    },
    {
        "skills": ["cooking", "driving", "fishing"],
        "years_experience": 0,
        "summary": "Looking for opportunities in the field of technology.",
        "bharat_tier": "tier_3",
        "institution_tier_score": 0.05,
        "trust_score": 0.05,
        "fraud_risk_score": 0.0,
        "title_history": [],
        "education": [],
        "recency_of_activity": 0.05,
        "career_trajectory_slope": 0.0,
        "engagement_score": 0.05,
    },
    {
        "skills": ["ms_office", "email", "powerpoint"],
        "years_experience": 0,
        "summary": "Fresher seeking first opportunity.",
        "bharat_tier": "tier_3",
        "institution_tier_score": 0.1,
        "trust_score": 0.05,
        "fraud_risk_score": 0.0,
        "title_history": [],
        "education": [{"degree": "B.Com", "graduation_year": 2026}],
        "recency_of_activity": 0.1,
        "career_trajectory_slope": 0.0,
        "engagement_score": 0.05,
    },
]

HONEYPOT_PREFIX = "HONEYPOT_INTEGRITY_"
_TOP_N_CRITICAL = 20
_TOP_N_WARNING  = 30


@dataclass
class IntegrityCheckResult:
    is_intact:             bool
    honeypots_injected:    int
    honeypots_in_top_20:   int
    compromised_honeypots: list[dict] = field(default_factory=list)
    highest_honeypot_rank: Optional[int] = None
    alert_level:           str = "none"          # "none" | "warning" | "critical"
    alert_message:         Optional[str] = None
    check_timestamp:       str = ""


class HoneypotManager:
    """Stateless honeypot lifecycle: inject → rank → check → remove."""

    def __init__(self, secret_key: str = "polyhire_honeypot_secret_CHANGE_IN_PROD"):
        self._secret = secret_key

    def _hp_id(self, idx: int, jd_id: str) -> str:
        raw = f"{self._secret}:{jd_id}:{idx}"
        return HONEYPOT_PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def inject(self, candidates: list[dict], jd_id: str = "unknown") -> list[dict]:
        """Add honeypot candidates to the pool before ranking."""
        honeypots = [
            {
                **tmpl,
                "id": self._hp_id(i, jd_id),
                "name": f"_HoneyTest_{i}",
                "city": "Unknown",
                "_is_honeypot": True,
                "_honeypot_idx": i,
            }
            for i, tmpl in enumerate(_TEMPLATES)
        ]
        logger.debug("[Honeypot] Injected %d honeypots for JD %s", len(honeypots), jd_id)
        return candidates + honeypots

    def check(self, ranked: list[dict], jd_id: str = "unknown") -> IntegrityCheckResult:
        """Inspect ranked output for integrity violations. Call BEFORE remove()."""
        findings = [
            {"honeypot_id": c["id"], "rank": i + 1, "fusion_score": c.get("fusion_score", 0)}
            for i, c in enumerate(ranked)
            if c.get("_is_honeypot") or c.get("id", "").startswith(HONEYPOT_PREFIX)
        ]

        in_top_20 = [f for f in findings if f["rank"] <= _TOP_N_CRITICAL]
        in_top_30 = [f for f in findings if f["rank"] <= _TOP_N_WARNING]
        highest   = min((f["rank"] for f in findings), default=None)

        if in_top_20:
            level = "critical"
            msg   = (
                f"CRITICAL: {len(in_top_20)} honeypot(s) reached top-{_TOP_N_CRITICAL}. "
                f"Highest rank: {min(f['rank'] for f in in_top_20)}. JD={jd_id}"
            )
            logger.critical("[Honeypot] %s", msg)
        elif in_top_30:
            level = "warning"
            msg   = f"WARNING: honeypot reached rank {min(f['rank'] for f in in_top_30)}. JD={jd_id}"
            logger.warning("[Honeypot] %s", msg)
        else:
            level, msg = "none", None

        return IntegrityCheckResult(
            is_intact=level == "none",
            honeypots_injected=len(_TEMPLATES),
            honeypots_in_top_20=len(in_top_20),
            compromised_honeypots=in_top_20,
            highest_honeypot_rank=highest,
            alert_level=level,
            alert_message=msg,
            check_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def remove(self, ranked: list[dict]) -> list[dict]:
        """Strip honeypots from final output — never exposed to the recruiter."""
        return [
            c for c in ranked
            if not (c.get("_is_honeypot") or c.get("id", "").startswith(HONEYPOT_PREFIX))
        ]
