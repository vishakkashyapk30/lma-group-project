"""S9 / A8b sampling-only critic at equal tokens (`Switches.critic_mode='sampling'`; Sweep 2, `docs/literature-to-code-map.md`).

The arm lives in `eval/ablations/a8b_sampling_critic.py`; the agents are untouched and `eval.runners.driver.run_agents` dispatches on the switch.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.fakes.data import build_world
from tests.fakes.models import ScriptedLLM
from tests.fakes.toolbox import FakeToolbox
from tests.integration import _helpers as h
from tests.unit.agents.vakeel import _variants_helpers as vh
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.eval.ablations import a8b_sampling_critic as a8b
from vakeel_sahayak.eval.runners.driver import build_context, run_agents
from vakeel_sahayak.eval.runners.systems import system_runner
from vakeel_sahayak.models.offline_llm import OfflineLLM
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import AgentName

FACTS = "The accused was arrested on 20.08.2024 under Section 318(4) BNS. Charge sheet filed 02.11.2024."


def s9() -> Switches:
    return Switches.for_variant("S9")


def critic_env(*, llm=None, **attrs):
    """Vakeel (offline) plus a SamplingCritic sharing its log and budget; attributes (k, token_budget, merge) are set on the critic."""
    env = vh.build(switches=s9(), abhiyojak_llm=llm)
    critic, _, _ = h.build_agent(a8b.SamplingCritic, llm=env.abhiyojak_llm, toolbox=env.toolbox, world=env.world, log=env.log, budgets=env.budgets, switches=s9())
    critic.replier = env.vakeel.reply_to_objections
    for k, v in attrs.items():
        setattr(critic, k, v)
    env.critic = critic
    env.after = env.vakeel.run(env.state)
    return env


def sample_calls(llm) -> int:
    return len(llm.of_task(a8b.TASK_SAMPLE))


# ---- selection and wiring ----------------------------------------------------------------------------------------------
def test_selection_and_implemented():
    assert s9().critic_mode == "sampling" and s9().variant() == "S9"
    assert Switches.for_variant("A8b").variant() == "S9"
    assert "S9" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("A8b")
    assert system_runner("S9")[1].variant() == "S9"


def test_the_arm_cannot_combine_with_no_isolation_or_no_sparring():
    with pytest.raises(ValueError):
        Switches(critic_mode="sampling", abhiyojak_isolation=False)
    with pytest.raises(ValueError):
        Switches(critic_mode="sampling", no_sparring=True)


def test_the_same_drafting_model_and_an_untouched_agent():
    assert a8b.SamplingCritic.ROLE_MODEL == VakeelAgent.ROLE_MODEL == AbhiyojakAgent.ROLE_MODEL
    for name in ("judge_replies", "spar", "run", "_judge_one", "_replies"):
        assert getattr(a8b.SamplingCritic, name) is getattr(AbhiyojakAgent, name), name
    assert a8b.SamplingCritic.raise_objections is not AbhiyojakAgent.raise_objections


def test_install_refuses_without_the_switch():
    env = vh.build()
    with pytest.raises(ValueError):
        a8b.install(SimpleNamespace(_peers={}), env.actx)


def test_the_default_driver_run_is_unchanged_and_has_no_variant_signals():
    world = build_world()
    case = {"case_id": "case-0007", "facts": FACTS, "before": world.case_date}
    ctx = build_context(case, tools=FakeToolbox(world).tools, llm=OfflineLLM(role="agents_14b", where="ada"))
    res = run_agents(case, ctx)
    assert "variant_signals" not in res and res["errors"] == []


# ---- sampling ------------------------------------------------------------------------------------------------------------
def test_k_independent_samples_at_a_non_zero_temperature():
    llm = vh.RecordingLLM()
    env = critic_env(llm=llm, k=4)
    objections = env.critic.raise_objections(env.after)
    calls = llm.of_task(a8b.TASK_SAMPLE)
    assert len(calls) == 4 and {t for _, t in calls} == {a8b.SAMPLE_TEMPERATURE}
    assert len({p for p, _ in calls}) == 4  # each sample has its own prompt (its index)
    assert objections and [o.id for o in objections] == [f"O{i}" for i in range(1, len(objections) + 1)]


def test_no_store_is_searched_and_the_isolation_holds():
    llm = vh.RecordingLLM()
    env = critic_env(llm=llm, k=2)
    after = env.after.model_copy(update={"vakeel_notes": "VAKEEL_PRIVATE_NOTE"})
    before = {n: env.toolbox.count(n) for n in ("search_objections", "search_reasoning", "get_statute")}
    env.critic.raise_objections(after)
    assert {n: env.toolbox.count(n) for n in before} == before
    assert not [p for p, _ in llm.seen if "VAKEEL_PRIVATE_NOTE" in p]


def test_offline_samples_are_deterministic_and_differ_from_each_other():
    a = critic_env(k=3)
    b = critic_env(k=3)
    oa, ob = a.critic.raise_objections(a.after), b.critic.raise_objections(b.after)
    assert [(o.against, o.factor, o.objection) for o in oa] == [(o.against, o.factor, o.objection) for o in ob]
    samples = [a8b.sample_offline(SimpleNamespace(case={"grounds": [{"id": "G1", "factor": "custody_period"}, {"id": "G2", "factor": "charge_sheet_filed"}], "general_factors": list(a8b.GENERAL_FACTORS), "facts": [], "sample": i})) for i in range(3)]
    assert len({json.dumps(s) for s in samples}) == 3


# ---- merging by agreement ------------------------------------------------------------------------------------------------
def test_union_keeps_every_cluster_and_majority_keeps_the_agreed_ones():
    union = critic_env(k=5, merge="union")
    ou = union.critic.raise_objections(union.after)
    major = critic_env(k=5, merge="majority")
    om = major.critic.raise_objections(major.after)
    keyed = lambda os: {(o.against, o.factor) for o in os}  # noqa: E731
    assert keyed(om) <= keyed(ou) and len(om) < len(ou)
    events = vh.events_of(union, "objection", "ABHIYOJAK")
    assert events and all(0 < e.outputs["agreement"] <= 1 and e.outputs["samples"] == 5 and e.outputs["variant"] == "S9" for e in events)
    for e in vh.events_of(major, "objection", "ABHIYOJAK"):
        assert e.outputs["votes"] >= 3  # at least half of 5 samples


def test_the_same_caps_as_abhiyojak_apply():
    """Two per ground, one per general factor, however many a sample raises."""
    many = {"objections": [{"against": "G1", "factor": f, "objection": f"Point {i} on parity.", "fact": None} for i, f in enumerate(["parity_with_co_accused"] * 4)]
            + [{"against": "general", "factor": "flight_risk", "objection": "Flight A."}, {"against": "general", "factor": "flight_risk", "objection": "Flight B."}]}
    llm = ScriptedLLM(by_prompt=[("abhiyojak.sample_objections", many)], strict=False, default="")
    env = critic_env(llm=llm, k=1)
    out = env.critic.raise_objections(env.after)
    assert sum(1 for o in out if o.against == "G1") <= 1  # clustered by (ground, factor): one cluster per pair, within the cap of two
    assert sum(1 for o in out if o.factor == "flight_risk") == 1


def test_a_hosted_style_model_answering_a_bare_list_is_read_and_predictions_are_dropped():
    bare = [
        {"against": "G1", "factor": "parity_with_co_accused", "objection": "The roles differ.", "fact": "co_accused_bail"},
        {"against": "G2", "factor": "charge_sheet_filed", "objection": "The accused is likely to be granted bail anyway.", "fact": None},
    ]
    llm = ScriptedLLM(by_prompt=[("abhiyojak.sample_objections", bare)], strict=False, default="")
    env = critic_env(llm=llm, k=1)
    out = env.critic.raise_objections(env.after)
    assert [(o.against, o.factor) for o in out] == [("G1", "parity_with_co_accused")]
    assert out[0].grounds[0].fact == "co_accused_bail"
    assert any("predicts" in (e.outputs or {}).get("text", "") for e in env.log.events)


# ---- equal tokens ----------------------------------------------------------------------------------------------------------
def one_sample_cost() -> int:
    llm = vh.RecordingLLM()
    env = critic_env(llm=llm, k=1)
    env.critic.raise_objections(env.after)
    return env.critic.critic_signals()["tokens_by_task"][a8b.TASK_SAMPLE]


def test_the_token_budget_is_respected_and_more_budget_gives_more_samples():
    cost = one_sample_cost()
    spent = {}
    for mult in (1.5, 3.5, 10):
        env = critic_env(k=9, token_budget=int(cost * mult))
        env.critic.raise_objections(env.after)
        sig = env.critic.critic_signals()
        assert sig["spent_round_1"] <= int(cost * mult)
        spent[mult] = sig["samples"]
    assert spent[1.5] < spent[3.5] < spent[10] <= 9 and spent[1.5] >= 1


def test_a_budget_too_small_for_one_sample_draws_none():
    env = critic_env(k=3, token_budget=10)
    assert env.critic.raise_objections(env.after) == []
    assert vh.events_of(env, "sampling_stopped", "ABHIYOJAK")


def test_the_budget_is_charged_to_the_case_budget():
    env = critic_env(k=2)
    before = env.budgets.snapshot().tokens_spent
    env.critic.raise_objections(env.after)
    assert env.budgets.snapshot().tokens_spent - before == env.critic.critic_signals()["tokens_by_task"][a8b.TASK_SAMPLE]


def test_equal_tokens_against_a_full_run():
    """The reference is the round-1 spend of Abhiyojak in the paired Full run; the sampling arm never spends more in round 1."""
    full = vh.build()
    vh.run_both(full)
    ref = a8b.reference_tokens(full.log.events)
    assert ref > 0
    assert a8b.reference_tokens([e for e in full.log.events if e.actor != AgentName.ABHIYOJAK]) == 0
    env = critic_env(k=50, token_budget=ref)
    env.critic.raise_objections(env.after)
    sig = env.critic.critic_signals()
    assert 1 <= sig["samples"] < 50 and sig["spent_round_1"] <= ref and sig["equal_tokens"] is True


def test_without_a_reference_budget_the_run_says_it_is_not_an_equal_token_run():
    env = critic_env(k=2)
    env.critic.raise_objections(env.after)
    assert vh.events_of(env, "budget_unspecified", "ABHIYOJAK")
    assert env.critic.critic_signals()["equal_tokens"] is False


# ---- signals and the whole exchange -----------------------------------------------------------------------------------------
def test_signals_events_and_the_state():
    env = critic_env(k=3)
    out = env.critic.run(env.after)
    sig = out.variant_signals["critic"]
    assert sig["variant"] == "S9" and sig["samples"] == 3 and sig["kept"] == sig["objections"] == len(out.sparring.objections) > 0
    assert sig["judged"] == len(out.sparring.objections) and sig["tokens"] > 0 and sig["agreement_rate"] is not None
    assert json.dumps(sig)
    assert vh.events_of(env, "sampling_critic", "ABHIYOJAK") and vh.events_of(env, "critic_signals", "ABHIYOJAK")


def test_replies_and_verdicts_follow_through_sparring():
    env = critic_env(k=3)
    rec = env.critic.spar(env.after)
    assert rec.rounds == 2 and rec.objections and all(o.reply is not None and o.verdict is not None for o in rec.objections)


# ---- the driver dispatches on critic_mode ---------------------------------------------------------------------------------------
def drive(switches, **case_extra):
    world = build_world()
    case = {"case_id": "case-0007", "facts": FACTS, "before": world.case_date, **case_extra}
    ctx = build_context(case, switches, tools=FakeToolbox(world).tools, llm=OfflineLLM(role="agents_14b", where="ada"))
    return run_agents(case, ctx)


def test_the_driver_runs_the_sampling_critic_for_s9():
    res = drive(s9())
    assert res["errors"] == []
    assert len(res["sparring"]["objections"]) > 0
    sig = res["variant_signals"]["critic"]
    assert sig["variant"] == "S9" and sig["equal_tokens"] is False


def test_the_driver_passes_the_equal_token_budget_from_the_case_row():
    res = drive(s9(), sparring_tokens=1)
    assert res["variant_signals"]["critic"]["equal_tokens"] is True
    assert res["variant_signals"]["critic"]["samples"] == 0 and res["sparring"]["objections"] == []


def test_full_and_s9_differ_only_where_the_critic_differs():
    full, arm = drive(Switches()), drive(s9())
    assert len(full["brief"]["grounds"]) == len(arm["brief"]["grounds"])
    assert "variant_signals" not in full
