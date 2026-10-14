"""T1 court-grounded bail set (plan §15.2): 200 test orders (at least 60 BNS-era), the FACTS part as the only input, answers G1-G7.

Plan §15.1: 'RQ1 runs on the facts part only, and a check confirms it shares no 8-word sequence with the other parts.'
Input layout: tests/unit/testsets/_helpers.py (400 candidates, only 62 of them BNS-era, the BNS-era ones placed last so that a naive
"first 200" would contain none).
"""

from __future__ import annotations

import json

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, shares_ngram, write_t1_inputs
from vakeel_sahayak.testsets.t1_court_grounded import build_t1


def build(tmp_path, **kw):
    parts, gold = write_t1_inputs(tmp_path, **kw)
    out = tmp_path / "t1"
    manifest = build_t1(str(parts), str(gold), str(out))
    return manifest, read_rows(out / "cases.jsonl"), out


def test_size_is_two_hundred_with_the_planned_metadata(tmp_path):
    m, cases, out = build(tmp_path)
    assert_manifest(m, "T1", 200)
    assert len(cases) == 200 and len({c["doc_id"] for c in cases}) == 200
    assert {"RQ1", "F1", "F3", "F5", "F6", "F7"} <= set(m.used_for)
    assert "G1" in m.answers_from and "G7" in m.answers_from
    assert read_manifest(out)["size"] == 200


def test_at_least_sixty_are_bns_era_even_when_they_are_rare_in_the_pool(tmp_path):
    """62 of 400 candidates are BNS-era (offence on or after 2024-07-01): a uniform sample of 200 would hold about 31, so the builder
    must reserve places for them (plan §2: test has at least 60 BNS-era orders)."""
    _, cases, _ = build(tmp_path)
    assert sum(c["bns_era"] for c in cases) >= 60


def test_fewer_than_sixty_bns_era_candidates_is_an_error(tmp_path):
    """The plan's minimum cannot be met: fail loudly instead of quietly shipping a weaker set. # ASSUMPTION: ValueError."""
    with pytest.raises(ValueError):
        build(tmp_path, n_bns=40)


def test_fewer_than_two_hundred_candidates_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        build(tmp_path, n_candidates=150, n_bns=70)


def test_the_input_is_the_facts_part_only(tmp_path):
    """The case carries the facts text and none of the defense, prosecution, reasoning or operative text."""
    parts_path, gold = write_t1_inputs(tmp_path)
    out = tmp_path / "t1"
    build_t1(str(parts_path), str(gold), str(out))
    src = {r["doc_id"]: r["parts"] for r in read_rows(parts_path)}
    for c in read_rows(out / "cases.jsonl"):
        parts = src[c["doc_id"]]
        assert c["facts_text"] == parts["facts"]
        blob = " ".join(str(v) for k, v in c.items() if k != "gold")
        for other in ("defense_submissions", "prosecution_submissions", "reasoning", "operative_order"):
            assert parts[other].split()[0] not in blob


def test_gold_g1_to_g7_is_attached_to_every_case(tmp_path):
    _, cases, _ = build(tmp_path)
    assert all(set(c["gold"]) == {f"G{k}" for k in range(1, 8)} for c in cases)


def test_orders_whose_facts_share_an_8_word_sequence_with_another_part_are_left_out(tmp_path):
    """Leakage check (plan §15.1): a candidate whose facts text repeats nine words of its reasoning is not a T1 case."""
    leaky = {5, 6, 7, 100, 101}
    parts_path, gold = write_t1_inputs(tmp_path, leaky=leaky)
    out = tmp_path / "t1"
    build_t1(str(parts_path), str(gold), str(out))
    cases = read_rows(out / "cases.jsonl")
    leaked_ids = {f"TEST-{i:04d}" for i in leaky}
    assert not leaked_ids & {c["doc_id"] for c in cases}
    src = {r["doc_id"]: r["parts"] for r in read_rows(parts_path)}
    for c in cases:  # independent re-check of the property for every case that was kept
        for name, text in src[c["doc_id"]].items():
            if name != "facts":
                assert not shares_ngram(c["facts_text"], text, 8), (c["doc_id"], name)


def test_orders_without_complete_gold_are_dropped(tmp_path):
    """Orders that do not split cleanly (no G-label) are dropped (plan §15.1) rather than scored on partial gold."""
    parts_path, gold = write_t1_inputs(tmp_path, n_candidates=410, n_bns=70)
    g3 = read_rows(gold / "g3.jsonl")
    (gold / "g3.jsonl").write_text("\n".join(json.dumps(r) for r in g3 if r["doc_id"] != "TEST-0100") + "\n")
    out = tmp_path / "t1"
    build_t1(str(parts_path), str(gold), str(out))
    assert "TEST-0100" not in {c["doc_id"] for c in read_rows(out / "cases.jsonl")}


def test_build_is_deterministic(tmp_path):
    """Fixed seed: the same candidates give the same 200 cases in the same order."""
    parts, gold = write_t1_inputs(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    build_t1(str(parts), str(gold), str(a))
    build_t1(str(parts), str(gold), str(b))
    assert (a / "cases.jsonl").read_bytes() == (b / "cases.jsonl").read_bytes()


def test_case_ids_are_unique_and_stable(tmp_path):
    _, cases, _ = build(tmp_path)
    assert len({c["case_id"] for c in cases}) == 200
