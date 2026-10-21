"""S2 adaptive retrieval depth: `Switches.retrieval_policy='adaptive'` (Adaptive-RAG, NAACL 2024; evaluation plan 3.3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar import depth
from vakeel_sahayak.agents.sutradhar.contracts_runtime import contract_for
from vakeel_sahayak.agents.sutradhar.factor_pick import CaseSignals
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind, Factor, FactorStance, SlotStatus

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S2 = Switches.for_variant("S2")
FAV, ADV = FactorStance.FAVOURABLE, FactorStance.ADVERSE


def sig(codes=("IPC",), rights=None) -> CaseSignals:
    return CaseSignals(sections=[{"ref": f"{c} 1", "code": c} for c in codes], rights=rights or {})


def decisions(env, tool: str) -> list[dict]:
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


# ---- switches --------------------------------------------------------------------------------------------------
def test_switch_and_variant_name():
    assert Switches.for_variant("s2").retrieval_policy == "adaptive" and S2.variant() == "S2" and "S2" in Switches.implemented_variants()
    with pytest.raises(ValueError):
        Switches(retrieval_policy="adaptive", fixed_router=True)
    with pytest.raises(ValueError):
        Switches(retrieval_policy="sometimes")


# ---- the complexity rules on constructed signals ---------------------------------------------------------------
def test_single_for_a_favourable_one_paragraph_factor_outside_the_bns_era():
    d = depth.classify(Factor.WEAK_PRIMA_FACIE, contract_for(Factor.WEAK_PRIMA_FACIE), FAV, sig())
    assert (d.level, d.max_rounds, d.store_calls, d.skip_corpus) == ("single", 1, 4, False)


@pytest.mark.parametrize(
    ("factor", "stance", "codes", "reason"),
    [
        (Factor.WEAK_PRIMA_FACIE, FAV, ("BNS",), "BNS-era"),
        (Factor.WEAK_PRIMA_FACIE, ADV, ("IPC",), "adverse"),
        (Factor.PARITY_WITH_CO_ACCUSED, FAV, ("IPC",), "citation check"),
        (Factor.CUSTODY_PERIOD, FAV, ("IPC",), "needs 2 paragraphs"),
        (Factor.TRIAL_DELAY, FAV, ("IPC",), "citation check"),
    ],
)
def test_multi_when_a_complexity_feature_holds(factor, stance, codes, reason):
    d = depth.classify(factor, contract_for(factor), stance, sig(codes))
    assert d.level == "multi" and (d.max_rounds, d.store_calls) == (None, None) and any(reason in r for r in d.reasons)


def test_none_when_a_statute_decides_on_its_face():
    ut = Factor.UNDERTRIAL_PERIOD
    d = depth.classify(ut, contract_for(ut), FAV, sig(rights={"undertrial_limit": ("ELIGIBLE", "")}))
    assert d.level == "none" and d.skip_corpus and d.max_rounds == 1 and d.store_calls == 4
    assert depth.classify(ut, contract_for(ut), FAV, sig(rights={"undertrial_limit": ("NOT_YET", "")})).level == "single"


def test_classification_is_deterministic_and_total():
    for f in Factor:
        a, b = (depth.classify(f, contract_for(f), FAV, sig()) for _ in range(2))
        assert a == b and a.level in depth.LEVELS and a.reasons


# ---- default-off equivalence -----------------------------------------------------------------------------------
@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_default_run_is_still_byte_identical(world):
    env = build(world=h.case_0007_world(second_parity=world.endswith("parity")))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert env.agent.retrieval_signals == {} and not decisions(env, "depth")


# ---- behaviour on case-0007 ------------------------------------------------------------------------------------
def test_case_0007_is_bns_era_so_every_factor_is_multi_and_the_loop_is_unchanged():
    env = build(switches=S2)
    out = env.agent.run(env.state)
    assert {s["depth"]["level"] for s in out.retrieval_signals.values()} == {"multi"}
    base = build()
    plain = base.agent.run(base.state)
    assert digest([p.model_dump(mode="json") for p in out.evidence_packs]) == digest([p.model_dump(mode="json") for p in plain.evidence_packs])


def test_run_is_deterministic():
    runs = [canonical_run(build(switches=S2)) for _ in range(2)]
    assert digest(runs[0]["packs"]) == digest(runs[1]["packs"]) and digest(runs[0]["plans"]) == digest(runs[1]["plans"])


def test_signals_are_events_and_state_fields():
    env = build(switches=S2)
    out = env.agent.run(env.state)
    emitted = {d["factor"]: d for d in decisions(env, "depth")}
    assert set(emitted) == set(out.retrieval_signals) and emitted
    for s in out.retrieval_signals.values():
        d = s["depth"]
        assert {"level", "max_rounds", "store_calls_cap", "reasons", "features", "rounds", "store_calls", "skipped_slots"} <= set(d)
    assert {d["factor"] for d in decisions(env, "retrieval_signals")} == set(out.retrieval_signals)


@pytest.fixture
def pre_bns(monkeypatch):
    """The same case read as an IPC-era case: the BNS-era feature no longer pushes factors to the full loop."""
    monkeypatch.setattr(depth, "BNS_CODES", set())


def test_single_factors_run_one_round_with_a_capped_budget(pre_bns):
    env = build(switches=S2)
    out = env.agent.run(env.state)
    singles = {f for f, s in out.retrieval_signals.items() if s["depth"]["level"] == "single"}
    assert "weak_prima_facie" in singles
    for f in singles:
        s = out.retrieval_signals[f]["depth"]
        assert s["rounds"] == 1 and s["store_calls"] <= 4 and s["store_calls_cap"] == 4
        assert [p.round for p in out.plans if p.factor.value == f] == [1]
        assert s["stopped"] in {"filled", "depth_cap", "budget"}


def test_adaptive_depth_spends_fewer_store_calls_than_the_full_loop(pre_bns):
    full, adaptive = build(), build(switches=S2)
    full.agent.run(full.state)
    adaptive.agent.run(adaptive.state)
    a, b = full.budgets.snapshot().store_calls, adaptive.budgets.snapshot().store_calls
    assert sum(b.values()) < sum(a.values()) and all(b[f] <= a[f] for f in b)


def test_none_factor_skips_corpus_slots_without_open_issues():
    env = build(switches=S2)
    env.agent.pick_factors(env.state)
    ut = Factor.UNDERTRIAL_PERIOD
    env.agent._pctx.sig.rights["undertrial_limit"] = ("ELIGIBLE", "")
    work = env.agent._new_work(ut, env.agent._pctx)
    assert work.depth.level == "none" and work.round_cap == 1
    sw = work.slots["authority"]
    assert sw.skipped and not sw.required and sw.result.status == SlotStatus.MISSING and "not retrieved" in sw.result.note
    assert not work.slots["statute_text"].skipped
    assert env.budgets.limits(ut)[0] == 4


def test_none_factor_run_makes_no_corpus_call():
    env = build(switches=S2)
    env.agent.pick_factors(env.state)
    ut = Factor.UNDERTRIAL_PERIOD
    env.agent._pctx.sig.rights["undertrial_limit"] = ("ELIGIBLE", "")
    plan = env.agent.plan_factor(ut, env.state)
    assert plan.steps and all(s.tool not in ("search_reasoning", "citations", "search_objections", "similar_orders") for s in plan.steps)
    pack = env.agent._drive({ut: plan})[ut]
    assert next(s for s in pack.slots if s.slot == "authority").status == SlotStatus.MISSING
    assert all("authority" not in i.lower() for i in pack.open_issues)
    assert env.agent._work[ut].stopped in {"filled", "depth_cap"}


def test_a_failed_claim_is_re_retrieved_at_full_depth(pre_bns):
    env = build(switches=S2)
    env.agent.retrieve(env.state, [Factor.WEAK_PRIMA_FACIE])
    work = env.agent._new_work(Factor.WEAK_PRIMA_FACIE, env.agent._context_for(env.state), adaptive=False)
    assert work.depth is None and work.round_cap is None


# ---- budgets ---------------------------------------------------------------------------------------------------
def test_budgets_are_respected(pre_bns):
    env = build(switches=S2, budgets=BudgetTracker(tokens_per_case=20000))
    env.agent.run(env.state)
    snap = env.budgets.snapshot()
    assert all(v <= 8 for v in snap.store_calls.values()) and snap.tokens_spent <= snap.tokens_cap + 500


def test_caps_never_raise_a_contract_budget():
    env = build(switches=S2)
    env.agent.pick_factors(env.state)
    work = env.agent._new_work(Factor.WEAK_PRIMA_FACIE, env.agent._pctx)
    assert env.budgets.limits(Factor.WEAK_PRIMA_FACIE)[0] <= contract_for(Factor.WEAK_PRIMA_FACIE).budget.store_calls and work.depth is not None
