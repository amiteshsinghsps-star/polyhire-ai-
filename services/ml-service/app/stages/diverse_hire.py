"""
DiverseHire™ — Bias Elimination + Diversity Intelligence
==========================================================
Three components:

1. GenderLanguageAnalyzer — detect gendered words in JD text and suggest
   neutral alternatives. Uses the established Gaucher et al. (2011) word lists
   plus India-specific additions. Does NOT infer gender from candidate names.

2. InstitutionBiasDetector — detects when a shortlist is over-concentrated
   in top-5 IITs/IIMs, which excludes 99.9% of Indian talent.

3. DiversityScoreCalculator — Shannon entropy of shortlist across institution
   tier. Higher entropy = more diverse pipeline.

4. JDCleaner — rewrite JD to remove exclusionary language (rule-based).

5. DiverseHireEngine — master wrapper called by the pipeline.
"""
from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── Gendered word lists (Gaucher 2011 + India additions) ─────────────────────

MASCULINE_CODED = {
    "aggressive", "ambitious", "analytical", "assertive", "autonomous",
    "battle", "boast", "challenge", "champion", "compete", "competitive",
    "confident", "courageous", "decisive", "dominant", "drive", "driven",
    "fearless", "fight", "force", "head-strong", "hierarchical", "independent",
    "individual", "intellect", "lead", "leader", "ninja", "outspoken",
    "persistent", "principle", "rockstar", "self-confident", "self-reliant",
    "self-sufficient", "stubborn", "superior", "warrior", "win",
}

FEMININE_CODED = {
    "affectionate", "child", "collaborate", "collaborative", "commit",
    "communal", "compassionate", "connect", "considerate", "cooperative",
    "dependable", "empathize", "empathy", "feel", "flatter", "gentle",
    "honest", "inclusive", "interdependent", "interpersonal", "kind",
    "kinship", "loyal", "nurture", "pleasant", "polite", "quiet",
    "relationship", "sensitive", "share", "sincere", "support", "sympathize",
    "team", "together", "trust", "understand", "warm", "yield",
}

NEUTRAL_REPLACEMENTS = {
    "ninja":       "expert",
    "rockstar":    "high-performer",
    "warrior":     "dedicated professional",
    "aggressive":  "proactive",
    "dominant":    "strong",
    "battle":      "challenge",
    "boast":       "demonstrate",
    "fight":       "address",
}

# ── Institution tier map (India) ─────────────────────────────────────────────

IIT_IIM_ELITE = {
    "iit bombay", "iit delhi", "iit madras", "iit kanpur", "iit kharagpur",
    "iim ahmedabad", "iim bangalore", "iim calcutta", "iim lucknow",
    "iim indore", "bits pilani", "nit trichy", "nit surathkal",
}

TIER_1 = IIT_IIM_ELITE | {
    "delhi university", "jadavpur university", "anna university",
    "vit university", "manipal university",
}

TIER_2 = {
    "amity university", "symbiosis", "srm university", "psg college",
    "christ university", "kiit university",
}


def _institution_tier(institution: str) -> str:
    name = (institution or "").lower()
    if any(t in name for t in TIER_1):
        return "tier_1"
    if any(t in name for t in TIER_2):
        return "tier_2"
    if name:
        return "tier_3"
    return "unknown"


# ── Gender Language Analyzer ──────────────────────────────────────────────────

class GenderLanguageAnalyzer:
    """
    Detect gendered language in JD text.
    Returns counts of masculine-coded and feminine-coded words,
    plus specific instances and neutral alternatives.

    Research shows masculine-coded JDs deter women from applying even when
    they are equally or more qualified (Gaucher, Friesen, Kay, 2011).
    """

    def analyze(self, jd_text: str) -> dict:
        words = re.findall(r"\b\w+\b", jd_text.lower())

        masculine_found = [w for w in words if w in MASCULINE_CODED]
        feminine_found  = [w for w in words if w in FEMININE_CODED]

        masculine_count = len(masculine_found)
        feminine_count  = len(feminine_found)

        # Bias indicator
        bias_direction = "neutral"
        if masculine_count >= feminine_count + 3:
            bias_direction = "masculine"
        elif feminine_count >= masculine_count + 3:
            bias_direction = "feminine"

        suggestions = []
        for w in set(masculine_found):
            if w in NEUTRAL_REPLACEMENTS:
                suggestions.append({
                    "word": w,
                    "replace_with": NEUTRAL_REPLACEMENTS[w],
                    "reason": "masculine-coded language may reduce female applicant pool",
                })

        return {
            "masculine_coded_words": list(set(masculine_found))[:10],
            "feminine_coded_words":  list(set(feminine_found))[:10],
            "masculine_count":       masculine_count,
            "feminine_count":        feminine_count,
            "bias_direction":        bias_direction,
            "is_biased":             bias_direction != "neutral",
            "suggestions":           suggestions,
            "research_note": (
                "Gaucher et al. (2011): masculine-coded job ads deter qualified women. "
                "Recommendation: balance or neutralize coded language."
            ),
        }


