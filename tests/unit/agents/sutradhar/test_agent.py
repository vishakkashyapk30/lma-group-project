"""SutradharAgent (plan §3.2, §6.1-§6.4): class facts (pass today) and behaviour (fail until implemented)."""

from __future__ import annotations

import copy
import inspect

import pytest
import yaml

from tests.fakes.models import ScriptedLLM
from tests.unit.agents._helpers import (
    CASE_DATE,
    REPO_ROOT,
    build_agent,
    make_state,
    models_yaml,
    para_dict,
    tool_specs,
)
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.schemas.chat import ChatMessage
from vakeel_sahayak.schemas.dossier import SectionValue
from vakeel_sahayak.schemas.enums import (
    AgentName,
    EventKind,
    Factor,
    FactorStance,
    RightsStatus,
    SlotStatus,
    StoreName,
)
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft, EvidencePack, PlanStep, RetrievalPlan, SlotResult

PARITY = Factor.PARITY_WITH_CO_ACCUSED
FAMILY = ["BNS 318(4)", "IPC 420"]


# ---- class facts ---------------------------------------------------------------------------------------------------
def test_class_facts():
    """Sutradhar is a concrete BaseAgent named SUTRADHAR running on the 14B agents model."""
    assert issubclass(SutradharAgent, BaseAgent) and not inspect.isabstract(SutradharAgent)
    assert SutradharAgent.NAME == AgentName.SUTRADHAR
    assert SutradharAgent.ROLE_MODEL == "agents_14b"
    assert "sutradhar" in models_yaml()["llm"]["agents_14b"]["used_by"]


@pytest.mark.parametrize(
    "method", ["run", "pick_factors", "plan_factor", "run_plan", "assess", "replan", "delegate", "answer_chat", "reopen_after_change"]
)
def test_method_exists(method):
    """The plan §6.2 loop steps exist as methods."""
    assert callable(getattr(SutradharAgent, method))


# ---- helpers -------------------------------------------------------------------------------------------------------
def contract(factor: str) -> EvidenceContract:
    path = REPO_ROOT / "src" / "vakeel_sahayak" / "contracts" / "factors" / f"{factor}.yaml"
    return EvidenceContract.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def parity_plan(round_: int = 1, drop_before: bool = False, budget=(99, 1)) -> RetrievalPlan:
    """The plan §6.3 example (a query is added because search_reasoning requires one)."""
    authority_args = {
        "query": "co-accused with identical role granted bail",
        "factor": PARITY.value,
        "section_family": FAMILY,
        "outcome": "granted",
        "court": "Delhi HC",
        "k": 10,
    }
    if not drop_before:
        authority_args["before"] = CASE_DATE
    return RetrievalPlan(
        factor=PARITY,
        round=round_,
        budget_left=BudgetLeft(store_calls=budget[0], tokens=budget[1]),
        steps=[
            PlanStep(slot="co_accused_order", tool="search_case_docs",
                     args={"case_id": "case-0007", "query": "co-accused granted bail", "doc_types": ["BAIL_ORDER"]}),
            PlanStep(slot="authority", tool="search_reasoning", args=authority_args),
            PlanStep(slot="good_law", tool="citations", args={"doc_ids": "$authority.top3", "want": ["overruled_by", "sc_root"]}),
            PlanStep(slot="likely_objection", tool="search_objections",
                     args={"query": "co-accused parity", "factor": PARITY.value, "section_family": FAMILY, "before": CASE_DATE}),
        ],
    )


def plan_llm(plan: RetrievalPlan) -> ScriptedLLM:
    # ASSUMPTION: plans are requested with json_schema=RetrievalPlan.model_json_schema(), so ScriptedLLM dispatches on
    # the title 'RetrievalPlan' (tests/fakes/__init__.py convention).
    return ScriptedLLM(by_schema={"RetrievalPlan": plan.model_dump(mode="json")}, strict=False, default="")


def step_is_allowed(step: PlanStep, contr: EvidenceContract) -> bool:
    """A step is allowed when its slot exists and its tool only reads stores the slot may use (or is a slot tool)."""
    slot = contr.slots.get(step.slot)
    if slot is None:
        return False
    spec = tool_specs()[step.tool]
    if spec.stores:
        return set(spec.stores) <= set(slot.stores)
    return step.tool in slot.tools


@pytest.fixture()
def state(dossier, expected_rights_report):
    return make_state(dossier=dossier, rights=expected_rights_report)


