"""
Bonus Differentiator 4 — Candidate skill-gap reports (Gemma 4 E2B via llama.cpp).

For near-miss candidates (rank 21–40), generates a warm, specific, 3-bullet
development plan that turns a silent rejection into actionable feedback.
Falls back to a deterministic templated report when the GGUF weights aren't
present, so the feature always produces output.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)

SKILL_GAP_PROMPT = (
    "A candidate applied for a {role} role and ranked just outside the shortlist. "
    "Their profile shows: {summary}. "
    "The skills they're missing relative to the role: {missing}. "
    "Write a warm, specific, 3-bullet-point development plan to help them close the gap."
)


def _templated_report(role: str, summary: str, missing: list[str]) -> str:
    bullets: list[str] = []
    if missing:
        bullets.append(f"- Close the top skill gap: focus first on **{missing[0]}**, "
                       f"the most-cited requirement you don't yet list.")
        if len(missing) > 1:
            bullets.append(f"- Build adjacent depth in **{missing[1]}** — it appears alongside "
                           f"your existing strengths in similar role profiles.")
        bullets.append(f"- Reapply in 3–6 months with 1–2 portfolio projects demonstrating "
                       f"{', '.join(missing[:2])} in a {role.lower()} context.")
    else:
        bullets.append(f"- You're close on skills for the {role} role — the gap is likely depth of "
                       f"experience, not coverage. Seek stretch projects that broaden scope.")
        bullets.append(f"- Quantify impact on your profile: lead with measurable outcomes from "
                       f"your most recent work, not just responsibilities.")
        bullets.append(f"- Reapply once you can point to one additional year of ownership in "
                       f"{role.lower()}-scale problems.")
    header = f"Skill-gap report — {role}\n\nSummary: {summary or '(not provided)'}\n"
    return header + "\n" + "\n".join(bullets)


class SkillGapGenerator:
    def __init__(self) -> None:
        self._llm: Any = None
        self._load_attempted = False
        self._available = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        if not settings.enable_skill_gap_reports:
            return
        path = Path(settings.gemma_gguf_path)
        if not path.exists():
            log.info(
                "Gemma GGUF not found at %s — skill-gap reports will use the templated generator. "
                "Run scripts/download_models.sh to enable Gemma 4 E2B.",
                path,
            )
            return
        try:
            from llama_cpp import Llama  # type: ignore

            log.info("Loading Gemma 4 E2B from %s …", path)
            self._llm = Llama(model_path=str(path), n_ctx=4096, verbose=False)
            self._available = True
            log.info("Gemma skill-gap generator ready.")
        except Exception as exc:  # noqa: BLE001
            log.warning("llama-cpp-python unavailable (%s); using templated reports.", exc)

    def is_available(self) -> bool:
        self._ensure_model()
        return self._available

    def generate(self, jd: dict[str, Any], candidate_profile: dict[str, Any]) -> str:
        role = str(jd.get("role_title", "the role"))
        summary = str(candidate_profile.get("summary", ""))
        missing = list(set(jd.get("must_have_skills", []) or []) - set(candidate_profile.get("skills", []) or []))

        self._ensure_model()
        if self._llm is None:
            return _templated_report(role, summary, missing)

        missing_str = ", ".join(missing) or "none major — close call on experience depth"
        prompt = SKILL_GAP_PROMPT.format(role=role, summary=summary, missing=missing_str)
        try:
            output = self._llm(prompt, max_tokens=200, temperature=0.4, stop=["\n\n\n"])
            text = output["choices"][0]["text"].strip()
            return text or _templated_report(role, summary, missing)
        except Exception as exc:  # noqa: BLE001
            log.warning("Gemma generation failed (%s); using templated report.", exc)
            return _templated_report(role, summary, missing)
