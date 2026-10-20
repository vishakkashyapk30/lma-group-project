"""Baseline B4. Every store queried with the facts and each factor name, results fused by reciprocal-rank fusion, no orchestrator; drafting, checks and sparring as in Full. (plan §15.3)

Isolates: many stores vs an agent choosing. The retrieval logic is `agents/sutradhar/baselines.py::run_b4` (Sutradhar in mode 'B4': no
contract, no filters, no sufficiency check, no re-plan); the drafting, claim checks and Abhiyojak's sparring are the Full system's, so
the only difference from Full is Sutradhar's planning.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief

RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Fuse ranked lists of ids: an id's score is the sum of 1 / (k + rank) over the lists holding it (rank from 1).

    Args:
        rankings: ranked id lists, best first
        k: damping constant

    Returns:
        Ids by descending score; ties keep the order of first appearance.
    """
    score: dict[str, float] = {}
    order: list[str] = []
    for ranked in rankings:
        for rank, item in enumerate(ranked, start=1):
            if item not in score:
                order.append(item)
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(order, key=lambda i: (-score[i], order.index(i)))


def _b4_sutradhar(ctx: AgentContext) -> Any:
    """Sutradhar in mode 'B4' whose store queries carry the case's facts text (not the dossier summary) plus the factor name."""
    from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

    class B4Sutradhar(SutradharAgent):
        def pick_factors(self, state: Any) -> Any:
            """No orchestrator decides which factors apply: all 12 are queried (and drafted); the picker's stance is kept where it has one."""
            from vakeel_sahayak.schemas.enums import FactorStance

            shells = super().pick_factors(state)
            return [sh.model_copy(update={"stance": FactorStance.FAVOURABLE, "reason": "B4: no factor picker, every factor is queried"})
                    if sh.stance == FactorStance.NOT_APPLICABLE else sh for sh in shells]

        def exec_step(self, step: Any, factor: Any, **kw: Any) -> Any:
            """Add the plain factor name (value with spaces) to every text query, next to the facts."""
            name = str(getattr(factor, "value", factor)).replace("_", " ")
            args = dict(step.args)
            for key in ("query", "facts_text"):
                if isinstance(args.get(key), str) and name not in args[key].lower():
                    args[key] = f"{args[key]} {name}"[:1600]
            return super().exec_step(step.model_copy(update={"args": args}), factor, **kw)

        def plan_context(self, state: Any) -> Any:
            pctx = super().plan_context(state)
            facts = (state.facts_text or "").strip()
            if facts:
                pctx.facts_summary = lambda: facts[:1200]  # type: ignore[method-assign]
            return pctx

    return B4Sutradhar(ctx, mode="B4")


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B4.

    Args:
        case: `case_id`, `facts`, `before`; optional `scenario`
        ctx: context

    Returns:
        BailBrief.
    """
    from vakeel_sahayak.eval.baselines import full_system

    result = full_system.run_pipeline(case, ctx, sutradhar=_b4_sutradhar)
    ctx.eval_record = {k: v for k, v in result.items() if not k.startswith("_") and k != "brief"}  # type: ignore[attr-defined]
    return result["_brief_obj"]