# ---- pick_factors (step 1) -------------------------------------------------------------------------------------------
def test_pick_factors_gives_every_factor_a_stance_and_reason(state):
    """All 12 factors get a stance and a non-empty reason; each pack is a shell (no slots yet)."""
    agent, _, toolbox = build_agent(SutradharAgent)
    packs = agent.pick_factors(state)
    assert [p.factor for p in packs].count(PARITY) == 1
    assert {p.factor for p in packs} == set(Factor) and len(packs) == 12
    for p in packs:
        assert isinstance(p, EvidencePack)
        assert p.stance in set(FactorStance)
        assert p.reason and p.reason.strip()
        assert p.slots == []
    # ASSUMPTION: stances come from the approved dossier and RightsReport alone (no retrieval, no LLM output needed).
    assert toolbox.store_calls() == 0


def test_pick_factors_case_0007_stances(state):
    """case-0007: parity and charge-sheet favourable; s.479 not reached; no special act."""
    agent, _, _ = build_agent(SutradharAgent)
    stance = {p.factor: p.stance for p in agent.pick_factors(state)}
    assert stance[PARITY] == FactorStance.FAVOURABLE  # Co-accused-1 granted bail 2024-12-05
    assert stance[Factor.CHARGE_SHEET_FILED] == FactorStance.FAVOURABLE  # filed 2024-11-02
    assert stance[Factor.UNDERTRIAL_PERIOD] in (FactorStance.NOT_APPLICABLE, FactorStance.ADVERSE)  # 167 < 852 days
    assert stance[Factor.STATUTORY_BAR] == FactorStance.NOT_APPLICABLE


def test_pick_factors_parity_not_applicable_without_a_granted_co_accused(dossier, expected_rights_report):
    """Contract 5 applies only if a co-accused has been granted bail: a rejected co-accused switches parity off."""
    d = copy.deepcopy(dossier)
    d.fields.co_accused_bail.value[0].outcome = "rejected"
    agent, _, _ = build_agent(SutradharAgent)
    stance = {p.factor: p.stance for p in agent.pick_factors(make_state(dossier=d, rights=expected_rights_report))}
    assert stance[PARITY] == FactorStance.NOT_APPLICABLE


def test_pick_factors_statutory_bar_is_adverse_when_the_radar_says_bar_applies(dossier, expected_rights_report):
    """An NDPS charge with a BAR_APPLIES radar entry makes the statutory-bar factor 'adverse (to be answered)'."""
    d = copy.deepcopy(dossier)
    d.fields.sections.value = [SectionValue(as_written="20 NDPS", code="NDPS", section="20", bailable=False, max_punishment="10 years")]
    r = copy.deepcopy(expected_rights_report)
    for c in r.checks:
        if c.check.value == "statutory_bar":
            c.status = RightsStatus.BAR_APPLIES
    agent, _, _ = build_agent(SutradharAgent)
    stance = {p.factor: p.stance for p in agent.pick_factors(make_state(dossier=d, rights=r))}
    assert stance[Factor.STATUTORY_BAR] == FactorStance.ADVERSE


# ---- plan_factor (step 2.1) ------------------------------------------------------------------------------------------
def test_plan_factor_returns_the_scripted_plan_within_the_contract(state):
    """The plan's steps only use tools the slot's stores allow, and the plan is requested once via the schema."""
    llm = plan_llm(parity_plan())
    agent, _, _ = build_agent(SutradharAgent, llm=llm, budgets=BudgetTracker())
    plan = agent.plan_factor(PARITY, state)
    assert isinstance(plan, RetrievalPlan) and plan.factor == PARITY
    assert plan.steps
    contr = contract("parity_with_co_accused")
    for step in plan.steps:
        assert step_is_allowed(step, contr), step
    assert len(llm.calls_for("RetrievalPlan")) == 1


def test_plan_factor_authority_slot_uses_reasoning_or_similar_orders(state):
    """The authority slot may only be served by search_reasoning or similar_orders (stores caselaw.reasoning/similar)."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    plan = agent.plan_factor(PARITY, state)
    authority_tools = {s.tool for s in plan.steps if s.slot == "authority"}
    assert authority_tools and authority_tools <= {"search_reasoning", "similar_orders"}


def test_plan_factor_shared_store_steps_always_carry_the_case_date(state):
    """Leakage rule: even if the model omits 'before', every shared-store step is bounded by the case date 2025-02-03."""
    # ASSUMPTION: the agent fills the mandatory 'before' from the dossier's as_of when the model leaves it out.
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan(drop_before=True)), budgets=BudgetTracker())
    plan = agent.plan_factor(PARITY, state)
    shared = {StoreName.CASELAW_REASONING, StoreName.CASELAW_SIMILAR, StoreName.ADVOCACY_OBJECTIONS, StoreName.ADVOCACY_ARGUMENTS}
    checked = 0
    for step in plan.steps:
        if set(tool_specs()[step.tool].stores) & shared:
            assert step.args.get("before") == CASE_DATE
            checked += 1
    assert checked >= 2


def test_plan_factor_budget_left_comes_from_the_tracker_not_the_model(state):
    """At round 1 budget_left is the fresh per-factor budget: 8 store calls and 12000 tokens."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan(budget=(99, 1))), budgets=BudgetTracker())
    plan = agent.plan_factor(PARITY, state)
    assert plan.round == 1
    assert plan.budget_left == BudgetLeft(store_calls=8, tokens=12000)


