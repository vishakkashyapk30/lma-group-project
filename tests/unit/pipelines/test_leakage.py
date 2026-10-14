"""Leakage rules (plan §2): test orders and orders with the same FIR as a test order are excluded from every store and
from fine-tuning data; the RQ1 input (facts part) shares no 8-word sequence with the other parts (plan §15.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.pipelines._helpers import order_row, words, write_jsonl
from vakeel_sahayak.pipelines.leakage import assert_no_overlap, excluded_doc_ids, same_fir_groups

FIXTURE_ORDERS = Path(__file__).resolve().parents[2] / "fixtures" / "caselaw" / "orders.jsonl"
SAME_FIR = {"TESTORD-2024-0001", "SAMEFIR-2024-0002"}


# ---- same_fir_groups ---------------------------------------------------------------------------------------------
def test_fixture_orders_with_same_fir_are_grouped():
    """TESTORD-2024-0001 and SAMEFIR-2024-0002 share (Delhi HC, PS-1, 112, 2024), so they form one group."""
    groups = same_fir_groups(str(FIXTURE_ORDERS))
    assert any(set(ids) == SAME_FIR for ids in groups.values())


def test_every_order_is_in_at_most_one_group():
    """Grouping is a partition: no doc id appears under two FIR keys."""
    groups = same_fir_groups(str(FIXTURE_ORDERS))
    seen = [i for ids in groups.values() for i in ids]
    assert len(seen) == len(set(seen))


def test_fir_key_is_court_station_number_year(tmp_path):
    """Orders differing in court, police station, FIR number or FIR year are different FIRs; identical on all four are one."""
    rows = [
        order_row("a", "2024-05-01", court="Delhi High Court", ps="PS-1", fir="112", fir_year=2024),
        order_row("b", "2024-06-01", court="Delhi High Court", ps="PS-1", fir="112", fir_year=2024),
        order_row("c", "2024-06-02", court="Bombay High Court", ps="PS-1", fir="112", fir_year=2024),
        order_row("d", "2024-06-03", court="Delhi High Court", ps="PS-2", fir="112", fir_year=2024),
        order_row("e", "2024-06-04", court="Delhi High Court", ps="PS-1", fir="113", fir_year=2024),
        order_row("f", "2024-06-05", court="Delhi High Court", ps="PS-1", fir="112", fir_year=2023),
    ]
    groups = same_fir_groups(str(write_jsonl(tmp_path / "o.jsonl", rows)))
    multi = [set(v) for v in groups.values() if len(v) > 1]
    assert multi == [{"a", "b"}]


# ---- excluded_doc_ids --------------------------------------------------------------------------------------------
def _splits(tmp_path: Path, mapping: dict[str, str]) -> Path:
    p = tmp_path / "splits.json"
    p.write_text(json.dumps(mapping))
    return p


def test_excluded_ids_are_test_orders_plus_same_fir_orders(tmp_path):
    """Plan §2: exclude the test order AND the same-FIR train order, but not train orders of other FIRs."""
    # ASSUMPTION: the splits file is a JSON object {doc_id: split}.
    splits = _splits(tmp_path, {"DLHC-2022-1187": "train", "DLHC-2023-0911": "train", "TESTORD-2024-0001": "test",
                                "SAMEFIR-2024-0002": "train", "DLHC-2025-0099": "train"})
    assert excluded_doc_ids(str(splits), str(FIXTURE_ORDERS)) == SAME_FIR


def test_dev_order_with_same_fir_as_a_test_order_is_excluded(tmp_path):
    """Any order with the same FIR as a test order is excluded, whatever its own split (here: dev)."""
    rows = [order_row("t1", "2024-08-01", fir="9", fir_year=2024, ps="PS-9"), order_row("d1", "2024-02-01", fir="9", fir_year=2024, ps="PS-9"),
            order_row("x1", "2023-02-01", fir="10", fir_year=2023)]
    orders = write_jsonl(tmp_path / "o.jsonl", rows)
    splits = _splits(tmp_path, {"t1": "test", "d1": "dev", "x1": "train"})
    assert excluded_doc_ids(str(splits), str(orders)) == {"t1", "d1"}


def test_no_test_orders_means_nothing_excluded(tmp_path):
    """Without a test order there is nothing to exclude."""
    rows = [order_row("a", "2022-01-01"), order_row("b", "2022-02-01")]
    orders = write_jsonl(tmp_path / "o.jsonl", rows)
    assert excluded_doc_ids(str(_splits(tmp_path, {"a": "train", "b": "train"})), str(orders)) == set()


def test_excluded_ids_are_a_set_of_strings(tmp_path):
    """The result is a set of doc-id strings, ready to pass to the store builders' exclude_doc_ids."""
    splits = _splits(tmp_path, {"TESTORD-2024-0001": "test", "SAMEFIR-2024-0002": "train"})
    out = excluded_doc_ids(str(splits), str(FIXTURE_ORDERS))
    assert isinstance(out, set) and all(isinstance(i, str) for i in out)


