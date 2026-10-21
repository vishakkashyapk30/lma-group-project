"""S1 retrieval critique with corrective re-retrieval: `Switches.retrieval_policy='self_critique'` (Self-RAG, ICLR 2024; CRAG, 2024).

Default-off equivalence is pinned to `golden_default_run.json` (captured before any variant existed).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar import critique
from vakeel_sahayak.agents.sutradhar.prompts import SlotCritique
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind, Factor, SlotStatus

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S1 = Switches.for_variant("S1")
PARITY = Factor.PARITY_WITH_CO_ACCUSED


def decisions(env, tool: str) -> list[dict]:
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


# ---- switches --------------------------------------------------------------------------------------------------
def test_switch_default_and_variant_name():
    assert Switches().retrieval_policy == "contract" and S1.retrieval_policy == "self_critique"
    assert S1.variant() == "S1" and "critique" in S1.describe() and "S1" in Switches.implemented_variants()


def test_s1_cannot_combine_with_a6_or_a7():
    for bad in ({"fixed_router": True}, {"free_planner": True}):
        with pytest.raises(ValueError):
            Switches(retrieval_policy="self_critique", **bad)


# ---- default-off equivalence -----------------------------------------------------------------------------------
@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_explicit_contract_policy_is_byte_identical_to_the_default(world):
    w = h.case_0007_world(second_parity=world.endswith("parity"))
    env = build(switches=Switches(retrieval_policy="contract"), world=w)
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert env.agent.retrieval_signals == {} and not decisions(env, "critique")


# ---- the offline critic ----------------------------------------------------------------------------------------
def test_offline_verdicts_are_deterministic_and_graded():
    case = {"factor": "parity_with_co_accused", "slot": "authority", "need": 1, "used": []}
    corpus = {"passages": [
        {"id": "D#1", "text": "parity: a co-accused of equal role was released", "tags": [], "in_family": True},
        {"id": "D#2", "text": "parity applies, similarly placed co-accused", "tags": [], "in_family": False},
        {"id": "D#3", "text": "a tenancy dispute about rent", "tags": [], "in_family": True},
    ]}
    out = critique.critique_data(case, corpus)
    assert out == critique.critique_data(case, corpus)
    assert [(v["relevant"], v["support"]) for v in out["verdicts"]] == [(True, "full"), (True, "partial"), (False, "none")]
    assert out["action"] == "keep"
    SlotCritique.model_validate(out)


@pytest.mark.parametrize(
    ("correct", "relevant", "judged", "used", "want"),
    [
        (1, 1, 3, [], "keep"),
        (0, 2, 3, [], "relax"),  # ambiguous: relax first
        (0, 2, 3, ["relax"], "requery"),
        (0, 0, 3, [], "discard"),  # incorrect with paragraphs: drop them
        (0, 0, 0, [], "requery"),  # incorrect with nothing: nothing to discard
        (0, 0, 3, ["discard", "requery", "relax", "switch_store"], "switch_store"),
    ],
)
def test_action_choice_follows_the_counts(correct, relevant, judged, used, want):
    assert critique.choose_action(correct, relevant, judged, 1, used) == want


def test_reorder_puts_the_critics_moves_first():
    ladder = ["relax:0", "relax:1", "reword", "sc_follow", "other_store"]
    assert critique.reorder(ladder, "requery")[0] == "reword"
    assert critique.reorder(ladder, "switch_store")[:2] == ["sc_follow", "other_store"] or critique.reorder(ladder, "switch_store")[0] == "other_store"
    assert critique.reorder(ladder, None) == ladder and sorted(critique.reorder(ladder, "discard")) == sorted(ladder)


# ---- behaviour on case-0007 ------------------------------------------------------------------------------------
def test_run_is_deterministic():
    runs = [canonical_run(build(switches=S1)) for _ in range(2)]
    assert digest(runs[0]["packs"]) == digest(runs[1]["packs"]) and digest(runs[0]["plans"]) == digest(runs[1]["plans"])


def test_critic_replaces_rules_for_corpus_slots_only():
    env = build(switches=S1)
    out = env.agent.run(env.state)
    judged = {(d["factor"], d["slot"]) for d in decisions(env, "critique")}
    assert judged and all(slot in {"authority", "conditions", "likely_objection", "argument_patterns"} for _, slot in judged)
    parity = next(p for p in out.evidence_packs if p.factor == PARITY)
    case_slot = next(s for s in parity.slots if s.slot == "co_accused_order")
    assert case_slot.status == SlotStatus.FILLED and all("critique" not in i for i in case_slot.items)
    authority = next(s for s in parity.slots if s.slot == "authority")
    assert authority.items and all(i["critique"]["relevant"] for i in authority.items)


def test_hard_guards_stay_rules_leakage_and_part(monkeypatch):
    """A paragraph dated on or after the case, or not court reasoning, never reaches the critic even if the critic would accept it."""
    env = build(switches=S1)
    env.agent.retrieve(env.state, [PARITY])
    work = env.agent._work[PARITY]
    sw = work.slots["authority"]
    before = work.pctx.before
    base = {"doc_id": "X", "para": 1, "court": "HC", "text": "parity co-accused released", "factors": ["parity_with_co_accused"], "section_family": [], "part": "reasoning"}
    later = {**base, "doc_id": "LATE", "date": "2999-01-01"}
    submission = {**base, "doc_id": "SUB", "part": "prosecution_submissions"}
    ok = {**base, "doc_id": "OK", "date": "2000-01-01"}
    seen = []
    real_ask = env.agent.ask
    def spy(task, instr, **kw):
        seen.extend(p["id"] for p in (kw.get("corpus") or {}).get("passages", []))
        return real_ask(task, instr, **kw)
    monkeypatch.setattr(env.agent, "ask", spy)
    monkeypatch.setattr(env.agent, "_budget_spent", lambda work: False)  # the factor's calls may be used up after retrieval
    sw.verdicts.clear()
    res = critique.critique_assess(env.agent, work, sw, [later, submission, ok])
    assert before > "2000-01-01" and seen == ["OK#1"] and [i["doc_id"] for i in res.items] == ["OK"]


def test_corrective_moves_are_driven_by_the_critic_and_counted():
    env = build(switches=S1)
    out = env.agent.run(env.state)
    sig = out.retrieval_signals
    assert sig and all(s["retrieval_policy"] == "self_critique" for s in sig.values())
    total = sum(s["critique"]["re_retrievals"] for s in sig.values())
    assert total > 0 and total == len(decisions(env, "critic_action"))
    for s in sig.values():
        c = s["critique"]
        assert c["relevant"] + c["not_relevant"] == c["judged"] and c["supported"] <= c["relevant"]
        assert {a["action"] for a in c["actions"]} <= set(critique.ACTIONS)


def test_signals_are_events_and_state_fields():
    env = build(switches=S1)
    out = env.agent.run(env.state)
    emitted = {d["factor"]: d for d in decisions(env, "retrieval_signals")}
    assert set(emitted) == set(out.retrieval_signals) and all("critique" in d for d in emitted.values())


def test_a_slot_with_nothing_retrieved_needs_no_critic_call():
    env = build(switches=S1)
    out = env.agent.run(env.state)
    calls = [e for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and (e.inputs or {}).get("task") == critique.TASK_CRITIQUE]
    assessed = len(decisions(env, "critique"))
    assert 0 < len(calls) < assessed
    assert sum(s["critique"]["critic_calls"] for s in out.retrieval_signals.values()) == len(calls)


def test_verdicts_are_cached_so_a_paragraph_is_judged_once():
    env = build(switches=S1)
    env.agent.run(env.state)
    for work in env.agent._work.values():
        assert work.critique.judged == sum(len(sw.verdicts) for sw in work.slots.values())


def test_the_models_action_is_used_but_keep_on_a_short_slot_is_overridden(monkeypatch):
    real = critique.critique_data
    def fake(case, corpus):
        out = real(case, corpus)
        return {**out, "action": "keep"}
    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.offline.critique_data", fake)
    env = build(switches=S1)
    out = env.agent.run(env.state)
    assert any(a["action"] != "keep" for s in out.retrieval_signals.values() for a in s["critique"]["actions"])


def test_a_failed_critic_falls_back_to_the_rules(monkeypatch):
    def boom(case, corpus):
        raise ValueError("no critic")
    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.offline.critique_data", boom)
    env = build(switches=S1)
    out = env.agent.run(env.state)
    rule_items = [i for p in out.evidence_packs for s in p.slots if s.slot == "authority" for i in s.items]
    assert rule_items and all("critique" not in i for i in rule_items)  # the rules assessed every slot the critic could not
    assert sum(s["critique"]["critic_failures"] for s in env.agent.retrieval_signals.values()) >= 1


# ---- budgets ---------------------------------------------------------------------------------------------------
def test_budgets_are_respected_and_critic_tokens_are_charged():
    env = build(switches=S1, budgets=BudgetTracker(tokens_per_case=20000))
    env.agent.run(env.state)
    snap = env.budgets.snapshot()
    assert all(v <= 8 for v in snap.store_calls.values()) and snap.tokens_spent <= snap.tokens_cap + 500
    calls = [e for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and (e.inputs or {}).get("task") == critique.TASK_CRITIQUE]
    assert all(e.outputs["budget_charge"]["tokens"] > 0 and e.outputs["budget_charge"]["factor"] for e in calls)


def test_no_critic_call_once_the_factor_budget_is_spent():
    env = build(switches=S1)
    env.agent.retrieve(env.state, [PARITY])
    work = env.agent._work[PARITY]
    work.budget_hit = True
    sw = work.slots["authority"]
    sw.verdicts.clear()
    item = {"doc_id": "Z", "para": 3, "court": "HC", "text": "parity co-accused", "factors": ["parity_with_co_accused"], "part": "reasoning", "date": "2000-01-01"}
    before = work.critique.skipped_budget
    assert critique.critique_assess(env.agent, work, sw, [item]) is None
    assert work.critique.skipped_budget == before + 1


def test_second_parity_world_fills_without_corrective_moves():
    env = build(switches=S1, world=h.case_0007_world(second_parity=True))
    out = env.agent.run(env.state)
    assert out.retrieval_signals[PARITY.value]["critique"]["re_retrievals"] == 0
