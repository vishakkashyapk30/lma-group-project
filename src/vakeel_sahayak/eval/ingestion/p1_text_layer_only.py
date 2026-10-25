"""Pipeline P1: text layer only, read with PyMuPDF (plan §15.5).

Every page is read from its text layer and nothing else: no OCR, no layout parser, no vision model, no questions. A page without a text layer
(a scan, a photo) comes back empty and UNREADABLE; a legacy-font layer (K6) comes back as the garbled characters it holds. The bundle is one
undifferentiated document (no splitting, no labelling).
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import BundleResult, page_count, page_route_of, single_document_report
from vakeel_sahayak.ingestion.routes.text_layer import read_text_layer_page
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "P1"


def availability() -> tuple[bool, str]:
    """(runnable, note): PyMuPDF must be importable."""
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        return False, "PyMuPDF is not installed"
    return True, ""


def run_bundle(pdf_path: str, ctx: AgentContext | None = None) -> BundleResult:
    """Read every page of a bundle under P1; returns the report and the page texts."""
    texts, routes = [], []
    for page in range(1, page_count(pdf_path) + 1):
        out = read_text_layer_page(pdf_path, page)
        texts.append(out.text)
        routes.append(page_route_of(page, out))
    return BundleResult(single_document_report(pdf_path, routes, texts), texts)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P1.

    Args:
        pdf_path: the bundle PDF
        ctx: unused (P1 has no agent)

    Returns:
        IngestionReport with one document covering every page.
    """
    return run_bundle(pdf_path, ctx).report
