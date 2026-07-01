"""
Bonus Differentiator 1 — IndicTrans2 multilingual JD support.

Recruiter submits a JD in Hindi (or any supported Indic language); it is
auto-translated to English before Stage 1 parsing. Falls back to a no-op
pass-through when the model can't be loaded or when input is already English.
"""
from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)


class Translator:
    def __init__(self) -> None:
        self._model: Any = None
        self._tokenizer: Any = None
        self._ip: Any = None
        self._load_attempted = False
        self._available = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        if not settings.enable_hindi_translation:
            return
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

            try:
                from IndicTransToolkit.processor import IndicProcessor  # type: ignore
            except Exception:  # noqa: BLE001
                IndicProcessor = None  # type: ignore[assignment]

            name = settings.indictrans_model
            log.info("Loading IndicTrans2 model %s …", name)
            self._tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=True)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=True)
            self._ip = IndicProcessor(inference=True) if IndicProcessor else None
            self._available = True
            log.info("IndicTrans2 loaded.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "IndicTrans2 unavailable (%s). Hindi JDs will pass through untranslated. "
                "Install with: pip install IndicTransToolkit transformers torch",
                exc,
            )
            self._available = False

    def is_available(self) -> bool:
        self._ensure_model()
        return self._available

    def translate_to_english(self, text: str, src_lang: str = "hin_Deva") -> str:
        """Translate Indic text → English. Returns original text if unavailable."""
        self._ensure_model()
        if not self._available or self._model is None:
            log.info("Translator unavailable — returning original text.")
            return text
        try:
            batch = (
                self._ip.preprocess_batch([text], src_lang=src_lang, tgt_lang="eng_Latn")
                if self._ip
                else [text]
            )
            import torch

            inputs = self._tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
            with torch.no_grad():
                outputs = self._model.generate(**inputs, max_length=256, num_beams=5)
            decoded = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)
            if self._ip:
                decoded = self._ip.postprocess_batch(decoded, lang="eng_Latn")
            return decoded[0] if decoded else text
        except Exception as exc:  # noqa: BLE001
            log.warning("Translation failed (%s); returning original text.", exc)
            return text

    # Convenience alias matching the PRD naming.
    def hindi_to_english(self, text: str) -> str:
        return self.translate_to_english(text, src_lang="hin_Deva")
