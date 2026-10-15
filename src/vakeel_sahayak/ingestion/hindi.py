"""Hindi handling: script detection, Hindi OCR choice, IndicTrans2; both texts kept (plan §4.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from vakeel_sahayak.models.base import TranslationClient

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_HI_MONTHS = {
    "जनवरी": "January", "फरवरी": "February", "मार्च": "March", "अप्रैल": "April", "मई": "May", "जून": "June",
    "जुलाई": "July", "अगस्त": "August", "सितंबर": "September", "सितम्बर": "September", "अक्टूबर": "October",
    "अक्तूबर": "October", "नवंबर": "November", "नवम्बर": "November", "दिसंबर": "December", "दिसम्बर": "December",
}  # fmt: skip


def script_shares(text: str) -> tuple[float, float]:
    """(Devanagari share, Latin share) of the letters in a text; both 0 for a text without letters."""
    dev, lat = len(_DEVANAGARI.findall(text)), len(_LATIN.findall(text))
    total = dev + lat
    return (dev / total, lat / total) if total else (0.0, 0.0)


def detect_script(text: str) -> str:
    """Return 'devanagari', 'latin' or 'mixed'.

    At least 80% Devanagari letters is 'devanagari', under 2% is 'latin' (a text without letters is 'latin'), and
    anything between is 'mixed' (for example an English order quoting Hindi statements, plan §4.1 K5).

    Args:
        text: see behaviour

    Returns:
        Script label.
    """
    dev, _ = script_shares(text)
    if dev >= 0.8:
        return "devanagari"
    return "latin" if dev < 0.02 else "mixed"


def script_confidence(text: str) -> float:
    """How clearly the text is in the script `detect_script` named (the dominant script's share; 1.0 for no letters)."""
    dev, lat = script_shares(text)
    if dev == lat == 0.0:
        return 1.0
    return max(dev, lat)


def lang_of(text: str) -> str:
    """Document language label: 'hi' (Devanagari), 'en' (Latin) or 'mixed' (the DocLang values)."""
    return {"devanagari": "hi", "latin": "en", "mixed": "mixed"}[detect_script(text)]


def ocr_lang_for(script: str | None) -> str:
    """OCR language for a detected script: 'hin' for Devanagari, 'eng' for Latin, 'hin+eng' for mixed or unknown."""
    return {"devanagari": "hin", "latin": "eng"}.get(script or "", "hin+eng")


def to_ascii_digits(text: str) -> str:
    """Devanagari digits to ASCII, so dates and section numbers parse ('२०.०८.२०२४' becomes '20.08.2024')."""
    return text.translate(_DIGITS)


def normalise_for_extraction(text: str) -> str:
    """ASCII digits, English month names and full stops for the danda, so date and section regexes see Hindi text."""
    text = to_ascii_digits(text).replace("।", ". ")
    for hi, en in _HI_MONTHS.items():
        text = text.replace(hi, en)
    return text


@dataclass(frozen=True)
class Translation:
    """A translation with the engine that made it, so a word-level or identity fallback is never mistaken for IndicTrans2."""

    original: str
    english: str
    engine: str
    is_identity: bool


def translate_keeping_original(text_hi: str, translator: TranslationClient | None = None) -> Translation:
    """Translate the Devanagari lines of a text to English and keep the original (plan §4.5).

    Lines without Devanagari are copied as they are, so a mixed page keeps its English.

    Args:
        text_hi: Hindi or mixed text
        translator: defaults to the configured client (`models.factory.get_translator`)

    Returns:
        Translation holding both texts and the engine name.
    """
    if translator is None:
        from vakeel_sahayak.models.factory import get_translator

        translator = get_translator()
    lines = text_hi.split("\n")
    todo = [i for i, ln in enumerate(lines) if _DEVANAGARI.search(ln)]
    out = list(lines)
    if todo:
        joined = translator.translate("\n".join(lines[i] for i in todo), "hi", "en").split("\n")
        if len(joined) == len(todo):
            for i, line in zip(todo, joined, strict=True):
                out[i] = line
        else:  # an engine that merged or split lines: translate line by line instead
            for i in todo:
                out[i] = translator.translate(lines[i], "hi", "en")
    return Translation(
        original=text_hi,
        english="\n".join(out),
        engine=getattr(translator, "name", type(translator).__name__),
        is_identity=bool(getattr(translator, "is_identity", False)),
    )


def to_english_with_original(text_hi: str) -> tuple[str, str]:
    """Translate and keep the Hindi original; span_check runs on the translation, counsel sees the original.

    Args:
        text_hi: see behaviour

    Returns:
        (original, translation).
    """
    t = translate_keeping_original(text_hi)
    return t.original, t.english
