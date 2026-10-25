"""Pipeline Munshi: the full agent, with a scripted counsel answering its questions (plan §15.5).

Survey, split and label, file, gap check (re-reading, searching, asking), conflict check and report, with the default switches. The scripted counsel
(`testsets.t2_messy_bundles.scripted_counsel`) knows the true values and gives a clean copy when asked for one; it answers at most the three questions
Munshi may ask per round.
"""

from __future__ import annotations

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.ingestion.common import BundleResult
from vakeel_sahayak.eval.ingestion.munshi_family import run_munshi
from vakeel_sahayak.schemas.ingestion_report import IngestionReport

PIPELINE = "Munshi"


def availability() -> tuple[bool, str]:
    """(runnable, note): Munshi runs offline."""
    return True, ""


def run_bundle(pdf_path: str, ctx: AgentContext | None = None, counsel=None) -> BundleResult:
    """Run the full Munshi on one bundle with the scripted counsel."""
    return run_munshi(pdf_path, ctx, {}, counsel)


def ingest_bundle(pdf_path: str, ctx: AgentContext | None = None) -> IngestionReport:
    """Ingest one T2 bundle under Munshi.

    Args:
        pdf_path: the bundle
        ctx: the agent context (None: a scratch one on the real tools)

    Returns:
        IngestionReport.
    """
    return run_bundle(pdf_path, ctx).report
