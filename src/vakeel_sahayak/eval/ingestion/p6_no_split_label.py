"""Pipeline P6: Munshi without bundle splitting and document labelling (plan §15.5).

Implemented as Munshi with `Switches.munshi_no_bundle_split` (variant P6): the whole file is one document labelled OTHER, so `split_bundle` and
`classify_document` are never called. Everything else is unchanged: the ladder, filing, the gap check (searching and asking counsel) and the report.
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import BundleResult
from vakeel_sahayak.eval.ingestion.munshi_family import run_munshi
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "P6"
SWITCHES = {"munshi_no_bundle_split": True}


def availability() -> tuple[bool, str]:
    """(runnable, note): Munshi runs offline."""
    return True, ""


def run_bundle(pdf_path: str, ctx: AgentContext | None = None, counsel=None) -> BundleResult:
    """Run P6 on one bundle with the scripted counsel."""
    return run_munshi(pdf_path, ctx, SWITCHES, counsel)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under P6.

    Args:
        pdf_path: the bundle
        ctx: the agent context (None: a scratch one on the real tools)

    Returns:
        IngestionReport.
    """
    return run_bundle(pdf_path, ctx).report
