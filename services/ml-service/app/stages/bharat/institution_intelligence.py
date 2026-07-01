"""
BIL-2: India Institution Intelligence.

Maps Indian educational institutions to a tier score using NIRF 2025 rankings
(Ministry of Education, Government of India — public data). Produces an
institution_tier_score in [0, 1] injected as a new feature into the fusion ranker.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

log = logging.getLogger(__name__)

# ── NIRF 2025 — Top institutions by category ───────────────────────────────
# Tier A (0.90-1.00): NIRF rank 1-25
# Tier B (0.75-0.89): NIRF rank 26-75
# Tier C (0.60-0.74): NIRF rank 76-200 + State universities of repute
# Tier D (0.45-0.59): Other recognized universities, autonomous colleges
# Tier E (0.30-0.44): Affiliating colleges, private colleges (unranked)

NIRF_INSTITUTION_SCORES: dict[str, float] = {
    # ── IITs ────────────────────────────────────────────────────────────────
    "iit madras": 1.00, "iit bombay": 0.99,
    "iit delhi": 0.98, "iit kharagpur": 0.97,
    "iit kanpur": 0.96, "iit roorkee": 0.95,
    "iit guwahati": 0.94, "iit hyderabad": 0.93,
    "iit bhu": 0.92, "iit tirupati": 0.88,
    "iit jodhpur": 0.87, "iit mandi": 0.86,
    "iit patna": 0.86, "iit gandhinagar": 0.88,
    "iit indore": 0.89, "iit ism dhanbad": 0.85,
    "iit bhilai": 0.84, "iit jammu": 0.83,
    "iit palakkad": 0.82, "iit dharwad": 0.81,
    # ── IISc, IIIT, NIT ─────────────────────────────────────────────────────
    "iisc bangalore": 1.00, "iisc": 1.00,
    "indian institute of science": 1.00,
    "iiit hyderabad": 0.92, "iiit delhi": 0.88,
    "iiit bangalore": 0.85, "iiit allahabad": 0.83,
    # ── NITs ────────────────────────────────────────────────────────────────
    "nit trichy": 0.87, "nit tiruchirappalli": 0.87,
    "nit surathkal": 0.86, "nit karnataka": 0.86,
    "nit warangal": 0.86, "nit rourkela": 0.85,
    "nit calicut": 0.84, "nit kozhikode": 0.84,
    "nit nagpur": 0.83, "vnit nagpur": 0.83,
    "nit jamshedpur": 0.82, "nit allahabad": 0.82,
    "nit motilal nehru": 0.83, "mnnit allahabad": 0.83,
    "nit kurukshetra": 0.81, "nit durgapur": 0.81,
    "nit bhopal": 0.80, "manit bhopal": 0.80,
    "nit srinagar": 0.79, "nit silchar": 0.79,
    "nit patna": 0.78, "nit agartala": 0.77,
    "nit manipur": 0.76, "nit mizoram": 0.75,
    # ── Top IIITs ───────────────────────────────────────────────────────────
    "iiit kancheepuram": 0.80, "iiit vadodara": 0.78,
    "iiit kota": 0.76, "iiit jabalpur": 0.76,
    "iiit guwahati": 0.75, "iiit lucknow": 0.75,
    # ── Top Central Universities ─────────────────────────────────────────────
    "jadavpur university": 0.85, "university of hyderabad": 0.83,
    "bhu varanasi": 0.80, "banaras hindu university": 0.80,
    "jnu new delhi": 0.82, "jawaharlal nehru university": 0.82,
    "du delhi": 0.79, "university of delhi": 0.79,
    "amu aligarh": 0.75, "aligarh muslim university": 0.75,
    "hcu hyderabad": 0.78, "tezpur university": 0.74,
    # ── Top Private Universities ─────────────────────────────────────────────
    "bits pilani": 0.90, "birla institute": 0.89,
    "vit vellore": 0.78, "vit university": 0.78,
    "manipal university": 0.74, "manipal institute": 0.74,
    "srm university": 0.70, "srm institute": 0.70,
    "amity university": 0.65,
    "symbiosis": 0.68, "symbiosis international": 0.68,
    "psg college": 0.73, "psg tech": 0.73,
    "thapar university": 0.76, "thapar institute": 0.76,
    "pes university": 0.72, "reva university": 0.65,
    "christ university": 0.67,
    # ── IIMs ────────────────────────────────────────────────────────────────
    "iim ahmedabad": 1.00, "iim bangalore": 0.99,
    "iim calcutta": 0.98, "iim lucknow": 0.95,
    "iim kozhikode": 0.93, "iim indore": 0.92,
    "iim shillong": 0.88, "iim trichy": 0.87,
    "iim rohtak": 0.86, "iim raipur": 0.85,
    "iim ranchi": 0.85, "iim kashipur": 0.84,
    "iim amritsar": 0.83, "iim bodhgaya": 0.82,
    "iim nagpur": 0.83, "iim sirmaur": 0.81,
    "iim udaipur": 0.82, "iim visakhapatnam": 0.82,
    "iim jammu": 0.81, "iim sambalpur": 0.80,
}

# Default scores by degree level when institution is not recognized.
DEGREE_DEFAULT_SCORES: dict[str, float] = {
    "phd": 0.72,
    "m.tech": 0.65, "mtech": 0.65,
    "m.e.": 0.63, "me": 0.63,
    "mca": 0.60,
    "mba": 0.62,
    "m.sc": 0.58, "msc": 0.58,
    "b.tech": 0.52, "btech": 0.52, "be": 0.52, "b.e.": 0.52,
    "bca": 0.48,
    "b.sc": 0.46, "bsc": 0.46,
    "bcom": 0.44,
    "ba": 0.43,
    "diploma": 0.38,
    "10+2": 0.30, "12th": 0.30,
    "10th": 0.25,
}


def _normalize_name(name: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace, strip punctuation."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


@lru_cache(maxsize=4096)
def _score_institution_cached(institution: str) -> tuple[float, str]:
    """Returns (score, match_type) — cached since institutions repeat across candidates."""
    normalized = _normalize_name(institution)

    # 1. Exact match
    if normalized in NIRF_INSTITUTION_SCORES:
        return NIRF_INSTITUTION_SCORES[normalized], "exact"

    # 2. Substring match (handles "IIT Bombay (Mumbai)" → "iit bombay")
    best_score, best_key = 0.0, ""
    for key, score in NIRF_INSTITUTION_SCORES.items():
        if key in normalized or normalized in key:
            if score > best_score:
                best_score, best_key = score, key
    if best_score > 0:
        return best_score, "substring"

    # 3. Token overlap — catches "Indian Institute of Technology Madras"
    tokens = set(normalized.split())
    best_overlap, best_key = 0.0, ""
    for key, score in NIRF_INSTITUTION_SCORES.items():
        key_tokens = set(key.split())
        overlap = len(tokens & key_tokens) / max(len(key_tokens), 1)
        if overlap >= 0.6 and score > best_overlap:
            best_overlap, best_key = score, key
    if best_overlap > 0:
        return NIRF_INSTITUTION_SCORES[best_key], "token_overlap"

    # 4. IIT/NIT/IIIT pattern match for unlisted branches
    if re.search(r"\biit\b", normalized):
        return 0.84, "iit_pattern"
    if re.search(r"\bnit\b", normalized):
        return 0.77, "nit_pattern"
    if re.search(r"\biiit\b", normalized):
        return 0.73, "iiit_pattern"
    if re.search(r"\biim\b", normalized):
        return 0.82, "iim_pattern"
    if re.search(r"\biisc\b", normalized):
        return 0.97, "iisc_pattern"

    return 0.0, "not_found"


@dataclass
class InstitutionScore:
    institution_name: str
    raw_name: str
    score: float
    match_type: str
    degree_bonus: float
    final_score: float
    in_nirf_database: bool


class IndiaInstitutionIntelligence:
    """
    BIL-2: Maps Indian educational institutions to a NIRF-calibrated prestige score.
    Injected as a new feature 'institution_tier_score' into the fusion ranker.
    """

    def score_candidate(
        self,
        institution: Optional[str],
        degree: Optional[str] = None,
    ) -> InstitutionScore:
        if not institution:
            raw_score, match_type = 0.50, "missing"
        else:
            raw_score, match_type = _score_institution_cached(institution)

        # Degree-level fallback when institution is unrecognized.
        degree_bonus = 0.0
        if raw_score == 0.0 and degree:
            degree_lower = degree.lower().strip()
            for degree_key, default in DEGREE_DEFAULT_SCORES.items():
                if degree_key in degree_lower:
                    raw_score = default
                    degree_bonus = default
                    match_type = "degree_default"
                    break

        if raw_score == 0.0:
            raw_score = 0.42  # completely unknown — avoid punishing unfairly

        final = round(min(1.0, raw_score), 4)
        return InstitutionScore(
            institution_name=_normalize_name(institution) if institution else "",
            raw_name=institution or "",
            score=raw_score,
            match_type=match_type,
            degree_bonus=degree_bonus,
            final_score=final,
            in_nirf_database=(match_type not in ("missing", "not_found", "degree_default")),
        )

    def score_batch(self, candidates: list[dict]) -> list[dict]:
        """Inject institution_tier_score into each candidate dict."""
        for c in candidates:
            education = c.get("education", [])
            if isinstance(education, list) and education:
                best = max(
                    (
                        self.score_candidate(
                            e.get("institution") or e.get("college") or e.get("school"),
                            e.get("degree"),
                        )
                        for e in education
                    ),
                    key=lambda s: s.final_score,
                    default=None,
                )
                if best:
                    c["institution_tier_score"] = best.final_score
                    c["institution_nirf_matched"] = best.in_nirf_database
            elif c.get("institution"):
                result = self.score_candidate(c["institution"], c.get("degree"))
                c["institution_tier_score"] = result.final_score
                c["institution_nirf_matched"] = result.in_nirf_database
            else:
                c.setdefault("institution_tier_score", 0.50)
                c.setdefault("institution_nirf_matched", False)
        return candidates
