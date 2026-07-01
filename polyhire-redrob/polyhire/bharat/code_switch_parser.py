"""BIL-3 Pass 1: dictionary + regex Hinglish/code-switch skill term normalizer."""
from __future__ import annotations
import json
import re
from pathlib import Path

DEFAULT_LEXICON = {
    "python mein": "python", "java mein": "java", "ml ka kaam": "machine learning",
    "data ka kaam": "data engineering", "backend pe kaam": "backend development",
    "cloud pe deploy": "cloud deployment", "model train kiya": "model training",
}


class CodeSwitchParser:
    def __init__(self, lexicon_path: str = "data/bharat/hinglish_lexicon.json"):
        self.lexicon = dict(DEFAULT_LEXICON)
        path = Path(lexicon_path)
        if path.exists():
            self.lexicon.update(json.loads(path.read_text(encoding="utf-8")))

    def normalize(self, text: str) -> str:
        if not text:
            return text
        out = text
        for phrase, canonical in self.lexicon.items():
            out = re.sub(re.escape(phrase), canonical, out, flags=re.IGNORECASE)
        return out
