"""PyMuPDF text layer (plan §4.2 step 1). Plan §4.2."""

from __future__ import annotations

from vakeel_sahayak.ingestion.ladder import RouteOutcome


def read_text_layer_page(file_path: str, page: int) -> RouteOutcome:
    """PyMuPDF text layer (plan §4.2 step 1).

    Args:
        file_path: see behaviour
        page: see behaviour

    Returns:
        RouteOutcome.
    """
    raise NotImplementedError