def test_plan_factor_never_keeps_a_step_outside_the_contract(state):
    """A model step that sends the authority slot to the argument bank (advocacy.arguments) is not allowed through."""
    bad = parity_plan()
    bad.steps.append(PlanStep(slot="authority", tool="search_arguments",
                              args={"query": "parity", "factor": PARITY.value, "before": CASE_DATE}))
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(bad), budgets=BudgetTracker())
    contr = contract("parity_with_co_accused")
    try:
        plan = agent.plan_factor(PARITY, state)
    except ValueError:
        return  # ASSUMPTION: rejecting the whole plan with ValueError is as good as dropping the bad step
    assert all(step_is_allowed(s, contr) for s in plan.steps)


# ---- run_plan (step 2.2) ---------------------------------------------------------------------------------------------
def test_run_plan_executes_every_step_through_call_tool(state):
    """One tool call per step, each logged as TOOL_CALL then TOOL_RESULT; results come back slot by slot in plan order."""
    agent, ctx, toolbox = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    results = agent.run_plan(parity_plan())
    assert [r.slot for r in results] == ["co_accused_order", "authority", "good_law", "likely_objection"]
    assert all(isinstance(r, SlotResult) for r in results)
    for tool in ("search_case_docs", "search_reasoning", "citations", "search_objections"):
        assert toolbox.count(tool) == 1
    assert ctx.log.tools_called() == ["search_case_docs", "search_reasoning", "citations", "search_objections"]
    kinds = [e.kind for e in ctx.log.events if e.kind in (EventKind.TOOL_CALL, EventKind.TOOL_RESULT)]
    assert kinds == [EventKind.TOOL_CALL, EventKind.TOOL_RESULT] * 4


def test_run_plan_authority_items_exclude_later_and_test_orders(state):
    """The authority results contain DLHC-2022-1187#14 and never DLHC-2025-0099 (post-dated) or the test-split order."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    authority = next(r for r in agent.run_plan(parity_plan()) if r.slot == "authority")
    ids = {(i["doc_id"], i["para"]) for i in authority.items}
    assert ("DLHC-2022-1187", 14) in ids
    assert not {d for d, _ in ids} & {"DLHC-2025-0099", "TESTORD-2024-0001"}


def test_run_plan_resolves_slot_references_before_calling(state):
    """'$authority.top3' is replaced by real doc ids from the authority results before the citations call."""
    # ASSUMPTION: '$slot.field' references are resolved by the agent (plan §6.3 shows '$authority.top3').
    agent, _, toolbox = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    agent.run_plan(parity_plan())
    call = next(c for c in toolbox.calls if c.name == "citations")
    assert isinstance(call.kwargs["doc_ids"], list)
    assert "$authority.top3" not in call.kwargs["doc_ids"]
    assert "DLHC-2022-1187" in call.kwargs["doc_ids"]


# ---- assess (step 2.3) -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "n_items, expected",
    [(2, SlotStatus.FILLED), (1, SlotStatus.WEAK), (0, SlotStatus.MISSING)],
)
def test_assess_marks_the_authority_slot(state, paragraphs, n_items, expected):
    """The parity contract needs 2 authorities: 2 -> FILLED, 1 -> WEAK, 0 -> MISSING."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    agent.plan_factor(PARITY, state)  # fixes the case date the rule checks use
    first = para_dict(paragraphs, "DLHC-2022-1187", 14)
    second = {**first, "doc_id": "DLHC-2021-0420", "para": 11, "date": "2021-03-10", "factors": ["parity_with_co_accused"]}
    raw = [SlotResult(slot="authority", status=SlotStatus.MISSING, items=[first, second][:n_items])]
    assessed = agent.assess(PARITY, raw)
    assert {r.slot: r.status for r in assessed}["authority"] == expected


