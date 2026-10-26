"""S14b/S14c scheduling simulation: hand-computed schedules on a few cases, then the T5 file (if present) end to end in a scratch directory."""

from __future__ import annotations

import json

import pytest

from vakeel_sahayak.eval.studies import run_study, s14


def case(cid, key, planted=False, days=None, gold=None, stages=2):
    return {"case_id": cid, "key": key, "planted": planted, "days_to_deadline": days, "gold_rank": gold, "stages": stages}


# stage 0.5 h, a day of 2 h (four stages a day)
CASES = [case("A", (1,)), case("B", (0, 1), True, 1, 2), case("C", (0, 0), True, 1, 1)]


def test_fifo_serves_in_arrival_order_and_misses_the_late_planted_case():
    r = s14.simulate(CASES, "fifo", stage_hours=0.5, hours_per_day=2.0)
    assert r["first"] == {"A": 0.0, "B": 1.0, "C": 2.0} and r["finish"] == {"A": 1.0, "B": 2.0, "C": 3.0}
    assert (r["missed_start"]["k"], r["missed_start"]["n"]) == (1, 2)  # C starts on day 2 (hour 2.0), its deadline is day 1
    assert r["missed_finish"]["k"] == 1  # C finishes at 3.0 h, day 2
    assert r["pairwise_ranking_accuracy"]["value"] == 0.0  # both planted cases start after the unplanted A
    assert r["planted_order_accuracy"]["value"] == 0.0  # gold wants C before B
    assert r["makespan_h"] == 3.0 and r["cases_per_node_hour"] == 1.0


def test_urgency_orders_by_key_and_meets_both_deadlines():
    r = s14.simulate(CASES, "urgency", stage_hours=0.5, hours_per_day=2.0)
    assert r["first"] == {"C": 0.0, "B": 1.0, "A": 2.0}
    assert r["missed_start"]["k"] == 0 and r["missed_finish"]["k"] == 0 and r["pairwise_ranking_accuracy"]["value"] == 1.0 and r["planted_order_accuracy"]["value"] == 1.0
    assert r["mean_planted_first_service_h"] == 0.5


def test_least_work_interleaves_ties_and_urgency_does_not():
    tied = [case("A", (1,)), case("B", (0, 0), True, 1, 2), case("C", (0, 0), True, 1, 1)]
    lw = s14.simulate(tied, "urgency_least_work", stage_hours=0.5, hours_per_day=2.0)
    assert lw["first"] == {"B": 0.0, "C": 0.5, "A": 2.0} and lw["finish"] == {"B": 1.5, "C": 2.0, "A": 3.0}
    u = s14.simulate(tied, "urgency", stage_hours=0.5, hours_per_day=2.0)
    assert u["first"]["C"] == 0.5 + 0.5 and u["finish"] == {"B": 1.0, "C": 2.0, "A": 3.0}  # ties by id: B runs its two stages first


def test_shortest_first_and_unknown_policy():
    r = s14.simulate([case("long", (1,), stages=4), case("short", (1,), stages=1)], "shortest_first", stage_hours=1.0)
    assert r["first"]["short"] == 0.0
    with pytest.raises(ValueError):
        s14.simulate(CASES, "lifo", stage_hours=1.0)


def test_stages_are_reproducible_and_in_range():
    assert s14.stages_of("t1-001") == s14.stages_of("t1-001") and all(3 <= s14.stages_of(f"x{i}") <= 8 for i in range(50))
    assert s14.stages_of("x", 7) == 7


def t5_rows():
    """Five unplanted T1 rows first (arrival order), then three planted default-bail scenarios with the deadline 1, 2 and 3 days away (their Radar checks are real)."""
    rows = [{"case_id": f"t1-{i}", "urgent": False, "facts": None, "rank": None, "days_to_deadline": None} for i in range(5)]
    for j, (day, rank) in enumerate([(89, 1), (88, 2), (87, 3)]):
        rows.append({"case_id": f"t5-db-{j}", "urgent": True, "rank": rank, "days_to_deadline": j + 1,
                     "facts": {"as_of": "2026-11-02", "charge_sheet": None, "day": day, "first_remand": "2026-08-06", "max_punishment": "20 years"}})
    return rows


def test_run_writes_json_and_markdown(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in t5_rows()) + "\n", encoding="utf-8")
    res = run_study("s14", str(tmp_path / "o"), cases_path=str(path), hours_per_day=1.0)
    pol = res["policies"]
    assert res["n_cases"] == 8 and res["n_planted"] == 3 and set(pol) == set(s14.POLICIES)
    # fifo serves the five unplanted cases first: each takes 0.25 h on average, so the planted ones start late; urgency serves them first
    assert pol["urgency"]["pairwise_ranking_accuracy"]["value"] == 1.0 and pol["fifo"]["pairwise_ranking_accuracy"]["value"] == 0.0
    assert pol["urgency"]["missed_start"]["k"] == 0 <= pol["fifo"]["missed_start"]["k"]
    assert pol["urgency"]["cases_per_node_hour"] == pytest.approx(pol["fifo"]["cases_per_node_hour"])
    assert "S14c" in (tmp_path / "o" / "s14.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "o" / "s14.json").read_text(encoding="utf-8"))["assumptions"]["workers"] == 1
    with pytest.raises(FileNotFoundError):
        run_study("s14", str(tmp_path / "o2"), cases_path=str(tmp_path / "absent.jsonl"))
