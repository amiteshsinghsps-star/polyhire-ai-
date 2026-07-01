"""
Enterprise Feature §23.7 — Auto-Generated Interview Question Engine.

Generates 3-5 interview questions per shortlisted candidate, specifically
targeting their uncertain or borderline skill claims, using fusion-ranker
feature contributions to identify what most needs probing.
"""
from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

QUESTION_GEN_PROMPT = """A candidate is shortlisted for {role_title}. Their profile claims
these skills: {claimed_skills}. Our system has LOW confidence specifically on: {uncertain_skills}
(based on shallow resume evidence vs. the depth the role requires).

Generate 4 interview questions:
- 2 should be targeted probes of the LOW-confidence skills specifically — designed to
  surface real depth vs. surface familiarity in 2-3 minutes of conversation.
- 2 should validate their strongest, highest-confidence claimed strength, to confirm
  it's genuinely as strong as the profile suggests.

Return as a JSON list of {{"question": "...", "probes_for": "...", "what_a_strong_answer_sounds_like": "..."}}.
Return ONLY valid JSON, no extra text."""


class InterviewQuestionGenerator:
    """
    Generates targeted interview questions based on fusion ranker feature
    contributions. Falls back to templated questions when Groq is unavailable.
    """

    def __init__(self) -> None:
        self._groq_client: Any = None

    def _ensure_client(self) -> None:
        if self._groq_client is not None:
            return
        from app.config import get_settings as _gs

        settings = _gs()
        if settings.groq_api_key:
            try:
                from groq import Groq  # type: ignore

                self._groq_client = Groq(api_key=settings.groq_api_key)
                log.info("Groq client initialized for interview question generation.")
            except Exception as exc:  # noqa: BLE001
                log.warning("Groq init failed (%s).", exc)

    def generate(
        self,
        role_title: str,
        claimed_skills: list[str],
        uncertain_skills: list[str],
    ) -> list[dict[str, str]]:
        """Returns list of {question, probes_for, what_a_strong_answer_sounds_like}."""
        self._ensure_client()

        if self._groq_client:
            try:
                completion = self._groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{
                        "role": "user",
                        "content": QUESTION_GEN_PROMPT.format(
                            role_title=role_title,
                            claimed_skills=", ".join(claimed_skills) if claimed_skills else "not specified",
                            uncertain_skills=", ".join(uncertain_skills) if uncertain_skills else "none flagged",
                        ),
                    }],
                    temperature=0.4,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                text = completion.choices[0].message.content
                if text:
                    parsed = json.loads(text)
                    # Handle both {questions: [...]} and [...]
                    if isinstance(parsed, dict):
                        questions = parsed.get("questions", parsed.get("interview_questions", []))
                    elif isinstance(parsed, list):
                        questions = parsed
                    else:
                        questions = []
                    return questions[:4]
            except Exception as exc:  # noqa: BLE001
                log.warning("Groq question gen failed (%s), using templates.", exc)

        return self._templated_questions(role_title, claimed_skills, uncertain_skills)

    def _templated_questions(
        self,
        role_title: str,
        claimed_skills: list[str],
        uncertain_skills: list[str],
    ) -> list[dict[str, str]]:
        """Fallback templated questions."""
        questions: list[dict[str, str]] = []

        # Probe uncertain skills
        for skill in uncertain_skills[:2]:
            questions.append({
                "question": (
                    f"Your profile mentions {skill} — can you walk me through a specific "
                    f"project where you applied {skill} to solve a non-trivial problem?"
                ),
                "probes_for": skill,
                "what_a_strong_answer_sounds_like": (
                    f"Describes concrete architecture decisions, trade-offs, or measurable "
                    f"outcomes involving {skill}."
                ),
            })

        # Validate strong skills
        for skill in (claimed_skills[:2] if claimed_skills else ["their domain expertise"]):
            questions.append({
                "question": (
                    f"You've worked extensively with {skill}. What's the most common "
                    f"misconception people have about {skill} in production, and how do you handle it?"
                ),
                "probes_for": skill,
                "what_a_strong_answer_sounds_like": (
                    f"Demonstrates deep understanding beyond surface-level usage, with "
                    f"nuanced opinions informed by real experience."
                ),
            })

        # Role-specific
        questions.append({
            "question": (
                f"For a {role_title} role, what do you think is the most underrated skill, "
                f"and how has it helped you in your career?"
            ),
            "probes_for": "general-fit",
            "what_a_strong_answer_sounds_like": (
                "Shows strategic thinking and self-awareness beyond technical skills."
            ),
        })

        return questions[:4]

    def is_available(self) -> bool:
        self._ensure_client()
        return self._groq_client is not None
