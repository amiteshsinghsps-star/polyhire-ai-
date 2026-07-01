"""
PromptInjectionSanitizer
========================
Defends all LLM input (JD text, candidate summaries passed to Groq)
against prompt injection attacks. Called BEFORE every Gemini/Groq API call.

Integration:
  from .security.prompt_guard import PromptInjectionSanitizer
  guard = PromptInjectionSanitizer()
  safe_text, flags = guard.sanitize(raw_jd_text)
  if flags:
      log_security_event("prompt_injection_attempt", flags)
  # use safe_text for Gemini call
"""

from __future__ import annotations
import re
import hashlib
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns that indicate prompt injection attempts
# ---------------------------------------------------------------------------
INJECTION_PATTERNS: list[tuple[str, str]] = [
    # Direct instruction override
    (r"ignore\s+(previous|all|above|prior|your)\s+instructions?",         "direct_override"),
    (r"disregard\s+(all|previous|prior|your)\s+",                          "disregard_override"),
    (r"forget\s+(everything|all|your|previous)",                           "forget_override"),
    (r"override\s+(your|the|all)\s+(instructions?|rules?|guidelines?)",    "rule_override"),
    # Role hijacking
    (r"you\s+are\s+now\s+",                                                "role_hijack"),
    (r"act\s+as\s+(a|an|the)\s+",                                          "role_hijack"),
    (r"pretend\s+(you|to)\s+(are|be)\s+",                                  "role_hijack"),
    (r"from\s+now\s+on\s+(you\s+are|act\s+as)",                            "role_hijack"),
    (r"new\s+(persona|role|identity|character)",                            "role_hijack"),
    # System prompt extraction
    (r"(reveal|show|print|output|display|repeat)\s+(your\s+)?(system\s+prompt|instructions?)", "system_prompt_extract"),
    (r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",            "system_prompt_extract"),
    (r"tell\s+me\s+your\s+(prompt|instructions?|system)",                  "system_prompt_extract"),
    # Score manipulation
    (r"(set|make|give|assign|return)\s+(all|every)\s+candidates?\s+(score|rank|rating)", "score_manipulation"),
    (r"fusion_score\s*=\s*[0-9\.]+",                                       "direct_score_injection"),
    (r"trust_score\s*=\s*[0-9\.]+",                                        "direct_score_injection"),
    (r"rank\s+(all|every)\s+candidates?\s+(as|at)\s+(first|1|top)",        "rank_manipulation"),
    # Jailbreaks
    (r"jailbreak",                                                          "jailbreak"),
    (r"DAN\s*(mode)?\s*:",                                                 "jailbreak"),
    (r"\[INST\]|\[/INST\]|<\|system\|>|<\|user\|>",                       "token_injection"),
    (r"###\s*(System|Instruction|Override)",                                "markdown_injection"),
    # Data exfiltration
    (r"(list|show|dump|export|extract)\s+(all|every)\s+(candidate|applicant|user)\s+(data|info|email|phone)", "data_exfil"),
    (r"(send|email|post|transmit)\s+(all|the)\s+(data|candidates?)",        "data_exfil"),
]

FORBIDDEN_CONTROL_CHARS = [chr(i) for i in range(32) if i not in (9, 10, 13)]  # keep tab, LF, CR


@dataclass
class SanitizationResult:
    original_text:   str
    sanitized_text:  str
    is_safe:         bool
    injection_flags: list[str] = field(default_factory=list)
    severity:        str = "none"   # "none" | "low" | "medium" | "high" | "critical"
    input_hash:      str = ""
    action_taken:    str = "pass"   # "pass" | "sanitize" | "block"


_SEVERITY_MAP: dict[str, str] = {
    "direct_override":        "critical",
    "disregard_override":     "critical",
    "forget_override":        "critical",
    "rule_override":          "critical",
    "role_hijack":            "high",
    "system_prompt_extract":  "high",
    "score_manipulation":     "critical",
    "direct_score_injection": "critical",
    "rank_manipulation":      "critical",
    "jailbreak":              "critical",
    "token_injection":        "high",
    "markdown_injection":     "medium",
    "data_exfil":             "critical",
}
_SEVERITY_ORDER = ["none", "low", "medium", "high", "critical"]


class PromptInjectionSanitizer:
    """
    Two-phase sanitizer:
    Phase 1 — Detection:   scan for injection patterns, assign severity
    Phase 2 — Remediation: strip/replace dangerous content

    Severity:
      critical → block (replace with [SECURITY_REDACTED])
      high     → strip + flag for manual review
      medium   → strip + log
      low      → log only, pass through
    """

    def sanitize(self, text: str, context: str = "jd_input") -> SanitizationResult:
        if not text:
            return SanitizationResult(original_text="", sanitized_text="", is_safe=True)

        input_hash = hashlib.sha256(text.encode()).hexdigest()
        flags: list[str] = []
        max_severity = "none"
        cleaned = text

        # Phase 1: Detection
        for pattern, flag_type in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                sev = _SEVERITY_MAP.get(flag_type, "medium")
                flags.append(f"{flag_type}:{sev}")
                if _SEVERITY_ORDER.index(sev) > _SEVERITY_ORDER.index(max_severity):
                    max_severity = sev
                logger.warning(
                    "[PromptGuard] Injection detected: %s | context=%s | hash=%s",
                    flag_type, context, input_hash[:8],
                )

        # Phase 2: Remediation
        if max_severity == "critical":
            for pattern, _ in INJECTION_PATTERNS:
                cleaned = re.sub(pattern, "[SECURITY_REDACTED]", cleaned, flags=re.IGNORECASE | re.DOTALL)
            action = "block"
        elif max_severity in ("high", "medium"):
            for pattern, _ in INJECTION_PATTERNS:
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
            action = "sanitize"
        else:
            action = "pass"

        # Strip forbidden control characters
        for ch in FORBIDDEN_CONTROL_CHARS:
            cleaned = cleaned.replace(ch, "")

        # Enforce hard length cap
        if len(cleaned) > 10_000:
            cleaned = cleaned[:10_000]
            flags.append("length_truncated:low")

        # Collapse excessive whitespace
        cleaned = re.sub(r"\s{4,}", " ", cleaned)

        is_safe = max_severity not in ("critical",)

        return SanitizationResult(
            original_text=text,
            sanitized_text=cleaned,
            is_safe=is_safe,
            injection_flags=flags,
            severity=max_severity,
            input_hash=input_hash,
            action_taken=action,
        )

    def sanitize_candidate_text(self, candidate: dict) -> tuple[dict, list[str]]:
        """Sanitize free-text fields in a candidate dict before passing to Groq."""
        all_flags: list[str] = []
        for field_name in ("summary", "cover_letter", "about"):
            if candidate.get(field_name):
                result = self.sanitize(candidate[field_name], context=f"candidate_{field_name}")
                candidate[field_name] = result.sanitized_text
                all_flags.extend(result.injection_flags)

        for role in candidate.get("title_history", []):
            if role.get("description"):
                result = self.sanitize(role["description"], context="title_history")
                role["description"] = result.sanitized_text
                all_flags.extend(result.injection_flags)

        return candidate, all_flags
