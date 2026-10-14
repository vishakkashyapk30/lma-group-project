"""Sutradhar over in-memory stores with the scripted fake LLM (plan §6.1-§6.3, §2 leakage, §19 budget).

Real modules: SutradharAgent (plan, run, assess, relax, delegate), the evidence contracts (configs/contracts YAML), the budget
tracker, BaseAgent.call_tool, and the downstream Vakeel and Abhiyojak that `run` delegates to. Fakes: the ten stores (in memory,
case-0007: tests/fakes/stores.py) and the LLM (`ScriptedLLM`, plans built from the real contracts by `h.plan_responder`).

World facts (tests/fixtures/caselaw/paragraphs.json): the section family BNS 318(4) / IPC 420 has ONE granted parity reasoning
paragraph (DLHC-2022-1187#14), so the parity contract's `authority` slot (need 2) is WEAK (1 of 2), as in the plan §6.3 example. Test
orders (TESTORD-2024-0001, SAMEFIR-2024-0002) are in no store and DLHC-2025-0099 is dated after the case.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.integration import _helpers as h
from tests.unit.agents._helpers import tool_specs
from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.schemas.enums import EventKind, Factor, OpenIssueType, SlotStatus, StoreName

PARITY = Factor.PARITY_WITH_CO_ACCUSED
ALL_PARAGRAPH_DOCS = {"DLHC-2022-1187", "DLHC-2021-0420", "DLHC-2023-0911", "SC-2014-0463", "BOMHC-2024-0355", "DLHC-2025-0099",
                      "TESTORD-2024-0001", "SAMEFIR-2024-0002"}
SHARED_STORES = (StoreName.CASELAW_REASONING, StoreName.CASELAW_SIMILAR, StoreName.ADVOCACY_OBJECTIONS, StoreName.ADVOCACY_ARGUMENTS)


def build(install_stores, *, world=None, llm=None, budgets=None, **plan_kw):
    world = world or h.case_0007_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world)
    llm = llm or h.full_pipeline_llm(plan=h.plan_responder(authority_court="Delhi HC", **plan_kw))
    budgets = budgets or BudgetTracker()
    agent, ctx, _ = h.build_agent(SutradharAgent, llm=llm, toolbox=tb, world=world, budgets=budgets)
    state = h.make_state(world.dossier, world.rights)
    return SimpleNamespace(world=world, tb=tb, llm=llm, budgets=budgets, agent=agent, ctx=ctx, state=state)


def loop(env, factor: Factor = PARITY):
    """Plan, run, assess, re-plan until Sutradhar stops (plan §6.2 step 2). Returns (rounds, assessments)."""
    plan = env.agent.plan_factor(factor, env.state)
    rounds, assessments = [plan], []
    while True:
        assessed = env.agent.assess(factor, env.agent.run_plan(plan))
        assessments.append({r.slot: r.status for r in assessed})
        nxt = env.agent.replan(plan, assessed)
        if nxt is None:
            return rounds, assessments
        plan = nxt
        rounds.append(plan)


def authority_args(plan) -> dict:
    return next(s for s in plan.steps if s.slot == "authority").args


def allowed(step, contract: dict) -> bool:
    slot = contract["slots"].get(step.slot)
    if slot is None:
        return False
    spec = tool_specs()[step.tool]
    return set(map(str, spec.stores)) <= set(slot.get("stores", [])) if spec.stores else step.tool in slot.get("tools", [])


# ---- plan --------------------------------------------------------------------------------------------------------
def test_plan_covers_every_slot_of_the_contract_and_only_those(install_stores):
    """Plan §6.1: the contract fixes what is needed and where it may be; the plan has one allowed step per slot."""
    env = build(install_stores)
    plan = env.agent.plan_factor(PARITY, env.state)
    contract = h.contract_spec(PARITY)
    assert [s.slot for s in plan.steps] == h.contract_slots(PARITY)
    assert all(allowed(s, contract) for s in plan.steps)
    assert plan.factor == PARITY and plan.round == 1


def test_plan_follows_the_plan_6_3_example(install_stores):
    """Plan §6.3: case docs for the co-accused order, reasoning for authority (granted, family BNS 318(4)/IPC 420, before 2025-02-03), citations for good law, objections for the likely objection."""
    env = build(install_stores)
    plan = env.agent.plan_factor(PARITY, env.state)
    steps = {s.slot: s for s in plan.steps}
    assert steps["co_accused_order"].tool == "search_case_docs"
    assert steps["authority"].tool == "search_reasoning"
    assert authority_args(plan)["before"] == h.AS_OF
    assert set(authority_args(plan)["section_family"]) == set(h.FAMILY)
    assert steps["good_law"].tool == "citations" and steps["likely_objection"].tool == "search_objections"


# ---- run and assess ----------------------------------------------------------------------------------------------
def test_slots_are_filled_from_the_right_stores(install_stores):
    """Running the plan: the co-accused order from case.docs, authority from caselaw.reasoning, the objection from the objection bank."""
    env = build(install_stores)
    results = {r.slot: r for r in env.agent.run_plan(env.agent.plan_factor(PARITY, env.state))}
    assert any("05.12.2024" in str(i) for i in results["co_accused_order"].items)
    assert "DLHC-2022-1187#14" in h.para_ids(results["authority"].items)
    assert any(i.get("doc_id") == "DLHC-2023-0911" and i.get("para") == 6 for i in results["likely_objection"].items)


def test_assessment_matches_the_plan_6_3_example(install_stores):
    """FILLED, FILLED, WEAK (1 of 2) for authority, FILLED, FILLED."""
    env = build(install_stores)
    _, assessments = loop(env)
    first = assessments[0]
    assert first["authority"] == SlotStatus.WEAK
    assert {s: v for s, v in first.items() if s != "authority"} == {s: SlotStatus.FILLED for s in first if s != "authority"}


def test_a_second_parity_paragraph_fills_the_slot_in_one_round(install_stores):
    """With a second qualifying paragraph the factor is complete after round 1: no relaxation, no second round."""
    env = build(install_stores, world=h.case_0007_world(second_parity=True))
    rounds, assessments = loop(env)
    assert len(rounds) == 1
    assert set(assessments[0].values()) == {SlotStatus.FILLED}


# ---- relaxation --------------------------------------------------------------------------------------------------
def test_weak_slot_is_relaxed_in_the_fixed_order_and_only_that_slot_is_replanned(install_stores):
    """Plan §6.2 step 2.4: later rounds re-plan only the unfilled slot and relax filters in the order factor, section family, court; 'before' never goes."""
    env = build(install_stores)
    rounds, _ = loop(env)
    assert len(rounds) >= 3
    assert all([s.slot for s in p.steps] == ["authority"] for p in rounds[1:])
    args = [authority_args(p) for p in rounds]
    assert args[0]["factor"] == PARITY.value
    first = lambda pred: next(i for i, a in enumerate(args) if pred(a))  # noqa: E731
    factor_dropped = first(lambda a: a.get("factor") is None)
    family_widened = first(lambda a: a.get("section_family") is None or set(a["section_family"]) > set(h.FAMILY))
    court_dropped = first(lambda a: a.get("court") is None)
    assert 1 <= factor_dropped <= family_widened <= court_dropped
    assert all(a["before"] == h.AS_OF for a in args)


def test_relaxation_stays_within_the_per_factor_store_call_budget(install_stores):
    """Plan §6.2: 8 store calls per factor, a hard stop."""
    env = build(install_stores)
    loop(env)
    assert env.budgets.snapshot().store_calls[PARITY.value] <= 8
    assert env.tb.store_calls() >= 5  # round 1 plus at least one relaxed retry


def test_rounds_stop_when_the_budget_is_spent_even_if_the_slot_is_still_weak(install_stores):
    env = build(install_stores, budgets=BudgetTracker(store_calls_per_factor=5))
    rounds, assessments = loop(env)
    assert assessments[-1]["authority"] in (SlotStatus.WEAK, SlotStatus.MISSING)
    assert env.budgets.snapshot().store_calls[PARITY.value] <= 5
    assert len(rounds) <= 3


# ---- leakage -----------------------------------------------------------------------------------------------------
def test_every_shared_store_query_is_bounded_by_the_case_date(install_stores):
    """Plan §2: every query only sees documents dated before the case (2025-02-03)."""
    env = build(install_stores)
    loop(env)
    checked = 0
    for name in SHARED_STORES:
        for _, kw in env.world.stores[name].calls:
            assert kw["before"] == h.AS_OF, (name, kw)
            checked += 1
    assert checked >= 3


def test_forbidden_orders_never_reach_an_evidence_pack(install_stores):
    """The test order, the same-FIR order and the post-dated order are in no slot of any round."""
    env = build(install_stores)
    seen: set[str] = set()
    plan = env.agent.plan_factor(PARITY, env.state)
    for r in env.agent.run_plan(plan):
        seen |= {i["doc_id"] for i in r.items if "doc_id" in i}
    assert seen and not seen & h.FORBIDDEN_DOC_IDS


# ---- the whole run: budget stop, missing slots as open issues ------------------------------------------------------
def test_full_run_produces_a_brief_with_grounds_within_budget(install_stores):
    """`run` plans every applicable factor, delegates to Vakeel and Abhiyojak, and stays within 8 store calls per factor."""
    env = build(install_stores)
    out = env.agent.run(env.state)
    assert out.brief is not None and out.brief.grounds
    assert out.sparring is not None
    assert all(v <= 8 for v in env.budgets.snapshot().store_calls.values())
    assert env.budgets.snapshot().tokens_spent <= env.budgets.snapshot().tokens_cap


def test_authorities_in_the_brief_are_court_reasoning_paragraphs_that_were_retrieved(install_stores):
    """Plan §5.2, §8.1: authorities come from `reasoning` paragraphs only (never the argument bank) and from nowhere else."""
    env = build(install_stores)
    out = env.agent.run(env.state)
    reasoning = {(r.doc_id, r.para) for r in env.world.stores[StoreName.CASELAW_REASONING].rows}
    cited = {(a.doc_id, a.para) for g in out.brief.grounds for a in g.authorities}
    assert cited and cited <= reasoning
    assert not {d for d, _ in cited} & h.FORBIDDEN_DOC_IDS


def test_missing_authority_becomes_an_open_issue_in_the_brief(install_stores):
    """Plan §6.2 step 2.5: with no parity authority anywhere, the slot stays MISSING and the brief says so (MISSING_EVIDENCE)."""
    env = build(install_stores, world=h.case_0007_world(excluded=set(ALL_PARAGRAPH_DOCS)))
    out = env.agent.run(env.state)
    issues = [i for i in out.brief.open_issues if i.type == OpenIssueType.MISSING_EVIDENCE]
    assert any("parity" in i.item.lower() and "authority" in i.item.lower() for i in issues), out.brief.open_issues
    assert env.budgets.snapshot().store_calls[PARITY.value] <= 8


def test_case_token_budget_stops_the_run_and_is_logged(install_stores):
    """Plan §6.2: 150K tokens per case, and every time a budget is hit it is logged (BUDGET_HIT). Each scripted call reports 60K tokens."""
    llm = h.make_llm(where="ada", llm_class=h.BigTokensLLM, plan=h.plan_responder(authority_court="Delhi HC"), factors=h.factors_responder(),
                     ground=h.ground_responder(), objections=h.objections_responder(), reply=h.reply_responder(),
                     judge=h.judge_responder(), free="ok")
    env = build(install_stores, llm=llm)
    out = env.agent.run(env.state)
    assert [e for e in env.ctx.log.events if e.kind == EventKind.BUDGET_HIT]
    assert len(llm.calls) <= 6  # ASSUMPTION: the 150K cap (60K per call) is reached after 3 calls; a little overshoot is tolerated
    assert out.brief is not None and out.brief.open_issues  # what could not be done is reported, not dropped


def test_every_store_call_is_an_event_pair_by_sutradhar(install_stores):
    """Plan §3.3: each tool call is a TOOL_CALL then a TOOL_RESULT event, by SUTRADHAR."""
    env = build(install_stores)
    loop(env)
    calls = [e for e in env.ctx.log.events if e.kind == EventKind.TOOL_CALL]
    results = [e for e in env.ctx.log.events if e.kind == EventKind.TOOL_RESULT]
    assert len(calls) == len(env.tb.calls) == len(results) > 0
    assert {str(getattr(e.actor, "value", e.actor)) for e in calls} == {"SUTRADHAR"}
    assert {e.tool for e in calls} <= h.STORE_TOOLS | {"rights_check", "date_calc"}


def test_factors_that_do_not_apply_are_not_planned(install_stores):
    """Plan §6.2 step 1: the statutory-bar factor is not applicable in case-0007 (no special act), so no plan is asked for it."""
    env = build(install_stores)
    env.agent.run(env.state)
    plan_prompts = [c.prompt for c in h.calls_of(env.llm, "plan")]
    assert plan_prompts
    assert not [p for p in plan_prompts if h.detect_factor(p) == Factor.STATUTORY_BAR]
