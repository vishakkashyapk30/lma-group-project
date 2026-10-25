"""S12 / S12b topology: `Switches.topology='sequential'` and `'single_agent'` (evaluation plan 3.3).

Papers: Plan-and-Act (ICML 2025), Towards a Science of Scaling Agent Systems (arXiv 2025), Why Do Multi-Agent LLM Systems Fail? (NeurIPS 2025 D&B).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar.contracts_runtime import contract_for
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S12, S12B = Switches.for_variant("S12"), Switches.for_variant("S12b")


def events(env, tool):
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


def evidence(out):
    return {p.factor.value: {s.slot: s.status.value for s in p.slots} for p in out.evidence_packs}


def test_switches():
    assert S12.topology == "sequential" and S12.variant() == "S12" and S12B.topology == "single_agent" and S12B.variant() == "S12b"
    assert {"S12", "S12b"} <= Switches.implemented_variants()
    with pytest.raises(ValueError):
        Switches(topology="sequential", fixed_router=True)
    with pytest.raises(ValueError):
        Switches(topology="single_agent", stopping="llm")


@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_default_run_is_still_byte_identical(world):
    env = build(world=h.case_0007_world(second_parity=world.endswith("parity")))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert not events(env, "topology") and env.agent.retrieval_signals == {}


@pytest.mark.parametrize("sw", [S12, S12B], ids=["sequential", "single_agent"])
def test_same_factors_and_schema_valid_packs_as_orchestrated(sw):
    base = build()
    base_out = base.agent.run(base.state)
    env = build(switches=sw)
    out = env.agent.run(env.state)
    assert [p.factor for p in out.evidence_packs] == [p.factor for p in base_out.evidence_packs]
    for p in out.evidence_packs:  # each topology yields the contract's slots, so the same stores are used
        assert {s.slot for s in p.slots} == {s.slot for s in next(b for b in base_out.evidence_packs if b.factor == p.factor).slots}
    assert evidence(out)  # packs exist and validate (pydantic) by construction


@pytest.mark.parametrize("sw", [S12, S12B], ids=["sequential", "single_agent"])
def test_signals_are_events_and_in_the_agent_result_and_context_grows(sw):
    env = build(switches=sw)
    env.agent.run(env.state)
    sigs = [s["topology"] for s in env.agent.retrieval_signals.values()]
    assert sigs and all(s["mode"] == sw.topology for s in sigs)
    assert [s["position"] for s in sorted(sigs, key=lambda s: s["position"])] == list(range(len(sigs)))
    chars = [s["context_chars_out"] for s in sorted(sigs, key=lambda s: s["position"])]
    assert chars == sorted(chars) and chars[-1] > chars[0] and sorted(sigs, key=lambda s: s["position"])[0]["context_chars_in"] == 0
    assert len(events(env, "topology")) == len(sigs)


def test_sequential_passes_the_history_to_the_planner_prompt():
    seen = []
    env = build(switches=S12)
    original = env.agent.ask

    def spy(task, user, *, case=None, **kw):
        seen.append(case)
        return original(task, user, case=case, **kw)

    env.agent.ask = spy
    env.agent.run(env.state)
    plan_cases = [c for c in seen if c and "slots" in c]
    assert plan_cases and "history" not in plan_cases[0] and any(c.get("history") for c in plan_cases[1:])


def test_single_agent_makes_no_planning_call_and_pools_the_budget():
    orch = build()
    orch.agent.run(orch.state)
    env = build(switches=S12B)
    out = env.agent.run(env.state)
    assert env.budgets.spent(None)[0] < orch.budgets.spent(None)[0]  # no planning prompts: fewer tokens
    total = sum(contract_for(p.factor).budget.store_calls for p in out.evidence_packs)
    used = sum(env.budgets.spent(p.factor.value)[1] for p in out.evidence_packs)
    assert used <= total  # one pooled budget never exceeds the sum of the contracts' budgets


@pytest.mark.parametrize("sw", [S12, S12B], ids=["sequential", "single_agent"])
def test_deterministic(sw):
    digests = []
    for _ in range(2):
        env = build(switches=sw)
        digests.append(digest(canonical_run(env)))
    assert digests[0] == digests[1]
