"""Assemble the IngestionReport (plan §4.6)."""

from __future__ import annotations

from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, FiledCounts, Gap, IngestionReport


def build_report(
    case_id: str, file: str, documents: list[DocumentEntry], filed: FiledCounts, gaps: list[Gap], questions: list[str]
) -> IngestionReport:
    """Assemble Munshi's output.

    Args:
        case_id: see behaviour
        file: see behaviour
        documents: see behaviour
        filed: see behaviour
        gaps: see behaviour
        questions: see behaviour

    Returns:
        IngestionReport.
    """
    raise NotImplementedError
