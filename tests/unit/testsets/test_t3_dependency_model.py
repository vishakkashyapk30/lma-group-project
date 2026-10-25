"""T3 (new tests): the builder's copy of the plan §10 dependency model equals the system's, and the construction is internally consistent."""

from __future__ import annotations

from datetime import date, timedelta

from tests.unit.testsets._helpers import read_rows, write_t1_dir
from vakeel_sahayak.agents.vakeel.facts import FACTOR_FIELDS, FACTOR_RIGHTS
from vakeel_sahayak.testsets import t3_change_sets as t3


def test_the_copied_dependency_model_matches_the_vakeel_tables():
    assert t3.FACTOR_FIELDS == FACTOR_FIELDS and t3.FACTOR_RIGHTS == FACTOR_RIGHTS


def test_charge_sheet_change_reopens_the_factors_the_plan_names():
    """staleness.factors_to_reopen: a filed charge sheet opens charge_sheet_filed, trial_delay and witness_tampering."""
    assert {"charge_sheet_filed", "trial_delay", "witness_tampering"} <= set(t3.reopened_factors(["charge_sheet"], ["default_bail"]))


def test_noop_reopens_nothing_and_every_real_change_keeps_other_fields_unchanged(tmp_path):
    t1 = write_t1_dir(tmp_path)
    t3.build_t3(str(t1), str(tmp_path / "t3"))
    for r in read_rows(tmp_path / "t3" / "updates.jsonl"):
        if r["change_type"] == "noop":
            assert r["reopened_factors"] == [] and r["duplicate_of"] == r["case_id"]
        else:
            assert set(r["expected"]["fields"]).isdisjoint(r["unchanged_fields"])
            assert set(r["expected"]["grounds"]) <= set(r["reopened_factors"])


def test_clock_changes_cross_the_threshold_between_baseline_and_new_date(tmp_path):
    t1 = write_t1_dir(tmp_path)
    t3.build_t3(str(t1), str(tmp_path / "t3"))
    for r in read_rows(tmp_path / "t3" / "updates.jsonl"):
        if r["change_type"] != "time_crosses_threshold":
            continue
        b, new = r["baseline"], date.fromisoformat(r["as_of"])
        old = date.fromisoformat(r["baseline_as_of"])
        assert new - old == timedelta(days=1)
        if r["threshold"] == "default_bail_day_61":
            assert (old - date.fromisoformat(b["first_remand"])).days + 1 == 60 and (new - date.fromisoformat(b["first_remand"])).days + 1 == 61
        else:
            assert (old - date.fromisoformat(b["arrest_date"])).days == 851 and (new - date.fromisoformat(b["arrest_date"])).days == 852


def test_the_blind_slice_is_not_used(tmp_path):
    """When manifest_open.json exists only its cases are eligible."""
    import json

    t1 = write_t1_dir(tmp_path, n=200)
    open_ids = [f"t1-{i:03d}" for i in range(0, 200, 2)]
    (t1 / "manifest_open.json").write_text(json.dumps({"slice": "open", "case_ids": open_ids}), encoding="utf-8")
    t3.build_t3(str(t1), str(tmp_path / "t3"))
    assert {r["case_id"] for r in read_rows(tmp_path / "t3" / "updates.jsonl")} <= set(open_ids)
