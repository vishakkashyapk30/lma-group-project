"""Tools in intake.pages (plan §4.2, §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import LayoutResult, TextLayerResult


def inspect_page(file_path: str, page: int) -> PageSignals:
    """Compute cheap quality signals for a page (plan §4.2). (plan §4.3)

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        PageSignals.
    """
    raise NotImplementedError


def read_text_layer(file_path: str, page: int) -> TextLayerResult:
    """Read the PyMuPDF text layer. (plan §4.2)

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        TextLayerResult.
    """
    raise NotImplementedError


def parse_layout(file_path: str, page: int) -> LayoutResult:
    """Docling layout parse for columns and tables. (plan §4.2)

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        LayoutResult.
    """
    raise NotImplementedError


def clean_image(image: bytes, ops: list[str] | None = None) -> bytes:
    """Clean up a page image (deskew, dewarp, denoise). (plan §4.3)

    Args:
        image: see behaviour
        ops: subset of deskew, dewarp, denoise

    Returns:
        Cleaned image.
    """
    raise NotImplementedError


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