def test_assess_ignores_post_dated_and_submission_paragraphs(state, paragraphs):
    """A post-dated order and a defence paragraph do not make the authority slot FILLED."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    agent.plan_factor(PARITY, state)
    items = [para_dict(paragraphs, "DLHC-2025-0099", 5), para_dict(paragraphs, "DLHC-2022-1187", 9)]
    assessed = agent.assess(PARITY, [SlotResult(slot="authority", status=SlotStatus.MISSING, items=items)])
    assert assessed[0].status == SlotStatus.MISSING


# ---- replan (step 2.4-2.5) -------------------------------------------------------------------------------------------
def weak_results() -> list[SlotResult]:
    return [SlotResult(slot="authority", status=SlotStatus.WEAK, note="WEAK (1 of 2)")]


def authority_args(plan: RetrievalPlan) -> dict:
    return next(s for s in plan.steps if s.slot == "authority").args


def test_replan_relaxes_filters_in_the_fixed_order_and_keeps_the_date(state):
    """Round 2 drops 'factor', round 3 widens the family, round 4 drops the court; 'before' survives every round."""
    # ASSUMPTION: the scripted model echoes the plan; the agent itself applies relax() step by step.
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    plan = parity_plan()
    p2 = agent.replan(plan, weak_results())
    assert p2 is not None and p2.round == 2
    a2 = authority_args(p2)
    assert a2.get("factor") is None and a2["section_family"] == FAMILY and a2["court"] == "Delhi HC"
    p3 = agent.replan(p2, weak_results())
    assert p3 is not None and p3.round == 3
    a3 = authority_args(p3)
    assert a3.get("section_family") is None or set(FAMILY) < set(a3["section_family"])
    assert a3["court"] == "Delhi HC"
    p4 = agent.replan(p3, weak_results())
    assert p4 is not None and p4.round == 4
    assert authority_args(p4).get("court") is None
    for p in (p2, p3, p4):
        assert authority_args(p)["before"] == CASE_DATE


def test_replan_stops_when_the_budget_is_exhausted(state):
    """No more rounds once the factor's 8 store calls are spent (hard budget, plan §6.2, §19)."""
    budgets = BudgetTracker()
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=budgets)
    budgets.charge(PARITY.value, store_calls=8)
    assert agent.replan(parity_plan(), weak_results()) is None


def test_replan_stops_when_everything_required_is_filled(state):
    """Nothing left to re-plan when every slot is FILLED."""
    agent, _, _ = build_agent(SutradharAgent, llm=plan_llm(parity_plan()), budgets=BudgetTracker())
    filled = [SlotResult(slot=s, status=SlotStatus.FILLED) for s in ("co_accused_order", "authority", "good_law", "likely_objection")]
    assert agent.replan(parity_plan(), filled) is None


# ---- answer_chat (§6.4) ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "question",
    ["Will my client get bail?", "What are the chances of bail?", "I am the accused, what should I do?"],
)
def test_answer_chat_refuses_predictions_and_lay_advice(state, question):
    """Refused: flagged refused, no tool is called, and the text makes no prediction."""
    agent, _, toolbox = build_agent(SutradharAgent)
    msg = agent.answer_chat(state, question)
    assert isinstance(msg, ChatMessage)
    assert msg.refused is True and msg.chips == []
    assert msg.agent == AgentName.SUTRADHAR and msg.case_id == "case-0007"
    assert msg.text.strip()
    assert toolbox.calls == []
    lowered = msg.text.lower()
    assert "%" not in lowered and "likely to be granted" not in lowered and "grant rate" not in lowered


def test_answer_chat_routes_section_question_to_map_section(state):
    """'BNS equivalent of 420 IPC?' is answered from the concordance, with a chip, citing BNS 318(4)."""
    agent, _, toolbox = build_agent(SutradharAgent)
    msg = agent.answer_chat(state, "BNS equivalent of 420 IPC?")
    assert msg.refused is False
    assert [c.tool for c in msg.chips] == ["map_section"]
    assert "318(4)" in msg.text
    call = toolbox.calls[0]
    assert call.name == "map_section" and call.kwargs["section"] == "420"
    assert str(call.kwargs["code"]).upper() == "IPC"


def test_answer_chat_custody_question_uses_timeline_and_date_calc(state):
    """'How many days in custody?' uses get_timeline and date_calc and states the day count."""
    import re

    agent, _, toolbox = build_agent(SutradharAgent)
    msg = agent.answer_chat(state, "How many days in custody?")
    assert {c.tool for c in msg.chips} == {"get_timeline", "date_calc"}
    assert {c.name for c in toolbox.calls} >= {"get_timeline", "date_calc"}
    # ASSUMPTION: the case fixture says 167 days; the fake date_calc 'inclusive_day_1' rule yields 168; both are accepted.
    assert re.search(r"\b16[78]\b", msg.text)
