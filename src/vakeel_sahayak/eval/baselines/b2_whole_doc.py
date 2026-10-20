"""Baseline B2. Whole-document embeddings (BGE-M3, one vector per order truncated at 8K tokens); the top-3 orders are passed to one drafting call. (plan §15.3)

Isolates: retrieval granularity. One `similar_orders` call (k=3, `before` = the case's order date), no paragraph search, one drafting call, no checks.
# SKELETON-GAP: `similar_orders` returns order metadata, not order text, so the orders go into the prompt as the rows the store gives.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.baselines.common import call_tool, draft, evidence_rows, facts_of
from vakeel_sahayak.schemas.bail_brief import BailBrief

TASK = "baseline.b2_whole_doc"
K = 3


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B2.

    Args:
        case: `case_id`, `facts`, `before`
        ctx: context

    Returns:
        BailBrief.
    """
    rows = call_tool(ctx, "similar_orders", facts_text=facts_of(case), before=case.get("before"), k=K)
    return draft(case, ctx, task=TASK, evidence=evidence_rows(rows, K))
