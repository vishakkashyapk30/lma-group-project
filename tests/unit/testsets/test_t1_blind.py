"""T1 manifests: dev / open / blind sizes, hashed blind ids, High-Court-only pool, post-release subset and the one-time blind opening."""

from __future__ import annotations

import json

import pytest

from tests.unit.testsets._helpers import read_rows, write_t1_inputs
from vakeel_sahayak.testsets.blind import BlindSliceError, blind_hash, open_blind
from vakeel_sahayak.testsets.t1_court_grounded import build_t1


def build(tmp_path, mutate=None):
    parts, gold = write_t1_inputs(tmp_path)
    rows = read_rows(parts)
    if mutate:
        rows = mutate(rows)
    parts.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    out = tmp_path / "t1"
    return build_t1(str(parts), str(gold), str(out)), out


def test_open_and_blind_partition_the_200_and_blind_has_enough_bns(tmp_path):
    m, out = build(tmp_path)
    assert m.details["sizes"] == {"test": 200, "dev": 0, "open": 120, "blind": 80}
    assert m.details["targets_met"]["blind_bns_ge_25"] and m.details["targets_met"]["bns_ge_60"]
    opened = json.loads((out / "manifest_open.json").read_text())["case_ids"]
    cases = {c["case_id"] for c in read_rows(out / "cases.jsonl")}
    assert len(opened) == 120 and set(opened) <= cases


def test_blind_ids_are_stored_as_hashes_only(tmp_path):
    _, out = build(tmp_path)
    manifest = json.loads((out / "manifest_blind.json").read_text())
    sealed = json.loads((out / "blind_sealed.json").read_text())["ids"]
    assert manifest["n"] == 80 and sorted(manifest["hashes"]) == sorted(blind_hash(i) for i in sealed)
    text = (out / "manifest_blind.json").read_text() + (out / "manifest.json").read_text()
    assert not any(i in text for i in sealed)


def test_blind_opens_once_and_only_with_the_flag(tmp_path):
    _, out = build(tmp_path)
    lock = tmp_path / "blind.lock"
    with pytest.raises(BlindSliceError):
        open_blind(str(out), confirm=False, lock=lock, check_tag=False)
    ids = open_blind(str(out), confirm=True, lock=lock, check_tag=False)
    assert len(ids) == 80 and lock.exists()
    with pytest.raises(BlindSliceError):
        open_blind(str(out), confirm=True, lock=lock, check_tag=False)


def test_blind_refuses_without_the_freeze_tag(tmp_path):
    _, out = build(tmp_path)
    with pytest.raises(BlindSliceError):
        open_blind(str(out), confirm=True, lock=tmp_path / "x.lock", tag="no-such-tag-ever")


def test_supreme_court_orders_never_enter_the_pool(tmp_path):
    def mutate(rows):
        for r in rows[:30]:
            r["court"] = "Supreme Court of India"
        return rows

    m, out = build(tmp_path, mutate)
    assert all("Supreme" not in c["court"] for c in read_rows(out / "cases.jsonl"))
    assert m.details["pool"]["left_out"]["test:not_high_court"] == 30


def test_post_release_orders_fill_the_blind_slice_when_there_are_enough(tmp_path):
    def mutate(rows):
        for r in rows[:150] + rows[-62:]:  # the BNS-era rows are last in the parts file
            r["date"] = "2025-06-10"
        return rows

    m, _ = build(tmp_path, mutate)
    assert m.details["targets_met"]["blind_all_post_release"] and m.details["post_release_subset"]["blind_count"] == 80


def test_manifest_has_per_court_script_and_coverage_statistics(tmp_path):
    m, _ = build(tmp_path)
    t = m.details["test"]
    assert sum(t["per_court"].values()) == 200 and t["per_script"] == {"latin": 200}
    assert "citation_resolution_coverage" in t and "dossier_field_coverage" in t
