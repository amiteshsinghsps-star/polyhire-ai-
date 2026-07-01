"""
Bonus Differentiator 2 — faster-whisper voice JD input.

Recruiter speaks the JD; it is transcribed (auto-detecting Hindi/English)
and piped into the same parsing pipeline. Gracefully unavailable when
faster-whisper isn't installed — the gateway will only expose the voice
button when this reports availability.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)


class VoiceTranscriber:
    def __init__(self) -> None:
        self._model: Any = None
        self._load_attempted = False
        self._available = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        if not settings.enable_voice_input:
            return
        try:
            from faster_whisper import WhisperModel  # type: ignore

            log.info("Loading faster-whisper '%s' …", settings.whisper_model_size)
            self._model = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
            self._available = True
            log.info("Voice transcriber ready.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "faster-whisper unavailable (%s). Install with: pip install faster-whisper",
                exc,
            )
            self._available = False

    def is_available(self) -> bool:
        self._ensure_model()
        return self._available

    def transcribe(self, audio_path: str) -> str:
        self._ensure_model()
        if not self._available or self._model is None:
            raise RuntimeError("Voice transcription is not available in this build.")
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        segments, _ = self._model.transcribe(audio_path, language=None)  # auto-detect
        return " ".join(seg.text for seg in segments).strip()