# ── Institution Bias Detector ─────────────────────────────────────────────────

class InstitutionBiasDetector:
    """
    Flags when a shortlist is over-concentrated in elite institutions.
    A shortlist where 80%+ are from IIT/IIM may miss 99.9% of Indian talent.

    Checks:
    - Elite institution concentration ratio
    - Whether any Tier-3 candidates are present
    - Whether any Tier-2 candidates are present
    """

    def analyze(self, candidates: list[dict]) -> dict:
        tiers = [_institution_tier(c.get("institution", "")) for c in candidates]
        tier_counts = Counter(tiers)
        total = max(len(tiers), 1)

        elite_ratio = tier_counts.get("tier_1", 0) / total
        has_tier_2  = tier_counts.get("tier_2", 0) > 0
        has_tier_3  = tier_counts.get("tier_3", 0) > 0
        unknown_pct = tier_counts.get("unknown", 0) / total

        bias_detected = elite_ratio > 0.70

        return {
            "tier_distribution": dict(tier_counts),
            "elite_concentration": round(elite_ratio, 3),
            "has_tier_2_candidates": has_tier_2,
            "has_tier_3_candidates": has_tier_3,
            "unknown_institution_pct": round(unknown_pct, 3),
            "institution_bias_detected": bias_detected,
            "recommendation": (
                "Shortlist is heavily concentrated in elite institutions. "
                "Consider lowering institution_tier_score weight or enabling "
                "MMR diversity reranking."
                if bias_detected
                else "Institution diversity appears healthy."
            ),
        }


# ── Diversity Score Calculator ────────────────────────────────────────────────

class DiversityScoreCalculator:
    """
    Computes Shannon entropy of the shortlist across institution tiers.
    Higher entropy = more diverse pipeline.

    H = -Σ p_i * log2(p_i)

    Max H for 3 tiers = log2(3) ≈ 1.585 bits
    Normalized diversity_score = H / max_H ∈ [0, 1]
    """

    def score(self, candidates: list[dict]) -> dict:
        if not candidates:
            return {"diversity_score": 0.0, "entropy_bits": 0.0, "tier_distribution": {}}

        tiers = [_institution_tier(c.get("institution", "")) for c in candidates]
        tier_counts = Counter(tiers)
        total = len(tiers)
        probs = [count / total for count in tier_counts.values()]

        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(len(tier_counts)) if len(tier_counts) > 1 else 1.0
        diversity_score = entropy / max_entropy if max_entropy > 0 else 0.0

        return {
            "diversity_score":    round(diversity_score, 4),
            "entropy_bits":       round(entropy, 4),
            "max_entropy_bits":   round(max_entropy, 4),
            "tier_distribution":  dict(tier_counts),
            "rating": (
                "excellent" if diversity_score > 0.80
                else "good" if diversity_score > 0.55
                else "moderate" if diversity_score > 0.30
                else "low"
            ),
        }


# ── JD Cleaner ────────────────────────────────────────────────────────────────

