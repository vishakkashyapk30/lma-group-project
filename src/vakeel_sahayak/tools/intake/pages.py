"""Tools in intake.pages (plan §4.2, §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.ingestion.imaging import clean_image_bytes
from vakeel_sahayak.ingestion.routes.layout import parse_layout_page
from vakeel_sahayak.ingestion.routes.text_layer import read_text_layer_page
from vakeel_sahayak.ingestion.signals import PageSignals, compute_signals
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.intake._common import check_page, guarded
from vakeel_sahayak.tools.store_call import invalid
from vakeel_sahayak.tools.types import LayoutResult, TextLayerResult


def inspect_page(file_path: str, page: int) -> PageSignals | ToolError:
    """Compute cheap quality signals for a page (plan §4.2). (plan §4.3)

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        PageSignals.
    """
    if err := check_page("inspect_page", file_path, page):
        return err
    return guarded("inspect_page", lambda: compute_signals(file_path, page))


def read_text_layer(file_path: str, page: int) -> TextLayerResult | ToolError:
    """Read the PyMuPDF text layer. (plan §4.2)

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        TextLayerResult (empty text when the page has no text layer).
    """
    if err := check_page("read_text_layer", file_path, page):
        return err

    def run() -> TextLayerResult:
        out = read_text_layer_page(file_path, page)
        return TextLayerResult(text=out.text, boxes=out.boxes)

    return guarded("read_text_layer", run)


def parse_layout(file_path: str, page: int) -> LayoutResult | ToolError:
    """Docling layout parse for columns and tables. (plan §4.2)

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        LayoutResult.
    """
    if err := check_page("parse_layout", file_path, page):
        return err

    def run() -> LayoutResult:
        out = parse_layout_page(file_path, page)
        return LayoutResult(text=out.text, tables=out.tables)

    return guarded("parse_layout", run)


def clean_image(image: bytes, ops: list[str] | None = None) -> bytes | ToolError:
    """Clean up a page image (deskew, dewarp, denoise). (plan §4.3)

    Args:
        image: see behaviour
        ops: subset of deskew, dewarp, denoise

    Returns:
        Cleaned image.
    """
    if not isinstance(image, (bytes, bytearray)) or not image:
        return invalid("clean_image", "image must be non-empty bytes")
    return guarded("clean_image", lambda: clean_image_bytes(bytes(image), ops))


INSPECT_PAGE_SPEC = ToolSpec(
    name="inspect_page",
    description="Compute cheap quality signals for a page (plan §4.2).",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.3",
)

READ_TEXT_LAYER_SPEC = ToolSpec(
    name="read_text_layer",
    description="Read the PyMuPDF text layer.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.2",
)

PARSE_LAYOUT_SPEC = ToolSpec(
    name="parse_layout",
    description="Docling layout parse for columns and tables.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.2",
)

CLEAN_IMAGE_SPEC = ToolSpec(
    name="clean_image",
    description="Clean up a page image (deskew, dewarp, denoise).",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.3",
)
