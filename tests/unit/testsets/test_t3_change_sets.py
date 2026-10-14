"""T3 change sets (plan §15.2, §7.4, §10): 60 T1 cases x 3 changes (charge sheet filed; co-accused granted bail; time crosses a threshold),
plus 60 no-op controls (a duplicate document): 240 updates. Answers by construction: which fields and grounds should change.

# ASSUMPTION: out_dir/updates.jsonl rows: {"update_id", "case_id", "change_type": "charge_sheet_filed" | "co_accused_bail" |
#   "time_crosses_threshold" | "noop", "trigger": "new_document" | "clock", "new_document": <text or None>, "as_of": <date or None>,
#   "expected": {"fields": [...], "grounds": [<factor ids>], "rights_changed": [...]}}.
# ASSUMPTION: the 60 no-op controls reuse the same 60 cases (one control per case); field and factor names are those of the dossier
# schema and Appendix A.
"""

from __future__ import annotations

import collections

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, write_t1_dir
from vakeel_sahayak.testsets.t3_change_sets import build_t3

TYPES = ["charge_sheet_filed", "co_accused_bail", "time_crosses_threshold", "noop"]


@pytest.fixture()
def built(tmp_path):
    t1 = write_t1_dir(tmp_path)
    out = tmp_path / "t3"
    manifest = build_t3(str(t1), str(out))
    return manifest, read_rows(out / "updates.jsonl"), out, read_rows(t1 / "cases.jsonl")


def of_type(rows, t):
    return [r for r in rows if r["change_type"] == t]


def test_240_updates_and_the_manifest(built):
    m, rows, out, _ = built
    assert_manifest(m, "T3", 240)
    assert len(rows) == 240 and m.used_for == ["F2"]
    assert read_manifest(out)["size"] == 240


def test_three_change_types_of_sixty_plus_sixty_noop_controls(built):
    """60 x 3 real changes (180 updates, the F2 workload of runs.yaml) and 60 controls."""
    _, rows, _, _ = built
    assert collections.Counter(r["change_type"] for r in rows) == {t: 60 for t in TYPES}


def test_sixty_distinct_t1_cases_are_used(built):
    _, rows, _, cases = built
    used = {r["case_id"] for r in rows}
    assert len(used) == 60 and used <= {c["case_id"] for c in cases}
    for t in TYPES:
        assert {r["case_id"] for r in of_type(rows, t)} == used


def test_charge_sheet_filed_changes_only_the_charge_sheet_field(built):
    """Truth for 'the charge sheet is filed': field charge_sheet changes, the charge-sheet ground is reopened, nothing else is."""
    _, rows, _, _ = built
    for r in of_type(rows, "charge_sheet_filed"):
        assert r["trigger"] == "new_document" and r["new_document"]
        assert r["expected"]["fields"] == ["charge_sheet"]
        assert r["expected"]["grounds"] == ["charge_sheet_filed"]
        assert "charge sheet" in r["new_document"].lower()


def test_co_accused_granted_bail_changes_the_parity_ground(built):
    _, rows, _, _ = built
    for r in of_type(rows, "co_accused_bail"):
        assert r["expected"]["fields"] == ["co_accused_bail"]
        assert r["expected"]["grounds"] == ["parity_with_co_accused"]
        assert "granted" in r["new_document"].lower() and "bail" in r["new_document"].lower()


def test_time_crossing_a_threshold_is_a_clock_change_with_no_new_document(built):
    """Plan §7.4: 'The radar also runs on a clock': crossing a threshold creates a change set without any upload."""
    _, rows, _, _ = built
    for r in of_type(rows, "time_crosses_threshold"):
        assert r["trigger"] == "clock" and not r["new_document"] and r["as_of"]
        assert r["expected"]["fields"] == ["custody_days"]
        assert r["expected"]["rights_changed"] and r["expected"]["grounds"]


def test_noop_controls_are_duplicates_and_expect_no_change_at_all(built):
    """No-op control: re-filing a document the case already holds -> no field, no ground, no rights flag changes (F2: 'no edits')."""
    _, rows, _, cases = built
    facts = {c["case_id"]: c["facts_text"] for c in cases}
    for r in of_type(rows, "noop"):
        assert r["expected"] == {"fields": [], "grounds": [], "rights_changed": []}
        assert r["new_document"] and r["new_document"] in facts[r["case_id"]] or r["new_document"] == facts[r["case_id"]]


def test_real_changes_always_expect_at_least_one_field_or_a_right(built):
    _, rows, _, _ = built
    for r in rows:
        if r["change_type"] != "noop":
            assert r["expected"]["fields"] or r["expected"]["rights_changed"]


def test_update_ids_are_unique(built):
    _, rows, _, _ = built
    assert len({r["update_id"] for r in rows}) == 240


def test_build_is_deterministic(tmp_path):
    t1 = write_t1_dir(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    build_t3(str(t1), str(a))
    build_t3(str(t1), str(b))
    assert (a / "updates.jsonl").read_bytes() == (b / "updates.jsonl").read_bytes()


def test_fewer_than_sixty_t1_cases_is_an_error(tmp_path):
    """Not enough cases for 60 x 3 + 60: refuse. # ASSUMPTION: ValueError."""
    t1 = write_t1_dir(tmp_path, n=40, n_bns=20)
    with pytest.raises(ValueError):
        build_t3(str(t1), str(tmp_path / "t3"))
