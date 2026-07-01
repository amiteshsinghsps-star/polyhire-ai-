"""
BIL-4: Informal Sector Signal Translator.

Maps informal sector experience (small business, gig work, agricultural operations,
family enterprise, contractual work) to formal enterprise skill equivalents.

Injects informal_sector_score as a new feature into the fusion ranker, and
augments the candidate's skills list with translated formal-sector equivalents
so that skill_overlap_ratio reflects true capability rather than vocabulary alignment.

This module is India-specific: the informal sector descriptors and their weightings
are calibrated to the Indian professional context.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ── Informal → Formal skill translation taxonomy ───────────────────────────
# Format: (regex_pattern, {formal_skill: confidence_weight})
# Weight = confidence that this informal experience demonstrates the formal skill.

INFORMAL_TO_FORMAL: list[tuple[str, dict[str, float]]] = [
    # ── Small business / shop ownership ──────────────────────────────────────
    (
        r"ran\s+(?:a|an|my)\s+(?:small\s+)?(?:\w+\s+){0,2}(shop|store|business|dukaan|enterprise)",
        {
            "team management": 0.80,
            "vendor management": 0.85,
            "procurement": 0.75,
            "cash flow management": 0.82,
            "customer relationship management": 0.85,
            "operations management": 0.78,
            "inventory management": 0.80,
            "p&l management": 0.70,
            "hiring": 0.65,
        },
    ),
    # ── Agricultural operations / farm management ────────────────────────────
    (
        r"(managed|running|operated?)\s+(farm|agricultural|crops?|khet|kheti)",
        {
            "operations management": 0.75,
            "resource planning": 0.72,
            "logistics": 0.68,
            "procurement": 0.70,
            "financial planning": 0.65,
            "vendor negotiation": 0.72,
        },
    ),
    # ── Freelance / contractual ──────────────────────────────────────────────
    (
        r"(freelance|freelancing|contract|contractual|self.?employed)",
        {
            "client management": 0.85,
            "project management": 0.78,
            "estimation": 0.72,
            "deliverables management": 0.80,
            "time management": 0.75,
            "self-management": 0.85,
        },
    ),
    # ── Tutoring / coaching ──────────────────────────────────────────────────
    (
        r"(tutor|tutoring|coaching|taught|teaching|padhai|padhaya)",
        {
            "communication": 0.85,
            "mentoring": 0.80,
            "curriculum development": 0.70,
            "assessment design": 0.72,
            "presentation skills": 0.78,
            "stakeholder management": 0.65,
        },
    ),
    # ── Gig economy (delivery, cab, logistics) ───────────────────────────────
    (
        r"(zomato|swiggy|dunzo|delivery|cab\s*driver|ola|uber|logistics\s*partner)",
        {
            "logistics": 0.80,
            "time management": 0.78,
            "customer service": 0.82,
            "route optimization": 0.68,
            "operations": 0.70,
        },
    ),
    # ── Family enterprise management ─────────────────────────────────────────
    (
        r"(family\s*(business|enterprise|firm)|parivar\s*ka\s*business|ghar\s*ka\s*kaam)",
        {
            "business operations": 0.75,
            "stakeholder management": 0.70,
            "financial management": 0.72,
            "vendor management": 0.73,
            "customer relations": 0.78,
        },
    ),
    # ── Event management / community organizing ──────────────────────────────
    (
        r"(event\s*(management|organiz)|organized?\s*(festival|event|program|mela|pooja))",
        {
            "event management": 0.88,
            "stakeholder coordination": 0.80,
            "logistics": 0.78,
            "vendor management": 0.72,
            "budget management": 0.70,
            "team coordination": 0.80,
        },
    ),
    # ── Data entry / back office (common first job in India) ─────────────────
    (
        r"(data\s*entry|back\s*office|bpo|kpo|call\s*cent(er|re)|customer\s*care)",
        {
            "data management": 0.78,
            "customer service": 0.82,
            "attention to detail": 0.75,
            "process adherence": 0.72,
            "communication": 0.80,
            "crm tools": 0.68,
        },
    ),
    # ── Construction / site supervision (common in Tier-2/3) ────────────────
    (
        r"(site\s*(engineer|supervisor|incharge)|construction|civil\s*work|building\s*work)",
        {
            "project management": 0.78,
            "resource management": 0.75,
            "vendor management": 0.72,
            "quality control": 0.74,
            "safety management": 0.70,
            "team management": 0.76,
        },
    ),
    # ── NGO / social work ────────────────────────────────────────────────────
    (
        r"(ngo|social\s*work|volunteer|sewa|community\s*(service|work))",
        {
            "stakeholder management": 0.75,
            "communication": 0.80,
            "project coordination": 0.72,
            "reporting": 0.70,
            "field operations": 0.74,
        },
    ),
    # ── Repair / technical servicing (ITI-type backgrounds) ─────────────────
    (
        r"(repair(ed|ing)?|servic(ed|ing)?|maintenance|iti|hvac|electrician|plumber)",
        {
            "technical troubleshooting": 0.85,
            "hardware maintenance": 0.80,
            "diagnostic skills": 0.78,
            "client service": 0.75,
            "documentation": 0.65,
        },
    ),
]


@dataclass
class InformalSectorResult:
    detected_patterns: list[str]
    translated_skills: dict[str, float]
    informal_sector_score: float
    high_confidence_skills: list[str]
    added_to_candidate_skills: list[str]
    explanation: str


class InformalSectorTranslator:
    """
    BIL-4: Translate informal sector experience into formal enterprise skill signals.
    Injects informal_sector_score into the fusion ranker feature set and augments
    the candidate skill list with high-confidence translated skills.
    """

    def translate(
        self,
        profile_text: str,
        existing_skills: Optional[list[str]] = None,
    ) -> InformalSectorResult:
        existing_skills = existing_skills or []
        text_lower = profile_text.lower()

        matched_patterns: list[str] = []
        all_translated: dict[str, float] = {}

        for pattern, skills in INFORMAL_TO_FORMAL:
            if re.search(pattern, text_lower, re.IGNORECASE):
                clean_pattern = re.sub(r"[\\()?+*]", "", pattern.split(r"\s*")[0]).strip()
                matched_patterns.append(clean_pattern[:40])
                for skill, weight in skills.items():
                    all_translated[skill] = max(all_translated.get(skill, 0.0), weight)

        if not all_translated:
            return InformalSectorResult(
                detected_patterns=[],
                translated_skills={},
                informal_sector_score=0.0,
                high_confidence_skills=[],
                added_to_candidate_skills=[],
                explanation="No informal sector experience detected in profile.",
            )

        # informal_sector_score: weighted average of matched skill confidences, breadth-bonused.
        weights = list(all_translated.values())
        raw_score = sum(weights) / max(len(weights), 1)
        breadth_bonus = min(0.10, len(matched_patterns) * 0.03)
        informal_score = round(min(0.85, raw_score + breadth_bonus), 4)

        high_confidence = [s for s, w in all_translated.items() if w >= 0.75]
        to_inject = [s for s in high_confidence if s not in existing_skills]

        if matched_patterns:
            pattern_str = ", ".join(matched_patterns[:3])
            skill_str = ", ".join(high_confidence[:4])
            explanation = (
                f"Informal sector experience detected: {pattern_str}. "
                f"Demonstrates: {skill_str}."
                + (f" Informal sector score: {informal_score:.2f}." if informal_score > 0.4 else "")
            )
        else:
            explanation = "No informal sector experience detected."

        return InformalSectorResult(
            detected_patterns=matched_patterns,
            translated_skills=all_translated,
            informal_sector_score=informal_score,
            high_confidence_skills=high_confidence,
            added_to_candidate_skills=to_inject,
            explanation=explanation,
        )

    def translate_batch(self, candidates: list[dict]) -> list[dict]:
        """Inject informal_sector_score and augment skills for a batch of candidates."""
        for c in candidates:
            profile_text = c.get("profile_text", "")
            result = self.translate(profile_text, c.get("skills", []))
            c["informal_sector_score"] = result.informal_sector_score
            if result.added_to_candidate_skills:
                c["skills"] = c.get("skills", []) + result.added_to_candidate_skills
                c["informal_skills_injected"] = result.added_to_candidate_skills
            c["informal_sector_explanation"] = result.explanation
        return candidates
