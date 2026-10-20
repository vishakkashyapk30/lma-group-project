"""The Full system through the thin evaluation driver (plan §11 'Reuse', §15.3, docs/evaluation-plan.md §7.3).

Munshi (when a bundle is given), Peshkar, Sutradhar, Vakeel, Abhiyojak and all checks run in sequence under a scripted counsel; the
driver does not use LangGraph. `run_case` returns the `BailBrief` (what the baselines return); `run_pipeline` returns the whole
result record (brief, sparring record, gates, export attempt, errors) that `make smoke` prints.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief


def run_pipeline(case: dict[str, Any], ctx: AgentContext, counsel: Any = None, *, sutradhar: Any = None) -> dict[str, Any]:
    """Run the agents in sequence for one case; the result record of `driver.run_agents` (key `_brief_obj` holds the BailBrief)."""
    from vakeel_sahayak.eval.runners.driver import run_agents

    return run_agents(case, ctx, counsel, sutradhar=sutradhar)


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak and all checks.

    Args:
        case: `case_id`, `facts` (or `facts_text`), `before`; optional `bundle` and `scenario`
        ctx: the case's context (switches, budget, log, tools, models)

    Returns:
        BailBrief (an empty labelled brief when a stage failed; the stage errors are in the event log).
    """
    result = run_pipeline(case, ctx)
    ctx.eval_record = {k: v for k, v in result.items() if not k.startswith("_") and k != "brief"}  # type: ignore[attr-defined]  # the driver saves it
    return result["_brief_obj"]
