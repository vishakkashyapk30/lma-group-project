"""T4 rights scenarios (plan §15.2, §7.3, Appendix C): 500 scenario specs written from the bare acts by a team member who does NOT write the
Radar code, rendered as document bundles; the designed answer is the spec's own. Dates sit on either side of each threshold:
day 59/60/61; one-third vs one-half; 7 vs 10 years; first-time vs repeat.

The scenario table below is what such a spec writer would produce from Appendix C (the same boundaries as tests/unit/rights, written
independently of the Radar). The 60-day window: day 61 without a charge sheet is ELIGIBLE, day 60 NOT_YET; offences of 10 years or more
use 90 days; the undertrial limit for 7 years is 852 days for a first-time offender (1/3) and 1,278 for a repeat offender (1/2).

# ASSUMPTION: spec row = {"id", "rule", "inputs": {...}, "designed_answer": <RightsStatus value>}; out_dir/scenarios.jsonl keeps the spec
# and adds {"bundle": <file name>}. The repo spec file (configs-side, testsets/specs/rights_scenarios.yaml) is empty until the team
# member writes it, so the 500-scenario check is skipped until then.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest
import yaml

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows
from vakeel_sahayak.testsets.t4_rights_scenarios import build_t4, load_scenario_specs

SPEC_FILE = Path(inspect.getfile(importlib.import_module("vakeel_sahayak.testsets"))).parent / "specs" / "rights_scenarios.yaml"


def spec(sid: str, rule: str, answer: str, **inputs) -> dict:
    return {"id": sid, "rule": rule, "inputs": inputs, "designed_answer": answer}


FR = "2024-08-21"  # first remand = day 1
# (day of charge sheet or "none yet" on day N, max punishment, answer)
STRADDLE = [
    spec("db-60-59", "default_bail", "NOT_YET", first_remand=FR, day=59, max_punishment="7 years", charge_sheet=None),
    spec("db-60-60", "default_bail", "NOT_YET", first_remand=FR, day=60, max_punishment="7 years", charge_sheet=None),
    spec("db-60-61", "default_bail", "ELIGIBLE", first_remand=FR, day=61, max_punishment="7 years", charge_sheet=None),
    spec("db-90-61", "default_bail", "NOT_YET", first_remand=FR, day=61, max_punishment="10 years", charge_sheet=None),
    spec("db-90-90", "default_bail", "NOT_YET", first_remand=FR, day=90, max_punishment="life", charge_sheet=None),
    spec("db-90-91", "default_bail", "ELIGIBLE", first_remand=FR, day=91, max_punishment="life", charge_sheet=None),
    spec("db-cs-74", "default_bail", "WINDOW_CLOSED", first_remand=FR, day=74, max_punishment="7 years", charge_sheet="2024-11-02"),
    spec("ut-third-851", "undertrial_limit", "NOT_YET", custody_days=851, max_punishment="7 years", first_time=True),
    spec("ut-third-852", "undertrial_limit", "ELIGIBLE", custody_days=852, max_punishment="7 years", first_time=True),
    spec("ut-half-852", "undertrial_limit", "NOT_YET", custody_days=852, max_punishment="7 years", first_time=False),
    spec("ut-half-1278", "undertrial_limit", "ELIGIBLE", custody_days=1278, max_punishment="7 years", first_time=False),
    spec("ut-life", "undertrial_limit", "NOT_APPLICABLE", custody_days=2000, max_punishment="life", first_time=True),
    spec("ut-7v10-first", "undertrial_limit", "NOT_YET", custody_days=852, max_punishment="10 years", first_time=True),  # 1/3 of 10 y = 1,217
]


def write_specs(tmp_path, specs) -> str:
    p = tmp_path / "specs.yaml"
    p.write_text(yaml.safe_dump({"scenarios": specs}), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------- loading
def test_load_scenario_specs_returns_the_list_in_file_order(tmp_path):
    loaded = load_scenario_specs(write_specs(tmp_path, STRADDLE))
    assert [s["id"] for s in loaded] == [s["id"] for s in STRADDLE]
    assert loaded[0]["designed_answer"] == "NOT_YET"


def test_repo_spec_file_has_the_scenarios_key():
    assert "scenarios" in yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8"))


def test_duplicate_scenario_ids_are_rejected(tmp_path):
    """# ASSUMPTION: ids identify scenarios in the F3 per-rule accuracy table, so duplicates are a ValueError."""
    with pytest.raises(ValueError):
        load_scenario_specs(write_specs(tmp_path, [STRADDLE[0], STRADDLE[0]]))


