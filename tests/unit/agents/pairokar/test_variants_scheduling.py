"""S14b (first come first served) and S14c (urgency with a least-work tie-break) scheduling policies, plus the shortest-first baseline, through Pairokar's batch desk
(stub runners: six constructed files that arrive in a fixed order; stage 2 under a GPU budget that fits three full runs)."""

from __future__ import annotations

import pytest

from tests.unit.agents.pairokar import _variants_helpers as vh
from tests.unit.batch._helpers import hand_card
from vakeel_sahayak.batch.urgency import POLICIES, has_deadline, order_cards
from vakeel_sahayak.orchestration.switches import Switches

ARRIVAL = ["case-0001", "case-0002", "case-0003", "case-0004", "case-0005", "case-0006"]
DEADLINE = {"case-0003", "case-0005", "case-0006"}  # default-bail soon, default-bail open, s.479 crossed (case-0002 waits for a document)


def run(variant: str | None = None, **kw):
    env = vh.build(Switches.for_variant(variant) if variant else None, **kw)
    out = vh.canonical_run(env)
    return env, out


def test_variant_ids_and_values():
    assert Switches.for_variant("S14b").urgency_policy == "fifo" and Switches.for_variant("S14c").urgency_policy == "urgency_least_work"
    assert Switches(urgency_policy="shortest_first").urgency_policy == "shortest_first" and POLICIES == ("urgency", "fifo", "urgency_least_work", "shortest_first")
    assert {"S14", "S14b", "S14c", "S14d"} <= set(Switches.implemented_variants())


def test_urgency_serves_the_three_deadline_cases_first_and_misses_none():
    env, out = run()
    assert set(out["done"]) == DEADLINE and out["done"][0] == "case-0005"
    sig = env.agent.scheduler.signals(env.agent.queue)
    assert sig["policy"] == "urgency" and sig["missed_deadlines"] == 0 and sig["inversions"] == 0 and sig["deadline_cases"] == 3


def test_fifo_serves_in_arrival_order_and_misses_deadlines_under_the_same_budget():
    env, out = run("S14b")
    assert out["done"] == ["case-0001", "case-0003", "case-0004"]  # case-0002 asks for a document first and has no full run
    assert [c["case_id"] for c in out["cards"]] == ARRIVAL
    sig = env.agent.scheduler.signals(env.agent.queue)
    assert sig["policy"] == "fifo" and sig["deadline_cases"] == 3 and sig["missed_deadlines"] == 2 and sig["inversions"] >= 1


def test_fifo_does_not_demote_a_case_with_a_bar():
    from vakeel_sahayak.batch.scheduler import Scheduler

    sched = Scheduler(policy="fifo")
    cards = [hand_card("a", 1, flags=["CHECK: statutory bar applies"]), hand_card("b", 2)]
    assert [c.case_id for c in sched.reprioritise(cards)] == ["a", "b"]
    assert [c.case_id for c in Scheduler().reprioritise(cards)] == ["b", "a"]


def test_least_work_keeps_the_urgency_order_when_keys_differ():
    _, urgency = run()
    _, least = run("S14c")
    assert [c["case_id"] for c in least["cards"]] == [c["case_id"] for c in urgency["cards"]] and least["done"] == urgency["done"]


def test_least_work_breaks_a_tie_towards_the_case_with_less_work_done():
    cards = [hand_card("a", reasons=["In custody 100 days"]), hand_card("b", reasons=["In custody 100 days"]), hand_card("c", reasons=["In custody 100 days"])]
    assert [c.case_id for c in order_cards(cards, "urgency")] == ["a", "b", "c"]  # equal keys: by id
    got = order_cards(cards, "urgency_least_work", work={"a": 0.5, "b": 0.0, "c": 0.25})
    assert [c.case_id for c in got] == ["b", "c", "a"] and [c.urgency_rank for c in got] == [1, 2, 3]
    # work never overrides a legal deadline
    mixed = [hand_card("late", reasons=["Default-bail window open for 3 day(s) (BNSS s.187(3))"]), hand_card("idle", reasons=["In custody 100 days"])]
    assert order_cards(mixed, "urgency_least_work", work={"late": 9.0})[0].case_id == "late"


def test_shortest_first_orders_by_planned_size_then_urgency():
    cards = [hand_card("a", reasons=["In custody 100 days"]), hand_card("b", reasons=["In custody 300 days"]), hand_card("c", reasons=["In custody 200 days"])]
    assert [c.case_id for c in order_cards(cards, "shortest_first", sizes={"a": 3.0, "b": 1.0, "c": 1.0})] == ["b", "c", "a"]
    assert [c.case_id for c in order_cards(cards, "shortest_first")] == [c.case_id for c in order_cards(cards, "urgency")]  # equal sizes: urgency


def test_unknown_policy_is_refused_and_has_deadline_reads_the_card():
    with pytest.raises(ValueError):
        order_cards([hand_card("a")], "random")
    assert has_deadline(hand_card("a", reasons=["Default-bail window opens in 3 day(s) (BNSS s.187(3))"])) and not has_deadline(hand_card("b"))


def test_stage_2_stays_within_the_budget_in_every_policy():
    for variant in (None, "S14b", "S14c"):
        _, out = run(variant)
        assert len(out["done"]) <= 3  # 0.75 GPU-hours at 0.25 per case


def test_batch_signals_are_in_the_stage_2_message_only_for_a_serving_variant():
    for variant in ("S14b", "S14c", "S14d", "S14"):
        env, _ = run(variant)
        msgs = [e.outputs for e in env.log.events if "batch_signals" in (e.outputs or {})]
        assert len(msgs) == 1 and "scheduling" in msgs[0]["batch_signals"] and "retrieval_cache" in msgs[0]["batch_signals"]
    env, _ = run()
    assert not [e for e in env.log.events if "batch_signals" in (e.outputs or {})]


def test_runs_are_deterministic_in_every_policy():
    for variant in ("S14b", "S14c"):
        assert vh.digests(run(variant)[1]) == vh.digests(run(variant)[1])
