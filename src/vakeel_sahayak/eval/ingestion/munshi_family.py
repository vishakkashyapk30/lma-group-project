"""Runs Munshi under a set of switches for the RQ2 comparison (P5, P6 and the full agent share this code).

With an `AgentContext` (tests, the driver) the agent works through that context's tools. Without one, a scratch context is built on a temporary cases folder
and the real tool registry. The scripted counsel (`testsets.t2_messy_bundles.scripted_counsel(truth)`) is installed as the ask handler for the run only.
"""

from __future__ import annotations

import copy
import tempfile
from collections.abc import Callable
from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.eval.ingestion.common import BundleResult, case_id_for
from vakeel_sahayak.ingestion import questions as questions_mod

Counsel = Callable[[str], str]


def run_munshi(pdf_path: str, ctx: AgentContext | None, switches_update: dict[str, Any] | None = None, counsel: Counsel | None = None,
               silent_counsel: bool = False) -> BundleResult:
    """Run Munshi on one bundle.

    Args:
        pdf_path: the bundle
        ctx: the context to use (None: a scratch one)
        switches_update: fields of `Switches` to set for this run (P5: `munshi_no_gap_check`, P6: `munshi_no_bundle_split`)
        counsel: scripted counsel for the questions Munshi asks (None: the questions stay open)
        silent_counsel: counsel never answers (P5 'no questions': nothing comes back)

    Returns:
        BundleResult with the report, the raw page texts read this run and the (question, answer) pairs.
    """
    scratch = None
    if ctx is None:
        from vakeel_sahayak.eval.runners import driver

        scratch = tempfile.TemporaryDirectory(prefix="vs-rq2-")
        ctx = driver.build_context({"case_id": case_id_for(pdf_path)}, cases_dir=scratch.name)
    run_ctx = copy.copy(ctx)
    run_ctx.switches = ctx.switches.model_copy(update=dict(switches_update or {}))
    agent = MunshiAgent(run_ctx)
    previous = questions_mod._handler  # noqa: SLF001 - restored below; the module offers a setter but no getter
    try:
        if counsel is not None and not silent_counsel:
            questions_mod.set_ask_handler(lambda qs, _case_id: [counsel(q) for q in qs])
        elif silent_counsel:
            questions_mod.set_ask_handler(lambda qs, _case_id: [])
        report = agent.ingest([pdf_path])
        texts = [p.raw for r in agent._run.reads for p in r.pages]  # noqa: SLF001 - the raw page text lives only in this run
        pairs = list(zip(report.questions, agent.answers, strict=False))
    finally:
        questions_mod.set_ask_handler(previous)
        if scratch is not None:
            scratch.cleanup()
    return BundleResult(report, texts, pairs)
