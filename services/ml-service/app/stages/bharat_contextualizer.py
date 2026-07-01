"""
BharatContextualizer — Master Orchestrator for the Bharat Intelligence Layer.

Runs BIL-1 through BIL-4 in the correct order and returns enriched candidate
dicts ready for LightGBM signal fusion.

Slot in pipeline: AFTER anomaly detection, BEFORE fusion ranker.
Integration point: services/ml-service/app/pipeline.py → CandidateDiscoveryPipeline.run()

New features injected into each candidate dict (available to fusion ranker):
    - engagement_score         (BIL-1 — normalized in-place)
    - recency_of_activity      (BIL-1 — normalized in-place)
    - bharat_tier              (BIL-1 — metadata)
    - institution_tier_score   (BIL-2 — new feature)
    - institution_nirf_matched (BIL-2 — metadata)
    - skills                   (BIL-3 + BIL-4 — augmented in-place)
    - code_switch_detected     (BIL-3 — metadata)
    - informal_sector_score    (BIL-4 — new feature)
    - bharat_context_applied   (flag — always True after this step)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from typing import Any, Optional

from .bharat.tier_normalizer import TierCityEngagementNormalizer
from .bharat.institution_intelligence import IndiaInstitutionIntelligence
from .bharat.code_switch_parser import CodeSwitchResumeParser
from .bharat.informal_sector_translator import InformalSectorTranslator

log = logging.getLogger(__name__)


@dataclass
class BharatContextSummary:
    """Returned alongside ranked results for dashboard transparency."""
    total_candidates: int
    tier_1_count: int
    tier_2_count: int
    tier_3_count: int
    tier_adjusted_count: int
    nirf_matched_count: int
    code_switch_detected_count: int
    informal_sector_count: int
    avg_engagement_delta: float
    processing_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BharatContextualizer:
    """
    Master orchestrator for the Bharat Intelligence Layer.

    Usage:
        contextualizer = BharatContextualizer()
        enriched = contextualizer.enrich(candidates, skill_pool=jd_skills)
        summary = contextualizer.last_summary
    """

    def __init__(
        self,
        use_indictrans2: bool = False,
        enabled: bool = True,
    ) -> None:
        """
        Args:
            use_indictrans2: Load IndicTrans2 for full Devanagari translation.
            enabled: Master toggle. If False, returns candidates unchanged.
        """
        self.enabled = enabled
        self.tier_normalizer = TierCityEngagementNormalizer()
        self.institution_iq = IndiaInstitutionIntelligence()
        self.code_switch = CodeSwitchResumeParser(use_indictrans2=use_indictrans2)
        self.informal_sector = InformalSectorTranslator()
        self.last_summary: Optional[BharatContextSummary] = None

    def enrich(
        self,
        candidates: list[dict],
        skill_pool: Optional[set] = None,
    ) -> list[dict]:
        """
        Run all four BIL modules over the candidate list.
        Returns the same list with enriched features — in-place modification.
        """
        if not self.enabled or not candidates:
            for c in candidates:
                c["bharat_context_applied"] = self.enabled
                c.setdefault("institution_tier_score", 0.50)
                c.setdefault("informal_sector_score", 0.0)
            if not self.enabled:
                self.last_summary = None
            return candidates

        t_start = time.perf_counter()

        # BIL-1: Tier-city engagement normalization
        log.debug("BIL-1: Normalizing engagement scores by city tier…")
        candidates = self.tier_normalizer.normalize_batch(candidates)

        # BIL-2: Institution intelligence
        log.debug("BIL-2: Scoring institutions via NIRF database…")
        candidates = self.institution_iq.score_batch(candidates)

        # BIL-3: Code-switch resume parsing
        log.debug("BIL-3: Parsing code-switched resume text…")
        candidates = self.code_switch.augment_candidate_skills(candidates, skill_pool)

        # BIL-4: Informal sector signal translation
        log.debug("BIL-4: Translating informal sector signals…")
        candidates = self.informal_sector.translate_batch(candidates)

        # Mark all candidates as processed
        for c in candidates:
            c["bharat_context_applied"] = True

        elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Build summary for dashboard
        tiers = [c.get("bharat_tier", "tier_2") for c in candidates]
        deltas = [c.get("engagement_delta", 0.0) for c in candidates]

        self.last_summary = BharatContextSummary(
            total_candidates=len(candidates),
            tier_1_count=tiers.count("tier_1"),
            tier_2_count=tiers.count("tier_2"),
            tier_3_count=tiers.count("tier_3"),
            tier_adjusted_count=sum(1 for c in candidates if c.get("tier_adjusted", False)),
            nirf_matched_count=sum(1 for c in candidates if c.get("institution_nirf_matched", False)),
            code_switch_detected_count=sum(1 for c in candidates if c.get("code_switch_detected", False)),
            informal_sector_count=sum(1 for c in candidates if c.get("informal_sector_score", 0) > 0.1),
            avg_engagement_delta=round(sum(deltas) / max(len(deltas), 1), 4),
            processing_ms=round(elapsed_ms, 1),
        )

        log.info(
            "BharatContextualizer: enriched %d candidates in %.1fms | "
            "tier-adjusted=%d | code-switch=%d | informal=%d",
            len(candidates),
            elapsed_ms,
            self.last_summary.tier_adjusted_count,
            self.last_summary.code_switch_detected_count,
            self.last_summary.informal_sector_count,
        )

        return candidates
