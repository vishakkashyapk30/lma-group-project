"""OCR, vision, script, translation and speech tools (plan §4.2, §4.5), with fake model clients patched in."""

from __future__ import annotations

import pytest

from tests.fakes.models import FakeAsr, FakeTranslator
from tests.unit.tools_intake._helpers import AnyImageOcr, AnyImageVision, assert_rejects, patch_everywhere
from vakeel_sahayak.tools.intake.language import transcribe, translate
from vakeel_sahayak.tools.intake.ocr import detect_script, ocr_page, vision_read_page
from vakeel_sahayak.tools.types import OcrResult, ScriptInfo, TranscriptResult

HINDI_FIR = "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024"


@pytest.fixture()
def scanned(pdfs):
    return str(pdfs.scanned("scan.pdf", 2))


# ---- ocr_page ----------------------------------------------------------------------------------------------------
def test_ocr_page_rejects_unknown_language(scanned):
    """lang must be 'eng' or 'hin'; anything else is rejected before any OCR runs."""
    assert_rejects(ocr_page, scanned, 1, "xx")


@pytest.mark.parametrize("page", [0, -3])
def test_ocr_page_rejects_page_below_one(scanned, page):
    """Pages are 1-based."""
    assert_rejects(ocr_page, scanned, page)


def test_ocr_page_missing_file(tmp_path):
    """A missing file is rejected."""
    assert_rejects(ocr_page, str(tmp_path / "missing.pdf"), 1)


@pytest.mark.parametrize("lang", ["eng", "hin"])
def test_ocr_page_returns_text_confidence_and_lang(monkeypatch, scanned, require_pymupdf, lang):
    """ocr_page renders the page, runs the OCR client from the factory and reports text, mean confidence and language."""
    ocr = AnyImageOcr("FIR No. 112/2024", 0.88)
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_ocr", lambda *a, **k: ocr)
    result = ocr_page(scanned, 1, lang)
    assert isinstance(result, OcrResult)
    assert result.text == "FIR No. 112/2024"
    assert result.mean_conf == pytest.approx(0.88)
    assert result.lang == lang
    assert len(ocr.calls) == 1, "the page is OCRed once"


# ---- vision_read_page --------------------------------------------------------------------------------------------
def test_vision_read_page_rejects_bad_page(scanned):
    """Page 0 is rejected."""
    assert_rejects(vision_read_page, scanned, 0)


def test_vision_read_page_returns_the_transcript(monkeypatch, scanned, require_pymupdf):
    """The vision tool returns the transcript from the vision client, and only transcribes."""
    vision = AnyImageVision("FIR page three, transcribed.")
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_vision", lambda *a, **k: vision)
    assert vision_read_page(scanned, 2) == "FIR page three, transcribed."
    assert len(vision.calls) == 1


# ---- detect_script -----------------------------------------------------------------------------------------------
def test_detect_script_needs_text_or_image():
    """With neither text nor image there is nothing to detect: rejected."""
    assert_rejects(detect_script)


@pytest.mark.parametrize(
    ("text", "script"),
    [(HINDI_FIR, "devanagari"), ("FIR No. 112/2024 dated 14.08.2024", "latin")],
)
def test_detect_script_on_text(text, script):
    """Script is detected from a text layer; confidence is a probability."""
    info = detect_script(text=text)
    assert isinstance(info, ScriptInfo)
    assert info.script == script
    assert 0.0 <= info.confidence <= 1.0


# ---- translate ---------------------------------------------------------------------------------------------------
def test_translate_uses_the_translation_client(monkeypatch):
    """translate goes through models.factory.get_translator (IndicTrans2 in production)."""
    fake = FakeTranslator()
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_translator", lambda *a, **k: fake)
    assert translate(HINDI_FIR) == "FIR No. 112/2024 dated 14.08.2024"
    assert fake.calls == [HINDI_FIR]


def test_translate_rejects_unknown_language_codes():
    """src and tgt must be language codes the translator handles ('hi', 'en')."""
    # ASSUMPTION: the supported codes are 'hi' and 'en' only.
    assert_rejects(translate, "text", "zz", "en")
    assert_rejects(translate, "text", "hi", "zz")


# ---- transcribe --------------------------------------------------------------------------------------------------
def test_transcribe_returns_transcript_and_language_hint(monkeypatch, tmp_path):
    """transcribe wraps the ASR client and returns a TranscriptResult carrying the text and the hinted language."""
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(b"RIFF....fake")
    asr = FakeAsr({str(audio): "arrested on 20 August 2024"})
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_asr", lambda *a, **k: asr)
    result = transcribe(str(audio), "en")
    assert isinstance(result, TranscriptResult)
    assert result.text == "arrested on 20 August 2024"
    assert result.lang == "en"


def test_transcribe_missing_audio_is_rejected(tmp_path):
    """A missing audio file is rejected."""
    assert_rejects(transcribe, str(tmp_path / "gone.wav"))


def test_transcribe_rejects_unknown_language_hint(tmp_path):
    """ASSUMPTION: lang_hint is None, 'hi' or 'en'; other values are rejected."""
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF....fake")
    assert_rejects(transcribe, str(audio), "klingon")
