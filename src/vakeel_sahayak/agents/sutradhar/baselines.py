"""The two variants that replace Sutradhar's contracts and loop: B4 (every store, fused) and A7 (free planner) (plan §6.5, §15.3, §15.4).

Comparing them with the full system and with A6 (the fixed router, `fixed_router.py`) shows whether the gains come from
the stores, from the contracts, or from the agent's planning and stopping:

- **B4** queries every store with the facts and the factor name and fuses the ranked lists by reciprocal-rank fusion. No
  contract, no filters, no sufficiency check, no re-plan; drafting, checks and sparring are the same as the full system.
  The citation store takes document ids rather than a query, and the concordance is keyed by section, so neither is
  queried by text; the other eight stores (reasoning, similar, objections, arguments, statutes, case documents, timeline,
  facts) are. The factor picker still marks which factors apply, so Vakeel gets packs for the same checklist.
- **A7** lets the model plan freely: it sees the applicable factors and the tool names and writes the calls, with no
  evidence contract (no slots, no required evidence, no stopping rule, no open issues). The calls run as written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vakeel_sahayak.agents.sutradhar.offline import free_plan_offline
from vakeel_sahayak.agents.sutradhar.planning import FACTOR_LABEL, FILTERED_TOOLS, TOOL_STORES, item_key
from vakeel_sahayak.agents.sutradhar.prompts import TASK_FREE_PLAN, USER_PROMPT_TEMPLATES, FreePlan
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.models.offline_llm import OfflineRequest
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, PlanStep, SlotResult

if TYPE_CHECKING:
    from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

RRF_K = 60  # the usual reciprocal-rank-fusion constant
B4_TOP = 10  # fused items per factor
B4_STORE_CALLS = 12  # no contract, so no 8-call contract budget: room for the nine calls of one factor
FREE_CORPUS_TOOLS = ("search_reasoning", "search_objections", "search_arguments", "similar_orders")


def rrf_fuse(rankings: list[list[dict[str, Any]]], k: int = RRF_K, top: int = B4_TOP) -> list[dict[str, Any]]:
    """Reciprocal-rank fusion: an item's score is the sum of 1 / (k + rank) over the lists it appears in (rank from 1).

    Args:
        rankings: ranked lists of items (dicts), best first; items are matched by `planning.item_key`
        k: damping constant (60)
        top: how many fused items to return

    Returns:
        The best items, each with `rrf` (score) and `stores` (indexes of the lists it came from), best first; ties keep
        the order of first appearance.
    """
    score: dict[str, float] = {}
    best: dict[str, dict[str, Any]] = {}
    where: dict[str, list[int]] = {}
    order: list[str] = []
    for li, ranked in enumerate(rankings):
        for rank, item in enumerate(ranked, start=1):
            key = item_key(item)
            if key not in best:
                best[key], order = dict(item), [*order, key]
            score[key] = score.get(key, 0.0) + 1.0 / (k + rank)
            where.setdefault(key, []).append(li)
    ranked_keys = sorted(order, key=lambda key: (-score[key], order.index(key)))
    return [{**best[key], "rrf": round(score[key], 6), "stores": where[key]} for key in ranked_keys[:top]]


def run_b4(agent: SutradharAgent, state: CaseGraphState) -> list[EvidencePack]:
    """Query every store with the facts and the factor name, fuse by reciprocal-rank fusion (B4)."""
    shells = agent.pick_factors(state)
    pctx = agent.plan_context(state)
    set_limits = getattr(agent.budgets, "set_factor_limits", None)
    packs: list[EvidencePack] = []
    for shell in shells:
        if shell.stance == FactorStance.NOT_APPLICABLE:
            continue
        factor = shell.factor
        if set_limits is not None:
            set_limits(factor.value, store_calls=B4_STORE_CALLS)
        query = f"{pctx.facts_summary()} {FACTOR_LABEL[factor]}"[:1500]
        k = {"before": pctx.before, "k": 10}
        calls = [
            PlanStep(slot="fused", tool="search_reasoning", args={"query": query, **k}),
            PlanStep(slot="fused", tool="search_objections", args={"query": query, **k}),
            PlanStep(slot="fused", tool="search_arguments", args={"query": query, **k}),
            PlanStep(slot="fused", tool="similar_orders", args={"facts_text": query, **k}),
            PlanStep(slot="fused", tool="search_case_docs", args={"case_id": pctx.case_id, "query": query, "k": 10}),
            PlanStep(slot="fused", tool="search_statutes", args={"query": query, "k": 10}),
            PlanStep(slot="fused", tool="get_timeline", args={"case_id": pctx.case_id}),
            PlanStep(slot="fused", tool="get_fact", args={"case_id": pctx.case_id, "field": "antecedents"}),
            PlanStep(slot="fused", tool="get_fact", args={"case_id": pctx.case_id, "field": "personal"}),
        ]
        with agent.factor_scope(factor):
            outcomes = agent.parallel(calls, lambda s, fac=factor: agent.exec_step(s, fac))
        rankings, counts = [], []
        for step, out in zip(calls, outcomes, strict=False):
            store = TOOL_STORES.get(step.tool)
            tagged = [{**it, "store": store.value if store else step.tool} for it in out.items]
            rankings.append(tagged)
            counts.append(f"{step.tool}: {len(tagged)}" + (f" ({out.error.kind})" if out.error else ""))
        fused = rrf_fuse(rankings)
        stores = [str(call.tool) for call in calls]
        for it in fused:
            it["stores"] = sorted({stores[i] for i in it["stores"]})
        status = SlotStatus.FILLED if fused else SlotStatus.MISSING
        note = "B4: every store queried with the facts and the factor name, fused by reciprocal-rank fusion; " + ", ".join(counts)
        issues = [] if fused else [f"Nothing retrieved for {factor.value} (B4)."]
        agent._decision("b4", f"{factor.value}: {len(fused)} fused item(s) from {sum(1 for r in rankings if r)} store(s).", factor=factor.value, counts=counts)
        packs.append(EvidencePack(factor=factor, stance=shell.stance, reason=shell.reason, slots=[SlotResult(slot="fused", status=status, items=fused, note=note)], open_issues=issues))
    return packs


def run_free_planner(agent: SutradharAgent, state: CaseGraphState) -> list[EvidencePack]:
    """A7: the model plans the calls with no evidence contracts; the calls run as written, nothing is assessed or re-planned."""
    shells = agent.pick_factors(state)
    pctx = agent.plan_context(state)
    chosen = [s for s in shells if s.stance != FactorStance.NOT_APPLICABLE]
    if not chosen:
        return []
    allowed = [t for t in agent.allowed_tools() if t in TOOL_STORES or t in ("rights_check", "date_calc")]
    sections = []
    for s in pctx.sig.sections[:3]:
        parts = str(s.get("ref", "")).split(" ", 1)
        if len(parts) == 2:
            sections.append(parts)
    case = {
        "case_id": pctx.case_id, "before": pctx.before, "as_of": pctx.as_of, "tools": allowed, "sections": sections,
        "section_family": pctx.family, "factors": [{"factor": s.factor.value, "stance": s.stance.value, "phrase": FACTOR_LABEL[s.factor]} for s in chosen],
    }  # fmt: skip
    try:
        out = agent.ask(TASK_FREE_PLAN, USER_PROMPT_TEMPLATES[TASK_FREE_PLAN].format(), case=case, schema=FreePlan, max_tokens=1500)
        plan = out if isinstance(out, FreePlan) else FreePlan.model_validate(out)
    except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError):
        plan = FreePlan.model_validate(free_plan_offline(OfflineRequest(task=TASK_FREE_PLAN, instructions="", data={"case": case}, prompt="", schema=None)))
    first = chosen[0].factor
    steps: list[tuple[Factor, PlanStep]] = []
    for s in plan.steps:
        try:
            factor = Factor(s.factor)
        except ValueError:
            factor = first
        if s.tool not in allowed:
            agent._decision("free_plan_refused", f"The planner named {s.tool}, which Sutradhar may not use.", tool=s.tool)
            continue
        args = {k: v for k, v in s.args.items() if v not in (None, [], "")}
        if s.tool in FREE_CORPUS_TOOLS and "before" not in args:
            args["before"] = pctx.before  # the leakage rule is not the planner's to waive
        if not pctx.switches.retrieval_filters and s.tool in FILTERED_TOOLS:
            args.pop("factor", None)
            args.pop("section_family", None)
        steps.append((factor, PlanStep(slot=f"free:{s.tool}", tool=s.tool, args=args)))
    agent._decision("free_plan", f"The free planner wrote {len(steps)} call(s) with no contract.", steps=[{"factor": f.value, **st.model_dump()} for f, st in steps])
    outcomes = agent.parallel(steps, lambda fs: agent.exec_step(fs[1], fs[0]))
    by_factor: dict[Factor, dict[str, list[dict[str, Any]]]] = {}
    for (factor, step), out in zip(steps, outcomes, strict=False):
        by_factor.setdefault(factor, {}).setdefault(step.slot, []).extend(out.items)
    packs = []
    for shell in chosen:
        got = by_factor.get(shell.factor, {})
        slots = [
            SlotResult(slot=name, status=SlotStatus.FILLED if items else SlotStatus.MISSING, items=items, note="A7: free plan, no contract, no check")
            for name, items in got.items()
        ]  # fmt: skip
        packs.append(EvidencePack(factor=shell.factor, stance=shell.stance, reason=shell.reason, slots=slots, open_issues=[]))
    return packs
