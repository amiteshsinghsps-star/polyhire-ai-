"""InputSanitizer — defense-in-depth for free-text fields (Phase B safe, zero network)."""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field

INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(previous|all|above|prior|your)\s+instructions?", "direct_override"),
    (r"disregard\s+(all|previous|prior|your)\s+", "disregard_override"),
    (r"forget\s+(everything|all|your|previous)", "forget_override"),
    (r"you\s+are\s+now\s+", "role_hijack"),
    (r"act\s+as\s+(a|an|the)\s+", "role_hijack"),
    (r"(reveal|show|print|output)\s+(your\s+)?(system\s+prompt|instructions?)", "prompt_extract"),
    (r"(set|make|give|assign)\s+(all|every)\s+candidates?\s+(score|rank)", "score_manipulation"),
    (r"score\s*=\s*[01](\.\d+)?", "direct_score_injection"),
    (r"\[INST\]|\[/INST\]|<\|system\|>|<\|user\|>", "token_injection"),
    (r"###\s*(System|Instruction|Override)", "markdown_injection"),
]

FORBIDDEN_CHARS = [chr(c) for c in range(0, 9)] + [chr(11), chr(12)] + [chr(c) for c in range(14, 32)]

SEVERITY = {
    "direct_override": "critical", "disregard_override": "critical",
    "forget_override": "critical", "role_hijack": "high",
    "prompt_extract": "high", "score_manipulation": "critical",
    "direct_score_injection": "critical", "token_injection": "high",
    "markdown_injection": "medium",
}


@dataclass
class SanitizationResult:
    sanitized_text: str
    is_safe: bool
    flags: list[str] = field(default_factory=list)
    severity: str = "none"
    input_hash: str = ""


class InputSanitizer:
    _ORDER = ["none", "low", "medium", "high", "critical"]

    def sanitize(self, text: str, context: str = "field") -> SanitizationResult:
        if not text:
            return SanitizationResult(sanitized_text="", is_safe=True)

        input_hash = hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:16]
        flags: list[str] = []
        max_sev = "none"
        cleaned = text

        for pattern, tag in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                sev = SEVERITY.get(tag, "medium")
                flags.append(f"{tag}:{sev}")
                if self._ORDER.index(sev) > self._ORDER.index(max_sev):
                    max_sev = sev

        if max_sev in ("critical", "high", "medium"):
            for pattern, _ in INJECTION_PATTERNS:
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        for ch in FORBIDDEN_CHARS:
            cleaned = cleaned.replace(ch, "")

        cleaned = re.sub(r"\s{4,}", " ", cleaned).strip()
        if len(cleaned) > 4000:
            cleaned = cleaned[:4000]

        return SanitizationResult(
            sanitized_text=cleaned,
            is_safe=(max_sev != "critical"),
            flags=flags,
            severity=max_sev,
            input_hash=input_hash,
        )

    def sanitize_candidate(self, candidate: dict) -> tuple[dict, list[str]]:
        all_flags: list[str] = []
        prof = candidate.get("profile", {})
        for field_name in ("summary", "headline"):
            if prof.get(field_name):
                res = self.sanitize(prof[field_name], context=field_name)
                prof[field_name] = res.sanitized_text
                all_flags.extend(res.flags)
        for role in candidate.get("career_history", []):
            if role.get("description"):
                res = self.sanitize(role["description"], context="career_history.description")
                role["description"] = res.sanitized_text
                all_flags.extend(res.flags)
        return candidate, all_flags
