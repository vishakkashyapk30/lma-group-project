"""Clean-up (deskew, dewarp, denoise) then Surya OCR; Tesseract fallback (step 3). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.ladder import RouteOutcome


def ocr_page_route(file_path: str, page: int) -> RouteOutcome:
    """Clean-up (deskew, dewarp, denoise) then Surya OCR; Tesseract fallback (step 3).

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        RouteOutcome.
    """
    raise NotImplementedError
