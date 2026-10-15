"""Tools in intake.ocr (plan §4.1 K5, §4.2). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.ingestion.hindi import detect_script as detect_script_label
from vakeel_sahayak.ingestion.hindi import script_confidence
from vakeel_sahayak.ingestion.routes.ocr import OCR_LANGS, ocr_page_lang
from vakeel_sahayak.ingestion.routes.vision import vision_route
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.intake._common import check_page, guarded
from vakeel_sahayak.tools.store_call import invalid
from vakeel_sahayak.tools.types import OcrResult, ScriptInfo


def ocr_page(file_path: str, page: int, lang: str = "eng") -> OcrResult | ToolError:
    """OCR a page with Surya (Tesseract fallback). (plan §4.2)

    Args:
        file_path: see behaviour
        page: page number from 1
        lang: 'eng', 'hin' or 'hin+eng'

    Returns:
        OcrResult.
    """
    if lang not in OCR_LANGS:
        return invalid("ocr_page", f"lang must be one of {list(OCR_LANGS)}, got {lang!r}")
    if err := check_page("ocr_page", file_path, page):
        return err

    def run() -> OcrResult:
        out = ocr_page_lang(file_path, page, lang=lang)
        return OcrResult(text=out.text, mean_conf=out.ocr_conf or 0.0, boxes=out.boxes, lang=lang)

    return guarded("ocr_page", run)


def vision_read_page(file_path: str, page: int) -> str | ToolError:
    """Vision-model transcription of a hard page; transcribe only, never summarise. (plan §4.2)

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        Transcript.
    """
    if err := check_page("vision_read_page", file_path, page):
        return err
    return guarded("vision_read_page", lambda: vision_route(file_path, page).text)


def detect_script(text: str | None = None, image: bytes | None = None) -> ScriptInfo | ToolError:
    """Detect script on a text layer or a first OCR pass. (plan §4.1 K5)

    Args:
        text: text to look at (wins when both are given)
        image: a page image, read with a first OCR pass when there is no text

    Returns:
        ScriptInfo.
    """
    if text is None and image is None:
        return invalid("detect_script", "give text or image")

    def run() -> ScriptInfo:
        sample = text
        if sample is None:
            from vakeel_sahayak.models.factory import get_ocr

            sample, _conf, _boxes = get_ocr().ocr(image, "hin+eng")  # type: ignore[arg-type]
        return ScriptInfo(script=detect_script_label(sample), confidence=round(script_confidence(sample), 3))

    return guarded("detect_script", run)


OCR_PAGE_SPEC = ToolSpec(
    name="ocr_page",
    description="OCR a page with Surya (Tesseract fallback).",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.2",
)

VISION_READ_PAGE_SPEC = ToolSpec(
    name="vision_read_page",
    description="Vision-model transcription of a hard page; transcribe only, never summarise.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.2",
)

DETECT_SCRIPT_SPEC = ToolSpec(
    name="detect_script",
    description="Detect script on a text layer or a first OCR pass.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.1 K5",
)