class JDCleaner:
    """
    Rewrites JD to remove exclusionary language.
    Rule-based + replacement dictionary. Returns cleaned JD text.
    """

    EXCLUSIONARY_PATTERNS = [
        (r"\b(males? only|male candidates? only)\b", "all genders welcome"),
        (r"\b(females? only|female candidates? only)\b", "all genders welcome"),
        (r"\b(men preferred|male preferred)\b", "qualified candidates welcome"),
        (r"\bfreshers? from IIT[s]?\b", "freshers from any accredited university"),
        (r"\bonly IIT[IM]* graduates?\b", "graduates from top engineering or management programs"),
        (r"\bmarried preferred\b", ""),
        (r"\bsingle preferred\b", ""),
    ]

    def clean(self, jd_text: str) -> dict:
        cleaned = jd_text
        changes: list[dict] = []

        for pattern, replacement in self.EXCLUSIONARY_PATTERNS:
            matches = re.findall(pattern, cleaned, flags=re.IGNORECASE)
            if matches:
                for m in matches:
                    changes.append({
                        "original": m,
                        "replacement": replacement,
                        "rule": pattern,
                    })
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # Replace neutral substitutes
        for original, neutral in NEUTRAL_REPLACEMENTS.items():
            if re.search(r"\b" + original + r"\b", cleaned, flags=re.IGNORECASE):
                changes.append({"original": original, "replacement": neutral, "rule": "gender_neutral_substitution"})
                cleaned = re.sub(r"\b" + original + r"\b", neutral, cleaned, flags=re.IGNORECASE)

        return {
            "original_text": jd_text,
            "cleaned_text":  cleaned,
            "changes_made":  len(changes),
            "changes":       changes,
            "is_modified":   len(changes) > 0,
        }


# ── DiverseHire™ Engine ───────────────────────────────────────────────────────

class DiverseHireEngine:
    """
    Master DiverseHire™ orchestrator.

    Usage in pipeline:
      diverse_hire = DiverseHireEngine()
      jd_diversity = diverse_hire.analyze_jd(jd_text)
      shortlist_diversity = diverse_hire.score_shortlist(candidates)
    """

    def __init__(self) -> None:
        self.gender_analyzer    = GenderLanguageAnalyzer()
        self.institution_bias   = InstitutionBiasDetector()
        self.diversity_score    = DiversityScoreCalculator()
        self.jd_cleaner         = JDCleaner()

    def analyze_jd(self, jd_text: str) -> dict:
        """Full JD diversity analysis: gender language + prohibited attributes."""
        gender = self.gender_analyzer.analyze(jd_text)
        clean  = self.jd_cleaner.clean(jd_text)
        return {
            "gender_language": gender,
            "jd_cleaner":      clean,
            "overall_jd_bias_score": round(
                (1.0 if gender["is_biased"] else 0.0) * 0.5 +
                (1.0 if clean["is_modified"] else 0.0) * 0.5,
                2,
            ),
        }

    def score_shortlist(self, candidates: list[dict]) -> dict:
        """Compute diversity metrics for the current shortlist."""
        institution = self.institution_bias.analyze(candidates)
        entropy     = self.diversity_score.score(candidates)
        return {
            "institution_bias":   institution,
            "diversity_score":    entropy,
            "recommendation": (
                "Shortlist diversity is strong — good representation across tiers."
                if entropy["diversity_score"] > 0.55
                else "Consider enabling DiverseHire™ MMR reranking to improve shortlist diversity."
            ),
        }

    def full_report(self, jd_text: str, candidates: list[dict]) -> dict:
        return {
            "jd_analysis":       self.analyze_jd(jd_text),
            "shortlist_analysis": self.score_shortlist(candidates),
        }

# ── Backwards Compatibility Adapters for Tests ────────────────────────────────

class JdBiasAnalyzer:
    def __init__(self):
        self.engine = DiverseHireEngine()
        
    def analyze(self, jd_text: str) -> dict:
        res = self.engine.analyze_jd(jd_text)
        return {
            "masculine_coded_count": res["gender_language"]["masculine_count"],
            "feminine_coded_count": res["gender_language"]["feminine_count"],
            "masculine_coded_words": res["gender_language"]["masculine_coded_words"],
            "feminine_coded_words": res["gender_language"]["feminine_coded_words"],
            "overall_bias_score": res["overall_jd_bias_score"],
            "has_prohibited_attributes": res["jd_cleaner"]["is_modified"],
        }
        
    def suggest_cleaned_jd(self, jd_text: str) -> str:
        return self.engine.jd_cleaner.clean(jd_text)["cleaned_text"]

class ShortlistDiversityScorer:
    def __init__(self):
        self.calc = DiversityScoreCalculator()
        
    def score(self, candidates: list[dict]) -> dict:
        res = self.calc.score(candidates)
        return {
            "shannon_entropy": res["entropy_bits"],
            "tier_breakdown": res["tier_distribution"]
        }
