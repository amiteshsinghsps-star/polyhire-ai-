"""
Bonus Differentiator 3 — d4data/bias-detection-model JD bias flagging.

Surfaces exclusionary / biased language in the JD before candidates are
sourced. An ethical-AI safeguard that pushes the submission past a
plain ranking demo toward a deployable hiring-intelligence product.

Falls back to a small lexicon-based heuristic when the HF model can't load.
"""
from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)

# A compact lexicon for the offline fallback. Not exhaustive — only meant
# to keep the bias surface functional without the model weights.
_FALLBACK_LEXICON = [
    "young", "youthful", "recent graduate", "fresh graduate", "digital native",
    "rockstar", "ninja", "aggressive", "dominant", "salesman", "he/she", "he will",
    "native english speaker", "culture fit", "clean cut",
]


class BiasDetector:
    def __init__(self) -> None:
        self._classifier: Any = None
        self._load_attempted = False
        self._fallback = False

    def _ensure_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        settings = get_settings()
        if not settings.enable_bias_detection:
            self._fallback = True
            return
        try:
            from transformers import pipeline  # type: ignore

            log.info("Loading bias detection model %s …", settings.bias_model)
            self._classifier = pipeline(
                "text-classification", model=settings.bias_model, top_k=None
            )
            log.info("Bias detector loaded.")
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Bias model unavailable (%s). Using lexicon fallback. "
                "Run scripts/download_models.sh for the full classifier.",
                exc,
            )
            self._fallback = True

    def scan(self, jd_text: str) -> list[dict[str, Any]]:
        """
        Returns a list of {sentence, confidence, category?} flags.
        Empty list means no biased language detected.
        """
        if not jd_text or not jd_text.strip():
            return []
        self._ensure_model()
        sentences = [s.strip() for s in jd_text.replace("\n", ".").split(".") if len(s.strip()) > 3]

        if self._classifier is not None:
            return self._scan_model(sentences)
        return self._scan_lexicon(sentences)

    def _scan_model(self, sentences: list[str]) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        for sent in sentences:
            try:
                result = self._classifier(sent)[0]
            except Exception as exc:  # noqa: BLE001
                log.debug("Bias classifier failed on a sentence (%s); skipping.", exc)
                continue
            biased = next(
                (r for r in result if r["label"].lower() in {"biased", "label_1"} and r["score"] > 0.6),
                None,
            )
            if biased:
                flags.append({"sentence": sent, "confidence": float(biased["score"]), "category": "bias"})
        return flags

    def _scan_lexicon(self, sentences: list[str]) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        lower_lex = [w.lower() for w in _FALLBACK_LEXICON]
        for sent in sentences:
            low = sent.lower()
            hits = [w for w in lower_lex if w in low]
            if hits:
                flags.append(
                    {
                        "sentence": sent,
                        "confidence": 0.7,
                        "category": "lexicon:" + ",".join(hits[:3]),
                    }
                )
        return flags

    @property
    def is_fallback(self) -> bool:
        self._ensure_model()
        return self._fallback