# ---- assert_no_overlap -------------------------------------------------------------------------------------------
FACTS = words("fact", 40)


def _with_run(k: int) -> tuple[str, str]:
    """facts text and an 'other part' text that share exactly one contiguous run of k words."""
    shared = FACTS[10:10 + k]
    other = words("op", 5) + shared + words("oq", 5)
    return " ".join(FACTS), " ".join(other)


def test_no_shared_words_passes():
    """Facts and other parts with no common sequence pass."""
    assert assert_no_overlap(" ".join(FACTS), [" ".join(words("x", 30))]) is None


def test_exactly_eight_shared_words_raises():
    """Plan §15.1: an 8-word shared run is a leak."""
    facts, other = _with_run(8)
    with pytest.raises((AssertionError, ValueError)):
        assert_no_overlap(facts, [other])


def test_seven_shared_words_passes():
    """Seven shared words are below the 8-word threshold."""
    facts, other = _with_run(7)
    assert assert_no_overlap(facts, [other]) is None


@given(st.integers(min_value=0, max_value=20))
def test_overlap_boundary_property(k):
    """Property: a contiguous shared run of k words raises iff k >= 8 (default n=8)."""
    facts, other = _with_run(k)
    if k >= 8:
        with pytest.raises((AssertionError, ValueError)):
            assert_no_overlap(facts, [other])
    else:
        assert assert_no_overlap(facts, [other]) is None


def test_overlap_with_any_one_part_is_enough():
    """A leak into only the second of several other parts is still caught."""
    facts, leaky = _with_run(9)
    with pytest.raises((AssertionError, ValueError)):
        assert_no_overlap(facts, [" ".join(words("clean", 20)), leaky, " ".join(words("also", 20))])


def test_two_separate_halves_do_not_make_a_run():
    """4 shared words, a break, 4 more shared words are not an 8-word run."""
    other = " ".join(words("p", 3) + FACTS[10:14] + ["BREAK"] + FACTS[14:18] + words("q", 3))
    assert assert_no_overlap(" ".join(FACTS), [other]) is None


def test_custom_window_n():
    """n is configurable: three shared words are a leak at n=3 but not at n=4."""
    facts, other = _with_run(3)
    with pytest.raises((AssertionError, ValueError)):
        assert_no_overlap(facts, [other], n=3)
    assert assert_no_overlap(facts, [other], n=4) is None


def test_comparison_ignores_case_and_punctuation():
    """ASSUMPTION: words are compared lower-cased without punctuation, so re-cased copies are still caught."""
    run = FACTS[10:18]
    other = "Intro, " + " ".join(w.upper() + "," for w in run) + " outro."
    with pytest.raises((AssertionError, ValueError)):
        assert_no_overlap(" ".join(FACTS), [other])


def test_short_facts_text_cannot_overlap():
    """A facts text shorter than 8 words has no 8-word sequence at all."""
    assert assert_no_overlap("the applicant was arrested", ["the applicant was arrested yesterday morning"]) is None
