"""PyMuPDF text layer (plan §4.2 step 1)."""

from __future__ import annotations

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.ladder import RouteOutcome
from vakeel_sahayak.ingestion.source import open_source
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute


def read_text_layer_page(file_path: str, page: int) -> RouteOutcome:
    """PyMuPDF text layer (plan §4.2 step 1). The quality check is the ladder's job, not this function's.

    Args:
        file_path: see behaviour
        page: page number from 1

    Returns:
        RouteOutcome with the text, one box per text block and confidence 1.0 (born-digital text is exact). A page
        without a text layer gives empty text and status UNREADABLE.
    """
    src = open_source(file_path)
    text = src.text_layer(page) or ""
    return RouteOutcome(
        route=ParseRoute.TEXT_LAYER,
        text=text,
        boxes=src.text_boxes(page),
        lang=lang_of(text) if text.strip() else None,
        confidence=1.0 if text.strip() else None,
        status=PageStatus.OK if text.strip() else PageStatus.UNREADABLE,
        log=["text_layer" if text.strip() else "text_layer: none"],
    )
