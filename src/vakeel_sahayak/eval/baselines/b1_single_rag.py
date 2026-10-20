"""Baseline B1. Single RAG: one store holding precedents and submissions, top-10 retrieved with the facts as the query, one drafting call. (plan §15.3)

Isolates: one store vs many. One retrieval call (`search_reasoning`, no factor filter, no section family, `before` = the case's order date),
one drafting call, no planner, no checks, no sparring. # SKELETON-GAP: no merged index exists; the reasoning store stands in for it.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.baselines.common import call_tool, draft, evidence_rows, facts_of
from vakeel_sahayak.schemas.bail_brief import BailBrief

TASK = "baseline.b1_single_rag"
K = 10


def retrieve(case: dict[str, Any], ctx: AgentContext) -> list[Any]:
    """The one top-10 retrieval with the facts as the query."""
    return call_tool(ctx, "search_reasoning", query=facts_of(case), before=case.get("before"), k=K)


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B1.

    Args:
        case: `case_id`, `facts`, `before`
        ctx: context (tools, budget, model)

    Returns:
        BailBrief.
    """
    return draft(case, ctx, task=TASK, evidence=evidence_rows(retrieve(case, ctx), K))
