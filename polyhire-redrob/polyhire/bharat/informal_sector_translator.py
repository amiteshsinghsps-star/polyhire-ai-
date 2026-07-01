"""BIL-4: maps informal-sector experience phrases to formal skill credit, capped low."""
from __future__ import annotations
import re

INFORMAL_PATTERNS: dict[str, dict[str, float]] = {
    r"family business": {"operations": 0.3, "stakeholder management": 0.3},
    r"freelance": {"project management": 0.3, "client communication": 0.3},
    r"self[- ]taught": {"independent learning": 0.2},
    r"side project": {"independent learning": 0.2, "shipping": 0.25},
}


def informal_sector_boost(text: str) -> float:
    if not text:
        return 0.0
    hits = sum(1 for pattern in INFORMAL_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    return min(0.08, hits * 0.03)