def test_a_spec_without_a_designed_answer_is_rejected(tmp_path):
    bad = {"id": "x", "rule": "default_bail", "inputs": {}}
    with pytest.raises(ValueError):
        load_scenario_specs(write_specs(tmp_path, [bad]))


# ---------------------------------------------------------------- the straddle table itself (spec facts, pass today)
def test_the_spec_table_straddles_every_planned_threshold():
    """Plan §15.2: day 59/60/61, one-third vs one-half, 7 vs 10 years, first-time vs repeat all appear."""
    days = {s["inputs"].get("day") for s in STRADDLE if s["rule"] == "default_bail"}
    assert {59, 60, 61} <= days
    ut = [s for s in STRADDLE if s["rule"] == "undertrial_limit"]
    assert {s["inputs"]["first_time"] for s in ut} == {True, False}
    assert {s["inputs"]["max_punishment"] for s in STRADDLE} >= {"7 years", "10 years"}
    assert {s["inputs"]["custody_days"] for s in ut} >= {851, 852, 1278}


def test_designed_answers_are_valid_rights_statuses():
    from vakeel_sahayak.schemas.enums import RightsStatus

    assert {s["designed_answer"] for s in STRADDLE} <= {x.value for x in RightsStatus}


# ---------------------------------------------------------------- the build
def test_one_rendered_scenario_per_spec_with_the_designed_answer_unchanged(tmp_path):
    out = tmp_path / "t4"
    m = build_t4(write_specs(tmp_path, STRADDLE), str(out))
    rows = read_rows(out / "scenarios.jsonl")
    assert_manifest(m, "T4", len(STRADDLE))
    assert [r["id"] for r in rows] == [s["id"] for s in STRADDLE]
    assert [r["designed_answer"] for r in rows] == [s["designed_answer"] for s in STRADDLE]
    assert m.used_for == ["F3"] and read_manifest(out)["size"] == len(STRADDLE)


def test_scenarios_are_rendered_as_document_bundles(tmp_path):
    out = tmp_path / "t4"
    build_t4(write_specs(tmp_path, STRADDLE), str(out))
    for r in read_rows(out / "scenarios.jsonl"):
        assert r["bundle"] and (out / r["bundle"]).exists()


def test_the_first_remand_date_appears_in_a_default_bail_bundle(tmp_path):
    """The rendered documents carry the scenario's dates (here: first remand 21.08.2024), so the system has to read them."""
    out = tmp_path / "t4"
    build_t4(write_specs(tmp_path, STRADDLE[:1]), str(out))
    row = read_rows(out / "scenarios.jsonl")[0]
    blob = (out / row["bundle"]).read_bytes() if (out / row["bundle"]).is_file() else b"".join(p.read_bytes() for p in (out / row["bundle"]).rglob("*") if p.is_file())
    assert b"21.08.2024" in blob or b"2024-08-21" in blob


def test_build_is_deterministic(tmp_path):
    spec_path = write_specs(tmp_path, STRADDLE)
    build_t4(spec_path, str(tmp_path / "a"))
    build_t4(spec_path, str(tmp_path / "b"))
    assert (tmp_path / "a" / "scenarios.jsonl").read_bytes() == (tmp_path / "b" / "scenarios.jsonl").read_bytes()


def test_the_answers_are_not_computed_by_the_radar():
    """Independence (plan §15.2): T4's module does not import the Rights Radar, so the designed answer cannot be the Radar's output."""
    src = (SPEC_FILE.parent.parent / "t4_rights_scenarios.py").read_text(encoding="utf-8")
    imports = [n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module]
    assert not [m for m in imports if m.startswith("vakeel_sahayak.rights")]


def test_the_repo_spec_file_holds_500_scenarios_straddling_every_threshold():
    """When the team member has written the specs: 500 of them, covering day 59/60/61 etc. Skipped until then."""
    scenarios = yaml.safe_load(SPEC_FILE.read_text(encoding="utf-8"))["scenarios"]
    if not scenarios:
        pytest.skip("rights_scenarios.yaml is still empty: the specs are written by a team member who does not write the Radar (plan §15.2)")
    assert len(scenarios) == 500
    rules = {s["rule"] for s in scenarios}
    assert {"default_bail", "undertrial_limit"} <= rules
    assert {59, 60, 61} <= {s["inputs"].get("day") for s in scenarios if s["rule"] == "default_bail"}
