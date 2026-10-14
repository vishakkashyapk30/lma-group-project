"""Pipeline P6: Munshi without bundle splitting and document labelling (plan §15.5)."""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.ingestion_report import IngestionReport


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P6.

    Args:
        pdf_path: see behaviour
        ctx: see behaviour

    Returns:
        IngestionReport.
    """
    raise NotImplementedError
