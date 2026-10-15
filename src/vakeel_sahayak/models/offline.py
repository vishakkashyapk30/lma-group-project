"""Deterministic offline clients: the pipeline runs end to end with no heavy dependency (plan §12, §4.2).

They understand only the stand-in page images of `ingestion.source.PlainTextSource`. Given a real photo or scan they
raise `ModelUnavailable`, never invented text. The glossary translator is word-level, marked as such, and meant for
offline runs and tests, not for real Hindi orders.
"""

from __future__ import annotations

import re
from pathlib import Path

from vakeel_sahayak.models.base import AsrClient, ModelUnavailable, OcrClient, TranslationClient, VisionClient

_NEEDS_OCR = "no OCR engine is installed (Surya or Tesseract), so real page images cannot be read"
_NEEDS_VLM = "no vision model is installed, so real page images cannot be transcribed"


def _fixture(image: bytes, what: str) -> dict:
    from vakeel_sahayak.ingestion.source import decode_fixture_image, is_fixture_image

    if not is_fixture_image(image):
        raise ModelUnavailable(what, "ocr")
    return decode_fixture_image(image)


class OfflineOcrClient(OcrClient):
    """Reads the pixel text of stand-in images; the confidence is the one the image carries."""

    name = "offline"

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """Return the stand-in image's text and confidence (handwriting lowers it to 0.35)."""
        data = _fixture(image, _NEEDS_OCR)
        conf = min(float(data.get("conf", 0.9)), 0.35) if data.get("hw") else float(data.get("conf", 0.9))
        text = data.get("text", "")
        boxes = [[72.0, 72.0 + 16.0 * i, 523.0, 86.0 + 16.0 * i] for i, _ in enumerate(text.splitlines() or [""])]
        return text, conf, boxes


class OfflineVisionClient(VisionClient):
    """Returns the pixel text of stand-in images, or '' when the image says the vision model cannot read it."""

    name = "offline"

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """Transcribe a stand-in image."""
        data = _fixture(image, _NEEDS_VLM)
        return data.get("text", "") if data.get("vision_ok", True) else ""


class OfflineAsrClient(AsrClient):
    """Reads a transcript sidecar: `note.wav` is transcribed from `note.wav.txt` (or `note.txt`) next to it."""

    name = "offline"

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        """Return the sidecar transcript; without one there is nothing to transcribe."""
        p = Path(audio_path)
        for sidecar in (p.with_name(p.name + ".txt"), p.with_suffix(".txt")):
            if sidecar.is_file():
                return sidecar.read_text(encoding="utf-8").strip()
        raise ModelUnavailable("no speech-recognition model is installed (Whisper or IndicConformer)", "speech")


class IdentityTranslator(TranslationClient):
    """Passthrough translator: returns the text unchanged. `is_identity` tells callers no translation happened."""

    name = "identity"
    is_identity = True

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """Return the text as it is."""
        return text


_GLOSSARY = {
    "प्राथमिकी": "FIR", "प्रथम सूचना रिपोर्ट": "First Information Report", "रिपोर्ट": "report", "गिरफ्तार": "arrested",
    "गिरफ्तारी": "arrest", "गिरफ़्तार": "arrested", "जमानत": "bail", "आवेदन": "application", "आदेश": "order",
    "धारा": "Section", "थाना": "police station", "थाने": "police station", "दिनांक": "dated", "को": "on",
    "आरोपी": "accused", "अभियुक्त": "accused", "शिकायतकर्ता": "complainant", "गवाह": "witness",
    "न्यायालय": "court", "रिमांड": "remand", "न्यायिक": "judicial", "अभिरक्षा": "custody", "हिरासत": "custody",
    "पुलिस": "police", "मामला": "case", "अपराध": "offence", "जांच": "investigation", "आरोपपत्र": "charge sheet",
    "भारतीय": "Indian", "न्याय": "justice", "संहिता": "Code", "सूचना": "information", "दर्ज": "registered",
    "की": "of", "का": "of", "के": "of", "में": "in", "से": "from", "पर": "on", "और": "and", "है": "is", "था": "was",
    "थी": "was", "ने": "", "द्वारा": "by", "हुआ": "occurred", "किया": "did", "गया": "was", "गई": "was", "बजे": "o'clock",
    "बीएनएस": "BNS", "आईपीसी": "IPC", "बीएनएसएस": "BNSS", "सीआरपीसी": "CrPC", "सत्र": "Sessions",
    "खारिज": "rejected", "स्वीकार": "allowed", "मंजूर": "granted", "पुत्र": "son of", "निवासी": "resident of",
    "द्वारा।": "by", "वादी": "complainant", "प्रार्थी": "applicant", "उपस्थित": "present", "पेश": "produced",
    "लिया": "taken", "ली": "taken", "दिया": "gave", "रात": "night", "सुबह": "morning", "शाम": "evening",
}  # fmt: skip
_HI_WORD = re.compile(r"[ऀ-ॣ०-ॿ]+")


class GlossaryTranslator(TranslationClient):
    """Word-level Hindi to English glossary for offline runs. Unknown words stay in Devanagari. Not IndicTrans2."""

    name = "offline-glossary"
    is_identity = False

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """Replace known Hindi words with English; everything else is kept."""
        if (src, tgt) != ("hi", "en"):
            raise ValueError("the offline glossary translates hi to en only")
        out = _HI_WORD.sub(lambda m: _GLOSSARY.get(m.group(0), m.group(0)), text)
        return re.sub(r"[ \t]{2,}", " ", out)
