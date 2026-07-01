"""BIL Orchestrator — combines BIL-1..4 into a bounded multiplier."""
from __future__ import annotations
from .institution_intelligence import InstitutionIntelligence
from .code_switch_parser import CodeSwitchParser
from .informal_sector_translator import informal_sector_boost


class BharatContextualizer:
    def __init__(self, institution_table_path: str, lexicon_path: str):
        self.institutions = InstitutionIntelligence(institution_table_path)
        self.parser = CodeSwitchParser(lexicon_path)

    def adjustment(self, candidate: dict) -> float:
        edu_score = self.institutions.score(candidate.get("education", []))
        edu_component = 1.0 + (edu_score - 0.6) * 0.10

        summary = candidate.get("profile", {}).get("summary", "")
        informal_component = 1.0 + informal_sector_boost(summary)

        adjustment = edu_component * informal_component
        return max(0.85, min(1.15, adjustment))

    def normalize_text(self, text: str) -> str:
        return self.parser.normalize(text)
