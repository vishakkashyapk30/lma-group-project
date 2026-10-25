"""S6 / B5 learned store prior: `Switches.store_prior='order'` (S6, A12) and `'only'` (B5, S6b); evaluation plan 3.3.

Papers: AgentRouter (ACL 2026), GraphRouter (ICLR 2025), RouteLLM (ICLR 2025). Trained here on synthetic outcome rows only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.agents.sutradhar.contracts_runtime import contract_for
from vakeel_sahayak.agents.sutradhar.store_prior import (
    Outcome,
    PriorContext,
    StorePrior,
    StorePriorUnavailable,
    era_of,
    outcomes_from_orders,
    train_from_file,
)
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import EventKind, Factor, StoreName

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S6, B5 = Switches.for_variant("S6"), Switches.for_variant("B5")
R, SIM = "caselaw.reasoning", "caselaw.similar"


def rows(factor="parity_with_co_ignored", useful=(), useless=()):
    return [Outcome(factor, s, True) for s in useful for _ in range(20)] + [Outcome(factor, s, False) for s in useless for _ in range(20)]


def reversed_prior() -> StorePrior:
    """A prior that prefers similar-orders over reasoning for every factor."""
    data = []
    for f in Factor:
        data += rows(f.value, useful=[SIM, "advocacy.objections", "case.docs"], useless=[R])
    return StorePrior.train(data)


def decisions(env, tool):
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


# ---- switches ------------------------------------------------------------------------------------------------
def test_switches_and_aliases():
    assert S6.store_prior == "order" and S6.variant() == "S6" and Switches.for_variant("a12") == S6
    assert B5.store_prior == "only" and B5.variant() == "B5" and Switches.for_variant("s6b") == B5
    assert {"S6", "B5"} <= Switches.implemented_variants()
    assert Switches(store_prior="only", free_planner=True).store_prior == "only"
    with pytest.raises(ValueError):
        Switches(store_prior="only", stopping="llm")


# ---- the model -------------------------------------------------------------------------------------------------
def test_counts_rank_and_back_off():
    prior = StorePrior.train(rows("custody_period", useful=[R], useless=["case.docs"]))
    ctx = PriorContext("custody_period")
    assert prior.p(ctx, R) > 0.9 > 0.1 > prior.p(ctx, "case.docs")
    assert prior.rank(ctx, ["case.docs", R]).order == [R, "case.docs"]
    other = PriorContext("trial_delay", family="theft", era="bns", court="X")  # unseen: backs off to the store level, still ordered by it
    assert prior.p(other, R) > prior.p(other, "case.docs")


def test_context_specific_counts_beat_the_parent():
    data = [Outcome("custody_period", R, True, "cheating", "bns") for _ in range(30)] + [Outcome("custody_period", R, False, "theft", "ipc") for _ in range(30)]
    prior = StorePrior.train(data)
    assert prior.p(PriorContext("custody_period", "cheating", "bns"), R) > prior.p(PriorContext("custody_period", "theft", "ipc"), R)


def test_neutral_prior_keeps_the_given_order_and_prune_defers_without_removing():
    assert StorePrior.neutral().rank(PriorContext("x"), ["b", "a", "c"]).order == ["b", "a", "c"] and not StorePrior.neutral().trained
    prior = StorePrior.train(rows("f", useful=["a"], useless=["b", "c"]), prune_below=0.3)
    r = prior.rank(PriorContext("f"), ["b", "a", "c"])
    assert r.order[0] == "a" and sorted(r.order) == ["a", "b", "c"] and set(r.deferred) == {"b", "c"}
    only_weak = StorePrior.train(rows("f", useless=["a", "b"]), prune_below=0.9).rank(PriorContext("f"), ["a", "b"])
    assert len(only_weak.order) == 2 and len(only_weak.deferred) == 1  # the best candidate is never deferred


def test_training_is_deterministic_and_artefact_round_trips(tmp_path):
    data = rows("f", useful=["a"], useless=["b"])
    a, b = StorePrior.train(data), StorePrior.train(list(data))
    pa, pb = tmp_path / "a.json", tmp_path / "b.json"
    assert a.save(pa) == b.save(pb) and pa.read_bytes() == pb.read_bytes()
    assert StorePrior.load(pa).p(PriorContext("f"), "a") == a.p(PriorContext("f"), "a")
    assert not StorePrior.load(tmp_path / "missing.json").trained
    with pytest.raises(StorePriorUnavailable):
        StorePrior.train([])


# ---- labels come from TRAIN orders' own text ---------------------------------------------------------------
def order(split, date="2022-05-01", cited=True, parts=True):
    g2 = {"labels": ["d1"] if cited else [], "raw": [], "unresolved": []}
    return {"doc_id": "o", "court": "Kerala High Court", "date": date, "split": split, "bns_era": False, "facts_text": "facts",
            "parts": {"prosecution": "State opposes", "defense": "Counsel argues"} if parts else {},
            "gold": {"G1": {"labels": ["custody_period"]}, "G2": g2, "G3": {"fields": {"sections": ["IPC 420"]}, "events": [{"date": date}]}}}


def test_only_train_orders_make_rows_and_unknown_is_skipped():
    rows_, stats = outcomes_from_orders([order("train"), order("dev"), order("test"), order("blind"), order(None, date="2024-06-01"), order(None)])
    assert stats["used"] == 2 and stats["refused"] == 4 and {r.factor for r in rows_} == {"custody_period"}
    by_store = {r.store: r.useful for r in rows_[: stats["rows"] // 2]}
    assert by_store[R] is True and by_store["advocacy.objections"] is True and by_store["law.statutes"] is True
    none_cited = [r for r in outcomes_from_orders([order("train", cited=False)])[0] if r.store == R]
    assert none_cited and not none_cited[0].useful
    unresolved = order("train", cited=False)
    unresolved["gold"]["G2"]["unresolved"] = ["x"]
    assert not [r for r in outcomes_from_orders([unresolved])[0] if r.store == R]  # unresolved citations say nothing (only 17% resolve)
    no_parts = [r for r in outcomes_from_orders([order("train", parts=False)])[0] if r.store == "advocacy.objections"]
    assert not no_parts


def test_trainer_script_writes_an_artefact(tmp_path):
    src = tmp_path / "orders.jsonl"
    src.write_text("\n".join(json.dumps(o) for o in [order("train"), order("test")]), encoding="utf-8")
    a = train_from_file(src, tmp_path / "p.json")
    b = train_from_file(src, tmp_path / "q.json")
    assert a["refused"] == 1 and a["digest"] == b["digest"] and (tmp_path / "p.json").read_bytes() == (tmp_path / "q.json").read_bytes()


def test_era():
    assert era_of({"BNS"}) == "bns" and era_of({"IPC", "CRPC"}) == "ipc" and era_of({"BNS", "IPC"}) == "mixed" and era_of(set()) == "unknown"


# ---- default off -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_default_run_is_still_byte_identical(world):
    env = build(world=h.case_0007_world(second_parity=world.endswith("parity")))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert not decisions(env, "store_prior") and env.agent.retrieval_signals == {}


# ---- S6: order -------------------------------------------------------------------------------------------------
def test_neutral_prior_in_order_mode_keeps_the_contract_order():
    env = build(switches=S6)
    out = env.agent.run(env.state)
    base = build()
    base_out = base.agent.run(base.state)
    assert [p.model_dump(mode="json") for p in out.evidence_packs] == [p.model_dump(mode="json") for p in base_out.evidence_packs]
    sig = next(iter(env.agent.retrieval_signals.values()))["store_prior"]
    assert sig["trained"] is False and sig["calls_saved"] == 0 and sig["regret"] == 0


def test_a_trained_prior_reorders_a_multi_store_slot_and_never_drops_a_store():
    env = build(switches=S6)
    env.agent.set_store_prior(reversed_prior())
    env.agent.run(env.state)
    traces = {f: w.prior_trace for f, w in env.agent._work.items()}
    changed = [(f, n, t) for f, tr in traces.items() for n, t in tr.items() if t["prior"] != t["contract"]]
    assert changed, "the reversed prior must change at least one slot's order"
    for _, name, t in changed:
        assert sorted(t["prior"]) == sorted(t["contract"])  # no allowed store removed
    for f, w in env.agent._work.items():
        for name, sw in w.slots.items():
            allowed = {StoreName(s).value for s in contract_for(f).slots[name].stores}
            assert {str(getattr(s, "value", s)) for s in sw.sources if isinstance(s, StoreName)} == allowed


def test_signals_are_events_and_in_the_agent_result():
    env = build(switches=S6)
    env.agent.set_store_prior(reversed_prior())
    env.agent.run(env.state)
    assert env.agent.retrieval_signals
    for f, sig in env.agent.retrieval_signals.items():
        sp = sig["store_prior"]
        assert sp["mode"] == "order" and sp["trained"] and {"stores_queried", "calls_saved", "slot_fill_rate", "regret"} <= set(sp)
        assert sp["regret"] >= 0 and 0 <= sp["slot_fill_rate"] <= 1
    assert decisions(env, "retrieval_signals")


def test_order_mode_is_deterministic():
    runs = []
    for _ in range(2):
        env = build(switches=S6)
        env.agent.set_store_prior(reversed_prior())
        runs.append(digest(canonical_run(env)))
    assert runs[0] == runs[1]


def test_order_mode_respects_the_store_call_budget():
    env = build(switches=S6, budgets=BudgetTracker())
    env.agent.set_store_prior(reversed_prior())
    env.agent.run(env.state)
    for f in env.agent._work:
        _, calls = env.budgets.spent(f.value)
        assert calls <= contract_for(f).budget.store_calls


# ---- B5: the prior alone ------------------------------------------------------------------------------------
def test_prior_only_queries_top_k_stores_with_no_contract():
    env = build(switches=B5)
    env.agent.set_store_prior(reversed_prior())
    out = env.agent.run(env.state)
    assert out.evidence_packs
    for pack in out.evidence_packs:
        assert 1 <= len(pack.slots) <= 3 and all("B5" in s.note for s in pack.slots)
        sig = env.agent.retrieval_signals[pack.factor.value]["store_prior"]
        assert sig["mode"] == "only" and sig["store_calls"] == len(sig["stores_queried"]) <= 3
        assert sig["calls_saved"] == len(set(StoreName(s).value for s in __import__("vakeel_sahayak.contracts.loader", fromlist=["x"]).ALLOWED_STORES[pack.factor])) - sig["store_calls"]
    assert decisions(env, "store_prior")


def test_prior_only_honours_a_knockout_and_is_deterministic():
    sw = Switches.for_variant("B5", knockout_store=SIM)
    env = build(switches=sw)
    env.agent.set_store_prior(reversed_prior())
    env.agent.run(env.state)
    assert all(SIM not in s["store_prior"]["stores_queried"] for s in env.agent.retrieval_signals.values())
    digests = []
    for _ in range(2):
        e = build(switches=B5)
        e.agent.set_store_prior(reversed_prior())
        out = e.agent.run(e.state)
        digests.append(digest([p.model_dump(mode="json") for p in out.evidence_packs]))
    assert digests[0] == digests[1]
