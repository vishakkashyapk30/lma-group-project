"""Driver case rows (T2, T5, T7) for `eval/runners/jobs.testset_cases_path`: shape, kinds mixed, no gold leaking into the facts."""

from __future__ import annotations

import json

from tests.unit.testsets._helpers import read_rows, write_jsonl, write_t1_dir
from vakeel_sahayak.testsets import driver_cases
from vakeel_sahayak.testsets.t7_safety import build_t7


def test_t2_rows_are_one_per_bundle_with_absolute_pdf_and_mixed_kinds(tmp_path):
    t2 = tmp_path / "t2"
    (t2 / "bundles").mkdir(parents=True)
    truth = [{"bundle_id": f"c{i}_K{k}", "case_id": f"c{i}", "kind": f"K{k}", "pdf": f"bundles/c{i}_K{k}.pdf", "fields": {"as_of": "2025-02-03"}}
             for i in range(10) for k in range(1, 7)]
    write_jsonl(t2 / "truth.jsonl", truth)
    rows = driver_cases.t2_driver_rows(t2)
    assert len(rows) == 60 and len({r["case_id"] for r in rows}) == 60
    assert all(r["bundle"][0].startswith("/") and r["before"] == "2025-02-03" for r in rows)
    assert len({r["kind"] for r in rows[:20]}) >= 4  # the first rows of a job span the kinds
    assert rows == driver_cases.t2_driver_rows(t2)


def test_t5_rows_follow_fifo_order_and_carry_facts(tmp_path):
    t1 = write_t1_dir(tmp_path, n=5)
    t5 = tmp_path / "t5"
    (t5 / "bundles" / "p1").mkdir(parents=True)
    (t5 / "bundles" / "p1" / "01_remand.txt").write_text("remand text", encoding="utf-8")
    cases = [{"case_id": "t1-001", "as_of": "2026-11-02", "source": "T1", "rank": None, "deadline": None, "deadline_kind": None, "bundle": None},
             {"case_id": "p1", "as_of": "2026-11-02", "source": "T4", "rank": 1, "deadline": "2026-11-03", "deadline_kind": "x", "bundle": "bundles/p1"}]
    write_jsonl(t5 / "cases.jsonl", cases)
    rows = driver_cases.t5_driver_rows(t5, t1)
    assert [r["case_id"] for r in rows] == ["t1-001", "p1"]
    assert "case 1" in rows[0]["facts"] and rows[1]["facts"] == "remand text" and rows[1]["bundle"][0].endswith("01_remand.txt")
    assert all(r["before"] == "2026-11-02" and r["scenario"]["approve_gate2"] is False for r in rows)


def test_t7_driver_rows_carry_the_plant_inside_the_court_text_and_never_approve_gate2(tmp_path):
    t1 = write_t1_dir(tmp_path)
    build_t7(str(t1), str(tmp_path / "t7"))
    rows = read_rows(tmp_path / "t7" / "driver_cases.jsonl")
    assert len(rows) == 60 and all(r["scenario"]["approve_gate2"] is False and r["facts"] for r in rows)
    digital = [r for r in rows if r["family"] == "A" and r["variant"] == "digital"]
    assert digital and all(r["planted"][0] in r["facts"] and "arrested on 20.08.2024" in r["facts"] for r in digital)
    assert all(r["planted"] == [] for r in rows if r["variant"] == "control")
    for r in (r for r in rows if r["family"] == "E"):
        assert all(n in r["facts"] for n in r["planted_names"])
    json.dumps(rows)
