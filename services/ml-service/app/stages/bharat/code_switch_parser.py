"""
BIL-3: Code-Switch Resume Parser.

Detects and normalizes Hindi/Indic + English mixed text (code-switching) in resume
text before skill extraction and skill_overlap_ratio computation.

Two passes:
  Pass 1 — Transliteration: Hinglish technical terms (Roman-script Hindi) mapped
            to standard English equivalents using a curated lexicon.
  Pass 2 — Translation: Devanagari / other Indic script segments translated to
            English using IndicTrans2 (optional; static map fallback otherwise).

Output is an augmented skill set — original skills PLUS skills extracted from the
normalized text — ensuring no candidate is penalized for writing in a bilingual style.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# ── Pass 1: Hinglish technical term lexicon ────────────────────────────────
HINGLISH_TECH_LEXICON: dict[str, str] = {
    # Programming & Software (common misspellings in Indian resumes)
    "programing": "programming", "progaming": "programming",
    "softwear": "software", "hardwear": "hardware",
    "sever": "server", "seever": "server",
    "databse": "database", "datbase": "database",
    "intenet": "internet", "wesite": "website", "websit": "website",
    "applicaton": "application", "appication": "application",
    "devlopment": "development", "develoment": "development", "developpment": "development",
    "developement": "development",
    "managment": "management", "manegement": "management",
    "anlaysis": "analysis", "analyssis": "analysis",
    "machiene": "machine", "mchine": "machine",
    "algortihm": "algorithm", "algorythm": "algorithm",
    "artficial": "artificial", "artifcial": "artificial",
    "intellgence": "intelligence", "inteligence": "intelligence",
    "deploment": "deployment", "deployement": "deployment",
    "architeture": "architecture", "architecure": "architecture",
    "implimentation": "implementation", "implementaton": "implementation",
    "configuartion": "configuration", "configuuration": "configuration",
    # Common Hinglish patterns for technical roles
    "coding karna": "coding", "coding ki": "coding",
    "development kiya": "development", "testing karna": "testing",
    "design kiya": "design", "maintain karna": "maintenance",
    "manage karta": "management", "build kiya": "built",
    "deploy kiya": "deployment", "implement kiya": "implementation",
    # Role title mixtures
    "developer ka kaam": "developer", "engineer ka": "engineer",
    "team lead": "team lead", "project mein": "project", "company mein": "company",
    # Experience phrases
    "ka anubhav": "experience", "mein kaam": "worked in",
    "years ka": "years of", "saal ka": "years of",
}

# Devanagari → English technical term direct map
DEVANAGARI_TECH_MAP: dict[str, str] = {
    "कोडिंग": "coding", "प्रोग्रामिंग": "programming",
    "सॉफ्टवेयर": "software", "हार्डवेयर": "hardware",
    "डेटाबेस": "database", "डेटा": "data",
    "विश्लेषण": "analysis", "नेटवर्क": "network",
    "इंजीनियरिंग": "engineering", "वेबसाइट": "website",
    "एप्लिकेशन": "application", "मशीन लर्निंग": "machine learning",
    "आर्टिफिशियल": "artificial", "इंटेलिजेंस": "intelligence",
    "परियोजना": "project", "प्रबंधन": "management",
    "अनुभव": "experience", "कौशल": "skills",
    "नेतृत्व": "leadership", "टीम": "team",
    "ग्राहक": "customer", "सेवा": "service",
    "विकास": "development", "परीक्षण": "testing",
    "तैनाती": "deployment", "वास्तुकला": "architecture",
    "सुरक्षा": "security", "क्लाउड": "cloud",
    "स्वचालन": "automation",
}

# Common Tamil/Telugu/Kannada/Bengali tech terms (romanized)
SOUTH_INDIC_TECH_MAP: dict[str, str] = {
    # Tamil
    "thozhilnutpam": "technology", "nilai": "level", "payirchi": "training", "arivu": "knowledge",
    # Telugu
    "anubhavam": "experience", "naipunyam": "skills", "abhivruddhi": "development",
    # Kannada
    "anubhava": "experience", "tantra": "technology", "vikasa": "development",
    # Bengali
    "projukti": "technology", "anubhob": "experience", "dakkhota": "skills", "unnayan": "development",
}


def _has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text))


def _has_other_indic(text: str) -> bool:
    ranges = [
        r"[\u0B80-\u0BFF]", r"[\u0C00-\u0C7F]", r"[\u0C80-\u0CFF]",
        r"[\u0D00-\u0D7F]", r"[\u0980-\u09FF]", r"[\u0A80-\u0AFF]",
        r"[\u0A00-\u0A7F]",
    ]
    return any(re.search(r, text) for r in ranges)


def _apply_hinglish_lexicon(text: str) -> str:
    text_lower = text.lower()
    for pattern, replacement in HINGLISH_TECH_LEXICON.items():
        text_lower = text_lower.replace(pattern, replacement)
    return text_lower


def _apply_devanagari_map(text: str) -> str:
    for deva, english in DEVANAGARI_TECH_MAP.items():
        text = text.replace(deva, f" {english} ")
    return text


def _apply_south_indic_map(text: str) -> str:
    for term, english in SOUTH_INDIC_TECH_MAP.items():
        text = re.sub(re.escape(term), f" {english} ", text, flags=re.IGNORECASE)
    return text


def _extract_skills_from_text(text: str, known_skill_pool: Optional[set] = None) -> list[str]:
    """Simple skill extraction from normalized English text."""
    if known_skill_pool is None:
        return []
    text_lower = text.lower()
    return [skill for skill in known_skill_pool if skill.lower() in text_lower]


@dataclass
class CodeSwitchParseResult:
    original_text: str
    normalized_text: str
    has_devanagari: bool
    has_other_indic: bool
    has_hinglish: bool
    original_skills: list[str]
    augmented_skills: list[str]
    new_skills_found: list[str]
    translation_used: bool
    code_switch_detected: bool


class CodeSwitchResumeParser:
    """
    BIL-3: Detect and normalize code-switched text in resumes before skill
    extraction, so candidates who write in Hinglish or mix regional language
    with English are not penalized by the skill_overlap_ratio computation.
    """

    def __init__(self, use_indictrans2: bool = False) -> None:
        """
        Args:
            use_indictrans2: If True, load IndicTrans2 for full Devanagari translation
                             (~500MB). Defaults to False (static maps only).
        """
        self.use_indictrans2 = use_indictrans2
        self._translator = None

        if use_indictrans2:
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

                try:
                    from IndicTransToolkit.processor import IndicProcessor  # type: ignore
                except ImportError:
                    IndicProcessor = None  # type: ignore

                model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
                self._tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
                self._model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
                self._ip = IndicProcessor(inference=True) if IndicProcessor else None
                self._translator = "loaded"
                log.info("BIL-3: IndicTrans2 loaded for full script translation.")
            except ImportError:
                log.warning(
                    "BIL-3: IndicTransToolkit not installed. Falling back to static Devanagari map. "
                    "Run: pip install IndicTransToolkit transformers"
                )

    def _translate_devanagari_segment(self, text: str) -> str:
        """Translate a Devanagari segment to English using IndicTrans2."""
        if not self._translator:
            return _apply_devanagari_map(text)
        try:
            if self._ip is not None:
                batch = self._ip.preprocess_batch([text], src_lang="hin_Deva", tgt_lang="eng_Latn")
            else:
                batch = [text]
            import torch  # type: ignore

            inputs = self._tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=256
            )
            with torch.no_grad():
                outputs = self._model.generate(**inputs, max_length=256, num_beams=4)
            decoded = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)
            if self._ip is not None:
                return self._ip.postprocess_batch(decoded, lang="eng_Latn")[0]
            return decoded[0]
        except Exception as exc:  # noqa: BLE001
            log.warning("BIL-3: IndicTrans2 inference failed (%s). Using static map.", exc)
            return _apply_devanagari_map(text)

    def parse(
        self,
        text: str,
        existing_skills: Optional[list[str]] = None,
        skill_pool: Optional[set] = None,
    ) -> CodeSwitchParseResult:
        existing_skills = existing_skills or []
        skill_pool = skill_pool or set()
        has_deva = _has_devanagari(text)
        has_other = _has_other_indic(text)

        # Pass 1: Hinglish (Roman-script mixed)
        normalized = _apply_hinglish_lexicon(text)
        has_hinglish = normalized != text.lower()

        # Pass 2: Devanagari
        if has_deva:
            if self._translator:
                parts = re.split(r"([\u0900-\u097F]+(?:\s+[\u0900-\u097F]+)*)", normalized)
                translated_parts = []
                for part in parts:
                    if re.search(r"[\u0900-\u097F]", part):
                        translated_parts.append(self._translate_devanagari_segment(part))
                    else:
                        translated_parts.append(part)
                normalized = " ".join(translated_parts)
            else:
                normalized = _apply_devanagari_map(normalized)

        # Pass 3: Other Indic scripts (static map)
        if has_other:
            normalized = _apply_south_indic_map(normalized)

        # Skill augmentation: find skills in normalized text that weren't in original
        new_skills = _extract_skills_from_text(normalized, skill_pool)
        new_unique = [s for s in new_skills if s not in existing_skills]
        augmented = list(existing_skills) + new_unique

        return CodeSwitchParseResult(
            original_text=text,
            normalized_text=re.sub(r"\s+", " ", normalized).strip(),
            has_devanagari=has_deva,
            has_other_indic=has_other,
            has_hinglish=has_hinglish,
            original_skills=existing_skills,
            augmented_skills=augmented,
            new_skills_found=new_unique,
            translation_used=bool(self._translator and has_deva),
            code_switch_detected=(has_deva or has_other or has_hinglish),
        )

    def augment_candidate_skills(
        self,
        candidates: list[dict],
        skill_pool: Optional[set] = None,
    ) -> list[dict]:
        """Augment each candidate's skills list by parsing their profile_text."""
        for c in candidates:
            profile_text = c.get("profile_text", "")
            if not profile_text:
                c.setdefault("code_switch_detected", False)
                continue
            result = self.parse(
                text=profile_text,
                existing_skills=c.get("skills", []),
                skill_pool=skill_pool or set(c.get("skills", [])),
            )
            if result.new_skills_found:
                c["skills"] = result.augmented_skills
                c["code_switch_detected"] = True
                c["skills_added_by_bil3"] = result.new_skills_found
            else:
                c["code_switch_detected"] = result.code_switch_detected
        return candidates
