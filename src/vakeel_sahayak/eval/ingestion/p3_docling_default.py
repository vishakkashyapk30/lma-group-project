"""Pipeline P3: Docling's default pipeline (plan §15.5).

Every page goes through the layout parser (`routes.layout.parse_layout_page`: Docling when installed) and nothing else: no text-layer shortcut, no
OCR clean-up, no vision escalation, no questions. Without Docling the parser falls back to the text layer with a table heuristic and its log says
`layout: heuristic`; `availability()` reports that, and the runner then records the arm as unavailable instead of presenting the text layer as Docling.
"""

from __future__ import annotations

import importlib.util

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import BundleResult, page_count, page_route_of, single_document_report
from vakeel_sahayak.ingestion.routes import layout
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "P3"


def availability() -> tuple[bool, str]:
    """(runnable, note): the docling package must be importable."""
    if importlib.util.find_spec("docling") is None:
        return False, "docling is not installed (parse_layout_page would fall back to the text layer, which is P1)"
    return True, "docling"


def run_bundle(pdf_path: str, ctx: AgentContext | None = None) -> BundleResult:
    """Parse every page of a bundle under P3; returns the report and the page texts."""
    texts, routes = [], []
    for page in range(1, page_count(pdf_path) + 1):
        out = layout.parse_layout_page(pdf_path, page)
        texts.append(out.text)
        routes.append(page_route_of(page, out))
    return BundleResult(single_document_report(pdf_path, routes, texts), texts)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P3.

    Args:
        pdf_path: the bundle PDF
        ctx: unused (P3 has no agent)

    Returns:
        IngestionReport with one document covering every page.
    """
    return run_bundle(pdf_path, ctx).report
