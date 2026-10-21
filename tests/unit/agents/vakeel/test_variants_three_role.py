"""S11 (a) / A8d three-role review (`Switches.critic_mode='three_role'`; Sweep 2, `docs/literature-to-code-map.md`).

Grader, Critic, Defender, Grader as prompts of the one drafting model, in `eval/ablations/a8d_three_role.py`; the agents are untouched
and `eval.runners.driver.run_agents` dispatches on the switch.
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
from vakeel_sahayak.eval.ablations import a8d_three_role as a8d
from vakeel_sahayak.eval.runners.driver import build_context, run_agents
from vakeel_sahayak.eval.runners.systems import system_runner
from vakeel_sahayak.models.offline_llm import OfflineLLM
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import AgentName

FACTS = "The accused was arrested on 20.08.2024 under Section 318(4) BNS. Charge sheet filed 02.11.2024."


def s11() -> Switches:
    return Switches.for_variant("S11")


def env_for(llm=None):
    env = vh.build(switches=s11(), abhiyojak_llm=llm)
    critic, _, _ = h.build_agent(a8d.ThreeRoleCritic, llm=env.abhiyojak_llm, toolbox=env.toolbox, world=env.world, log=env.log, budgets=env.budgets, switches=s11())
    critic.replier = env.vakeel.reply_to_objections
    env.critic = critic
    env.after = env.vakeel.run(env.state)
    return env


def test_selection_and_wiring():
    assert s11().critic_mode == "three_role" and s11().variant() == "S11"
    assert Switches.for_variant("A8d").variant() == "S11"
    assert "S11" in IMPLEMENTED_VARIANTS and "S11c" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("A8d")
    assert system_runner("S11")[1].variant() == "S11"
    with pytest.raises(ValueError):
        a8d.install(SimpleNamespace(_peers={}), vh.build().actx)
    for name in ("judge_replies", "spar", "run", "_judge_one"):
        assert getattr(a8d.ThreeRoleCritic, name) is getattr(AbhiyojakAgent, name)
    assert a8d.ThreeRoleCritic.ROLE_MODEL == AbhiyojakAgent.ROLE_MODEL


def test_the_four_roles_are_called_in_order_on_the_isolated_context():
    llm = vh.RecordingLLM()
    env = env_for(llm)
    after = env.after.model_copy(update={"vakeel_notes": "VAKEEL_PRIVATE_NOTE"})
    out = env.critic.raise_objections(after)
    order = [next(t for t in a8d.ROLE_TASKS if f"### TASK: {t}" in p) for p, _ in llm.seen]
    assert order == [a8d.TASK_GRADE, a8d.TASK_CRITIC, a8d.TASK_DEFEND, a8d.TASK_RULE]
    assert not [p for p, _ in llm.seen if "VAKEEL_PRIVATE_NOTE" in p]
    assert out and [o.id for o in out] == [f"O{i}" for i in range(1, len(out) + 1)]


def test_only_upheld_objections_are_returned_with_abhiyojaks_caps():
    scripted = {
        "abhiyojak.role_grade": {"grades": [{"ground": "G1", "score": 2, "weakness": "thin"}]},
        "abhiyojak.role_critic": {"objections": [
            {"against": "G1", "factor": "parity_with_co_accused", "objection": "Roles differ.", "fact": "co_accused_bail"},
            {"against": "general", "factor": "flight_risk", "objection": "May abscond.", "fact": None},
            {"against": "general", "factor": "witness_tampering", "objection": "May intimidate.", "fact": None},
            {"against": "G2", "factor": "charge_sheet_filed", "objection": "The accused will surely be granted bail.", "fact": None},
        ]},
        "abhiyojak.role_defend": {"defences": [{"objection": "C1", "defence": "Same role.", "holds": True}, {"objection": "C2", "defence": "None.", "holds": False}]},
        "abhiyojak.role_rule": {"rulings": [{"objection": "C1", "upheld": False, "reason": "met"}, {"objection": "C2", "upheld": True, "reason": "stands"}, {"objection": "C3", "upheld": True, "reason": "stands"}]},
    }
    llm = ScriptedLLM(by_prompt=[(f"### TASK: {k}", v) for k, v in scripted.items()], strict=False, default="")
    env = env_for(llm)
    out = env.critic.raise_objections(env.after)
    assert [(o.against, o.factor) for o in out] == [("general", "flight_risk"), ("general", "witness_tampering")]
    sig = env.critic.critic_signals()
    assert sig["critic_raised"] == 3 and sig["defended"] == 1 and sig["upheld"] == 2  # the prediction was dropped before the roles saw it
    assert any("predicts" in (e.outputs or {}).get("text", "") for e in env.log.events)


def test_signals_events_state_and_tokens():
    env = env_for()
    out = env.critic.run(env.after)
    sig = out.variant_signals["critic"]
    assert sig["variant"] == "S11" and sig["calls"] == 4 and sig["spent_round_1"] > 0 and sig["upheld"] == len(out.sparring.objections)
    assert json.dumps(sig)
    assert vh.events_of(env, "three_role", "ABHIYOJAK") and vh.events_of(env, "critic_signals", "ABHIYOJAK")
    assert all(e.outputs["variant"] == "S11" for e in vh.events_of(env, "objection", "ABHIYOJAK"))


def test_offline_runs_are_deterministic_and_replies_follow():
    a, b = env_for(), env_for()
    pick = lambda e: [(o.against, o.factor, o.objection) for o in e.critic.raise_objections(e.after)]  # noqa: E731
    assert pick(a) == pick(b)
    env = env_for()
    rec = env.critic.spar(env.after)
    assert rec.rounds == 2 and rec.objections and all(o.verdict is not None for o in rec.objections)


def test_a_spent_budget_gives_no_objections_and_no_crash():
    from tests.unit.agents._helpers import SpyBudget, build_agent

    env = env_for()
    critic, _, _ = build_agent(a8d.ThreeRoleCritic, llm=OfflineLLM(role="agents_14b", where="ada"), switches=s11(), budgets=SpyBudget(exhausted=True))
    assert critic.raise_objections(env.after) == []


def test_the_driver_runs_the_three_role_critic_for_s11():
    world = build_world()
    case = {"case_id": "case-0007", "facts": FACTS, "before": world.case_date}
    ctx = build_context(case, s11(), tools=FakeToolbox(world).tools, llm=OfflineLLM(role="agents_14b", where="ada"))
    res = run_agents(case, ctx)
    assert res["errors"] == [] and res["sparring"]["objections"]
    assert res["variant_signals"]["critic"]["variant"] == "S11" and res["variant_signals"]["critic"]["calls"] == 4
    assert AgentName.ABHIYOJAK  # the peer table carried the arm
