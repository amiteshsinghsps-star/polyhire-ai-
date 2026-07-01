"""BIL-2: India institution prestige scoring, NIRF-informed, with safe fallback."""
from __future__ import annotations
import json
from pathlib import Path

_DEFAULT_BY_SCHEMA_TIER = {
    "tier_1": 0.90, "tier_2": 0.70, "tier_3": 0.50, "tier_4": 0.35, "unknown": 0.45,
}


class InstitutionIntelligence:
    def __init__(self, table_path: str = "data/bharat/institution_tiers.json"):
        self.table: dict[str, float] = {}
        path = Path(table_path)
        if path.exists():
            self.table = json.loads(path.read_text(encoding="utf-8"))

    def score(self, education: list[dict]) -> float:
        if not education:
            return 0.45
        best = 0.0
        for edu in education:
            name = (edu.get("institution") or "").strip().lower()
            if name in self.table:
                best = max(best, self.table[name])
            else:
                schema_tier = edu.get("tier", "unknown")
                best = max(best, _DEFAULT_BY_SCHEMA_TIER.get(schema_tier, 0.45))
        return best
