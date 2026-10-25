"""Pipeline P5: Munshi's ladder with fixed thresholds; no gap check, no re-reading, no questions (plan §15.5).

Implemented as Munshi with `Switches.munshi_no_gap_check` (variant P5): pages are still routed text layer, layout, OCR, vision, and the bundle is still
split and labelled, but the checklist is never compared with the filed items, `search_pages` is never used and counsel is never asked about a gap. A page
no route can read (or a broken file) is still queued as a question by the agent; under P5 that question gets no answer (the scripted counsel is silent), so
the run measures the cascade alone.
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import BundleResult
from vakeel_sahayak.eval.ingestion.munshi_family import run_munshi
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "P5"
SWITCHES = {"munshi_no_gap_check": True}


def availability() -> tuple[bool, str]:
    """(runnable, note): Munshi runs offline."""
    return True, ""


def run_bundle(pdf_path: str, ctx: AgentContext | None = None, counsel=None) -> BundleResult:
    """Run P5 on one bundle (counsel, if given, stays silent)."""
    return run_munshi(pdf_path, ctx, SWITCHES, counsel, silent_counsel=True)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P5.

    Args:
        pdf_path: the bundle
        ctx: the agent context (None: a scratch one on the real tools)

    Returns:
        IngestionReport.
    """
    return run_bundle(pdf_path, ctx).report
