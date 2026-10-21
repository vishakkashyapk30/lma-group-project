"""S10 / A8c Abhiyojak without context isolation (`Switches.abhiyojak_isolation=False`; Sweep 2, `docs/literature-to-code-map.md`).

The arm reads Vakeel's notes, open issues, factor reasons and replies. It is reachable only through the switch; with the default the
isolation guard stays in force (`ContextIsolationError`). Default-off equivalence: `tests/unit/agents/vakeel/test_variants_golden.py`.
"""

from __future__ import annotations

import json

import pytest

from tests.unit.agents._helpers import SpyBudget, build_agent
from tests.unit.agents.vakeel import _variants_helpers as vh
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.abhiyojak.isolation import ContextIsolationError, build_context, build_open_context
from vakeel_sahayak.models.offline_llm import OfflineLLM
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented

MARK = "VAKEEL_PRIVATE_NOTE"


class Recording(OfflineLLM):
    """The offline model that also keeps every prompt it was sent."""

    def __init__(self) -> None:
        super().__init__(role="agents_14b", where="ada")
        self.prompts: list[str] = []

    def generate(self, prompt, *a, **k):  # noqa: ANN001, ANN002, ANN003
        self.prompts.append(prompt)
        return super().generate(prompt, *a, **k)


def s10() -> Switches:
    return Switches.for_variant("S10")


def drafted(env, with_mark=True):
    """The state after Vakeel's run, with a private note attached the way the integration tests do."""
    after = env.vakeel.run(env.state)
    return after.model_copy(update={"vakeel_notes": MARK}) if with_mark else after


def test_selection_and_implemented():
    assert s10().abhiyojak_isolation is False and s10().variant() == "S10"
    assert Switches.for_variant("A8c").variant() == "S10"
    assert "S10" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("A8c")


def test_the_default_keeps_the_guard_and_the_open_context_is_unreachable():
    env = vh.build()
    assert env.abhiyojak.isolated
    with pytest.raises(ContextIsolationError):
        env.abhiyojak.guard({"vakeel_notes": MARK})
    with pytest.raises(ContextIsolationError):
        build_open_context(env.state, Switches())
    with pytest.raises(ContextIsolationError):
        build_context({"case_id": "case-0007", "vakeel_notes": MARK})
    assert env.abhiyojak.critic_signals() == {}


def test_the_default_arm_never_sends_vakeels_notes():
    llm = Recording()
    env = vh.build(abhiyojak_llm=llm)
    state = drafted(env)
    env.abhiyojak.spar(state)
    assert llm.prompts and not [p for p in llm.prompts if MARK in p or "vakeel_view" in p]


def test_the_open_arm_sends_vakeels_notes_and_says_so():
    llm = Recording()
    env = vh.build(switches=s10(), abhiyojak_llm=llm)
    state = drafted(env)
    env.abhiyojak.spar(state)
    assert [p for p in llm.prompts if MARK in p]
    assert all("vakeel_view" in p for p in llm.prompts if "raise_objections" in p)
    assert any("switched off to measure" in p for p in llm.prompts)  # the system text no longer claims ignorance
    assert any("needs counsel's review" in p or "sentence(s) pass" in p for p in llm.prompts)  # Vakeel's own decision notes from the log


def test_vakeel_texts_reach_the_model_as_untrusted_data():
    llm = Recording()
    env = vh.build(switches=s10(), abhiyojak_llm=llm)
    env.abhiyojak.spar(drafted(env))
    assert any("UNTRUSTED_DOCUMENT_DATA" in p and "vakeel note" in p for p in llm.prompts)


def test_the_baseline_one_call_list_stays_isolated():
    llm = Recording()
    env = vh.build(switches=s10(), abhiyojak_llm=llm)
    env.abhiyojak.list_objections_one_call(drafted(env))
    assert llm.prompts and not [p for p in llm.prompts if MARK in p or '"vakeel_view":' in p]


def test_events_are_labelled_and_default_runs_have_none():
    env = vh.build(switches=s10())
    vh.run_both(env)
    off = vh.events_of(env, "isolation_off", "ABHIYOJAK")
    assert off and all(e.outputs["variant"] == "S10" and e.outputs["abhiyojak_isolation"] is False for e in off)
    assert vh.events_of(env, "critic_signals", "ABHIYOJAK")
    base = vh.build()
    vh.run_both(base)
    assert not vh.events_of(base, "isolation_off") and not vh.events_of(base, "critic_signals")


def test_signals_are_in_the_state_and_the_agent_result():
    env = vh.build(switches=s10())
    after = env.vakeel.run(env.state)
    out = env.abhiyojak.run(after)
    sig = out.variant_signals["critic"]
    assert sig["variant"] == "S10" and sig["abhiyojak_isolation"] is False
    assert sig["objections"] == len(out.sparring.objections) > 0
    assert sig["judged"] == sig["verdict_answered"] + sig["verdict_partly"] + sig["verdict_unanswered"]
    assert sig["tokens"] > 0 and sig["notes_shown"] > 0 and 0 <= sig["conceded_share"] <= 1
    assert json.dumps(sig)


def test_offline_open_runs_are_deterministic():
    a = vh.digests(vh.canonical_run(vh.build(switches=s10())))
    b = vh.digests(vh.canonical_run(vh.build(switches=s10())))
    assert a == b
    open_run, base_run = vh.run_both(vh.build(switches=s10())), vh.run_both(vh.build())
    pick = lambda r: [(o.against, o.factor, o.objection) for o in r.record.objections]  # noqa: E731
    assert pick(open_run) == pick(base_run)  # the rule-based stand-in ignores what it reads: same objections


def test_a_spent_budget_stops_the_arm_without_a_call():
    llm = Recording()
    agent, _, _ = build_agent(AbhiyojakAgent, llm=llm, switches=s10(), budgets=SpyBudget(exhausted=True))
    env = vh.build(switches=s10())
    out = agent.spar(env.vakeel.run(env.state))
    assert llm.prompts == [] and out.objections == []


def test_the_switch_cannot_combine_with_no_sparring():
    with pytest.raises(ValueError):
        Switches(abhiyojak_isolation=False, no_sparring=True)
