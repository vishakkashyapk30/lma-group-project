"""S3 (A11b) sufficiency stopping: `Switches.stopping` = 'rules' | 'rules_llm' | 'llm' (evaluation plan 3.3; Sufficient Context, ICLR 2025).

Default-off equivalence is pinned to digests captured from the code before the variants existed
(`golden_default_run.json`: case-0007 and the second-parity world, offline model, retrieval only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar.sufficiency import rate_data, rater_inputs, signals_of, supported_count
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind, Factor, SlotStatus

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
WORLDS = {"case_0007": lambda: h.case_0007_world(), "case_0007_second_parity": lambda: h.case_0007_world(second_parity=True)}
PARITY = Factor.PARITY_WITH_CO_ACCUSED


def decisions(env, tool: str) -> list[dict]:
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


# ---- switches --------------------------------------------------------------------------------------------------
def test_switch_default_and_variant_names():
    assert Switches().stopping == "rules" and Switches().variant() == "full"
    assert Switches.for_variant("S3").stopping == "rules_llm" and Switches.for_variant("a11b") == Switches.for_variant("S3")
    assert Switches.for_variant("S3b").stopping == "llm"
    assert Switches(stopping="rules_llm").variant() == "S3" and Switches(stopping="llm").variant() == "S3b"
    assert "sufficiency" in Switches(stopping="llm").describe()


def test_stopping_variants_cannot_combine_with_a6_or_a7():
    for bad in ({"fixed_router": True}, {"free_planner": True}):
        with pytest.raises(ValueError):
            Switches(stopping="llm", **bad)
    with pytest.raises(ValueError):
        Switches(stopping="sometimes")


# ---- default-off equivalence -----------------------------------------------------------------------------------
@pytest.mark.parametrize("world", sorted(WORLDS))
def test_default_run_is_byte_identical_to_the_run_before_the_variants(world):
    run = canonical_run(build(world=WORLDS[world]()))
    assert {k: digest(v) for k, v in run.items()} == GOLDEN[world]


def test_explicit_rules_stopping_equals_default():
    env = build(switches=Switches(stopping="rules"))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN["case_0007"]
    assert env.agent.retrieval_signals == {} and not decisions(env, "sufficiency")


# ---- the offline rater -----------------------------------------------------------------------------------------
def test_rater_inputs_split_public_court_text_from_private_case_text():
    env = build()
    env.agent.retrieve(env.state, [PARITY])
    case, corpus = rater_inputs(env.agent._work[PARITY])
    assert case["factor"] == "parity_with_co_accused" and {s["slot"] for s in case["slots"]} >= {"authority", "co_accused_order"}
    assert all(i["id"].count("#") == 1 for items in corpus["evidence"].values() for i in items)
    assert all("text" in i for s in case["slots"] for i in s["case_evidence"])


def test_offline_rater_is_deterministic_and_names_missing_slots():
    case = {"factor": "parity_with_co_accused", "slots": [{"slot": "authority", "need": 2, "status": "FILLED", "n_items": 1, "case_evidence": []}]}
    corpus = {"evidence": {"authority": [{"id": "D#1", "text": "parity: a co-accused of equal role was released"}]}}
    first = rate_data(case, corpus)
    assert first == rate_data(case, corpus) and first["sufficient"] is False and first["missing"] == ["authority"]
    corpus["evidence"]["authority"].append({"id": "D#2", "text": "similarly placed co-accused granted bail"})
    assert rate_data(case, corpus)["sufficient"] is True
    assert supported_count("parity_with_co_accused", case["slots"][0], [{"id": "X#1", "text": "unrelated tenancy dispute"}]) == 0


# ---- behaviour of the arms -------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["rules_llm", "llm"])
def test_variant_runs_are_deterministic(mode):
    runs = [canonical_run(build(switches=Switches(stopping=mode))) for _ in range(2)]
    assert digest(runs[0]["packs"]) == digest(runs[1]["packs"]) and digest(runs[0]["plans"]) == digest(runs[1]["plans"])


def test_rules_llm_only_asks_the_rater_when_the_rules_say_filled():
    """In the second-parity world every slot fills in round 1: the rater is asked once and agrees, so the run equals the default."""
    env = build(switches=Switches(stopping="rules_llm"), world=h.case_0007_world(second_parity=True))
    env.agent.run(env.state)
    judged = [d for d in decisions(env, "sufficiency") if d["factor"] == PARITY.value]
    assert judged and all(d["rules_short"] == [] for d in judged)
    assert env.agent.retrieval_signals[PARITY.value]["over_search_calls"] == 0


def test_rules_llm_can_veto_a_stop_and_search_on(monkeypatch):
    """The rules fill every parity slot in round 1; an 'insufficient' verdict on authority reopens it for a second round, then the rater agrees."""
    from vakeel_sahayak.agents.sutradhar.prompts import SufficiencyJudgment

    verdicts = iter([SufficiencyJudgment(sufficient=False, missing=["authority"], reason="thin"), SufficiencyJudgment(sufficient=True)])
    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.agent.rate", lambda agent, work: next(verdicts) if work.factor == PARITY else SufficiencyJudgment(sufficient=True))
    env = build(switches=Switches(stopping="rules_llm"), world=h.case_0007_world(second_parity=True))
    out = env.agent.run(env.state)
    sig = env.agent.retrieval_signals[PARITY.value]
    assert sig["rounds"] == 2 and sig["stopped"] == "rater_sufficient" and sig["rater_calls"] == 2
    assert sig["rule_pass_calls"] is not None and sig["over_search_calls"] > 0 and sig["stopped_too_early"] is False
    assert [p.round for p in out.plans if p.factor == PARITY] == [1, 2]


def test_llm_mode_stops_on_a_sufficient_verdict_and_flags_stopping_before_the_rules(monkeypatch):
    from vakeel_sahayak.agents.sutradhar import sufficiency
    from vakeel_sahayak.agents.sutradhar.prompts import SufficiencyJudgment

    monkeypatch.setattr(sufficiency, "rate", lambda agent, work: SufficiencyJudgment(sufficient=True, reason="enough"))
    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.agent.rate", sufficiency.rate)
    env = build(switches=Switches(stopping="llm"))
    out = env.agent.run(env.state)
    sig = env.agent.retrieval_signals[PARITY.value]
    assert sig["stopped"] == "rater_sufficient" and sig["rounds"] == 1 and sig["stopped_too_early"] is True
    assert out.retrieval_signals[PARITY.value]["stopped_too_early"] is True
    assert env.budgets.snapshot().store_calls[PARITY.value] < 8


def test_a_failed_rater_falls_back_to_the_rules(monkeypatch):
    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.agent.rate", lambda agent, work: None)
    env = build(switches=Switches(stopping="llm"))
    run = canonical_run(env)
    assert {digest(run["packs"]), digest(run["plans"])} == {GOLDEN["case_0007"]["packs"], GOLDEN["case_0007"]["plans"]}
    assert all(s["rater_failures"] >= 1 for s in env.agent.retrieval_signals.values())


# ---- budgets and signals ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["rules_llm", "llm"])
def test_budgets_are_respected_and_rater_tokens_are_charged(mode):
    env = build(switches=Switches(stopping=mode), budgets=BudgetTracker(tokens_per_case=20000))
    env.agent.run(env.state)
    snap = env.budgets.snapshot()
    assert all(v <= 8 for v in snap.store_calls.values()) and snap.tokens_spent <= snap.tokens_cap + 500  # a call that started under the cap may overshoot it slightly, as in the default loop


@pytest.mark.parametrize("mode", ["rules_llm", "llm"])
def test_rater_calls_are_charged_to_the_factor_token_budget(mode):
    env = build(switches=Switches(stopping=mode), world=h.case_0007_world(second_parity=True))
    env.agent.run(env.state)
    llm_calls = [e for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and (e.inputs or {}).get("task") == "sutradhar.rate_sufficiency"]
    assert llm_calls and all(e.outputs["budget_charge"]["tokens"] > 0 and e.outputs["budget_charge"]["factor"] for e in llm_calls)


def test_signals_are_events_and_state_fields_with_the_plan_metrics():
    env = build(switches=Switches(stopping="rules_llm"))
    out = env.agent.run(env.state)
    emitted = {d["factor"]: d for d in decisions(env, "retrieval_signals")}
    assert set(emitted) == set(out.retrieval_signals) and emitted
    for sig in out.retrieval_signals.values():
        assert {"stopped_too_early", "over_search_calls", "rater_calls", "judgments", "rule_pass_calls", "store_calls"} <= set(sig)
        assert sig["over_search_calls"] >= 0 and sig["rater_calls"] == len(sig["judgments"])


def test_signals_of_counts_calls_after_the_rules_first_passed():
    env = build(switches=Switches(stopping="rules_llm"))
    env.agent.retrieve(env.state, [PARITY])
    work = env.agent._work[PARITY]
    work.stopping.rule_pass_calls = 3
    assert signals_of(work, "rules_llm", 8, 100)["over_search_calls"] == 5
    work.stopping.rule_pass_calls = None
    assert signals_of(work, "rules_llm", 8, 100)["over_search_calls"] == 0


def test_slot_statuses_still_come_from_the_rules():
    env = build(switches=Switches(stopping="rules_llm"))
    out = env.agent.run(env.state)
    parity = next(p for p in out.evidence_packs if p.factor == PARITY)
    assert {s.status for s in parity.slots} <= set(SlotStatus)
