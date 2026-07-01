"""
HallucinationGuard
==================
Validates Groq LLM explanation output against candidate ground-truth data.
Called in stage6_explain.py AFTER Groq generates the explanation.

Integration:
  from .security.hallucination_guard import HallucinationGuard
  guard = HallucinationGuard()
  result = guard.validate(explanation_text, candidate)
  candidate["explanation"] = result.safe_explanation
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    original_explanation: str
    safe_explanation:     str
    hallucinations_found: list[dict] = field(default_factory=list)
    is_valid:             bool = True
    confidence:           float = 1.0


class HallucinationGuard:
    """
    Cross-validates every factual claim in an LLM-generated explanation
    against the structured candidate record.

    Checks:
      1. Years of experience (within ±2 of actual)
      2. Skill claims (LLM must not invent skills absent from candidate.skills)
      3. Percentage / score claims (within ±10% of actual fusion_score)
    """

    def validate(self, explanation: str, candidate: dict) -> ValidationResult:
        hallucinations: list[dict] = []
        corrected = explanation

        actual_yoe    = candidate.get("years_experience", 0)
        actual_skills = {s.lower() for s in candidate.get("skills", [])}
        actual_score  = candidate.get("fusion_score", 0)

        # 1. Years-of-experience claims
        for match in re.findall(
            r"(\d+)\s*(?:\+)?\s*years?\s*(?:of\s*)?(?:experience|exp\.?)",
            explanation, re.IGNORECASE,
        ):
            claimed = int(match)
            if abs(claimed - actual_yoe) > 2:
                hallucinations.append({
                    "type": "yoe_mismatch",
                    "claimed": claimed,
                    "actual": actual_yoe,
                    "severity": "high",
                })
                corrected = corrected.replace(f"{claimed} year", f"{actual_yoe} year", 1)

        # 2. Invented skills
        for skill_group in re.findall(
            r"(?:skills?\s+(?:include|like|such as|:)\s*)([\w\s,+#\.]+?)(?:\.|,|\band\b|$)",
            explanation, re.IGNORECASE,
        ):
            for skill in re.split(r"[,;]", skill_group):
                skill = skill.strip().lower()
                if len(skill) > 2 and skill not in actual_skills:
                    if not any(skill in a or a in skill for a in actual_skills):
                        hallucinations.append({
                            "type": "invented_skill",
                            "claimed_skill": skill,
                            "severity": "medium",
                        })

        # 3. Score / percentage claims
        for match in re.findall(r"(\d+(?:\.\d+)?)\s*%\s*(?:match|fit|score)", explanation):
            claimed_pct = float(match) / 100
            if abs(claimed_pct - actual_score) > 0.10:
                hallucinations.append({
                    "type": "score_mismatch",
                    "claimed_pct": float(match),
                    "actual_pct": round(actual_score * 100, 1),
                    "severity": "low",
                })

        is_valid   = not any(h["severity"] == "high" for h in hallucinations)
        confidence = max(0.0, 1.0 - len(hallucinations) * 0.15)

        return ValidationResult(
            original_explanation=explanation,
            safe_explanation=corrected,
            hallucinations_found=hallucinations,
            is_valid=is_valid,
            confidence=round(confidence, 3),
        )

    def validate_batch(self, candidates: list[dict]) -> list[dict]:
        """Validate explanations for a batch of ranked candidates in-place."""
        for c in candidates:
            if c.get("explanation"):
                result = self.validate(c["explanation"], c)
                c["explanation"]            = result.safe_explanation
                c["explanation_validated"]  = result.is_valid
                c["explanation_confidence"] = result.confidence
                if result.hallucinations_found:
                    c["explanation_warnings"] = result.hallucinations_found
        return candidates
