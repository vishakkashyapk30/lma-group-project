"""Tools in intake.ocr (plan §4.1 K5, §4.2). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import OcrResult, ScriptInfo


def ocr_page(file_path: str, page: int, lang: str = "eng") -> OcrResult:
    """OCR a page with Surya (Tesseract fallback). (plan §4.2)

    Args:
        file_path: see behaviour
        page: see behaviour
        lang: 'eng' or 'hin'

    Returns:
        OcrResult.
    """
    raise NotImplementedError


def vision_read_page(file_path: str, page: int) -> str:
    """Vision-model transcription of a hard page; transcribe only, never summarise. (plan §4.2)

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        Transcript.
    """
    raise NotImplementedError


def detect_script(text: str | None = None, image: bytes | None = None) -> ScriptInfo:
    """Detect script on a text layer or a first OCR pass. (plan §4.1 K5)

    Args:
        text: see behaviour
        image: see behaviour

    Returns:
        ScriptInfo.
    """
    raise NotImplementedError


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
