"""Bundle splitting: document type changes, new headers, page numbers restarting (plan §4.1 K8, §4.3)."""

from __future__ import annotations

from vakeel_sahayak.ingestion.signals import PageSignals


def split_into_documents(page_texts: list[str], page_signals: list[PageSignals]) -> list[tuple[int, int]]:
    """Return inclusive (first, last) page ranges, one per document.

    Args:
        page_texts: see behaviour
        page_signals: see behaviour

    Returns:
        Ranges.
    """
    raise NotImplementedError
