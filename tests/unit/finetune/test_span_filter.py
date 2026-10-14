"""Fine-tuning data steps 2-3 (plan §12): `span_check` tests whether each quote supports its value; only orders where EVERY field
passes are kept (an estimated ~2K of ~4K pairs).

The NLI-based `span_check` tool is replaced by a rule-based stand-in (`RuleSpanCheck`: a quote supports its value unless it is
empty or the BAD_QUOTE marker), so what is under test is the filtering rule, not the NLI model. Row shape: see _helpers.py.
"""

from __future__ import annotations

import inspect

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.finetune._helpers import RuleSpanCheck, pair_row, read_rows, valued_fields, write_jsonl
from vakeel_sahayak.finetune.span_filter import filter_pairs

ALL_FIELDS = valued_fields(pair_row("x")["dossier"])


def run_filter(tmp_path, monkeypatch, rows):
    span = RuleSpanCheck().install(monkeypatch)
    src = write_jsonl(tmp_path / "dossiers.jsonl", rows)
    out = tmp_path / "pairs.jsonl"
    kept = filter_pairs(str(src), str(out))
    return kept, read_rows(out), span


def test_signature():
    """filter_pairs(dossiers_path, out_path) -> number kept."""
    assert list(inspect.signature(filter_pairs).parameters) == ["dossiers_path", "out_path"]


def test_the_synthetic_dossier_has_ten_valued_fields():
    """Sanity of the helper: case-0007 minus its computed, user-stated and unsupported fields leaves ten fields with a quote."""
    assert len(ALL_FIELDS) == 10 and "custody_days" not in ALL_FIELDS and "antecedents" not in ALL_FIELDS


def test_orders_where_every_field_passes_are_kept(tmp_path, monkeypatch):
    """Two clean orders -> both kept, same order, and the count returned equals the rows written."""
    kept, rows, _ = run_filter(tmp_path, monkeypatch, [pair_row("o1"), pair_row("o2")])
    assert kept == 2
    assert [r["doc_id"] for r in rows] == ["o1", "o2"]


def test_one_failing_field_drops_the_whole_order(tmp_path, monkeypatch):
    """Plan §12 step 3: 'only orders where every field passes are kept': an order with a single bad quote is dropped entirely."""
    kept, rows, _ = run_filter(tmp_path, monkeypatch, [pair_row("good"), pair_row("one_bad", ("arrest_date",)),
                                                       pair_row("two_bad", ("fir", "sections"))])
    assert kept == 1
    assert [r["doc_id"] for r in rows] == ["good"]


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_any_single_field_failing_drops_the_order(tmp_path, monkeypatch, field):
    """The rule is per field with no exemption: whichever field fails, the order goes."""
    kept, rows, _ = run_filter(tmp_path, monkeypatch, [pair_row("o", (field,))])
    assert (kept, rows) == (0, [])


def test_kept_pairs_are_passed_through_unchanged(tmp_path, monkeypatch):
    """The filter selects; it never edits the facts input or the teacher's target dossier."""
    original = pair_row("o1")
    _, rows, _ = run_filter(tmp_path, monkeypatch, [original])
    assert rows == [original]


def test_span_check_is_run_on_each_valued_field_with_its_own_quote(tmp_path, monkeypatch):
    """Every valued field is checked (the quote is the tool's second argument), and every quote used is one of the order's own."""
    row = pair_row("o1")
    _, _, span = run_filter(tmp_path, monkeypatch, [row])
    own_quotes = {f["source"]["quote"] for f in row["dossier"]["fields"].values() if f.get("value") is not None}
    assert {q for _, q in span.calls} == own_quotes
    assert len(span.calls) >= len(ALL_FIELDS)


def test_empty_fields_without_a_value_are_not_checked(tmp_path, monkeypatch):
    """# ASSUMPTION: a field the teacher left empty (value null, e.g. antecedents) has nothing to verify and does not drop the order."""
    row = pair_row("o1")
    assert row["dossier"]["fields"]["antecedents"]["value"] is None
    kept, _, span = run_filter(tmp_path, monkeypatch, [row])
    assert kept == 1
    assert all(value is not None for value, _ in span.calls)


def test_a_valued_field_without_a_quote_fails(tmp_path, monkeypatch):
    """The teacher must quote a source sentence for each field (plan §12 step 1): a value with no quote cannot pass step 2."""
    row = pair_row("o1")
    row["dossier"]["fields"]["trial_stage"]["source"]["quote"] = ""
    kept, rows, _ = run_filter(tmp_path, monkeypatch, [row])
    assert (kept, rows) == (0, [])


def test_empty_input_gives_zero(tmp_path, monkeypatch):
    kept, rows, _ = run_filter(tmp_path, monkeypatch, [])
    assert (kept, rows) == (0, [])


def test_about_half_survive_in_the_planned_proportion(tmp_path, monkeypatch):
    """Plan §12: ~4K teacher outputs -> ~2K kept. A toy run with every second order corrupted keeps exactly half."""
    rows = [pair_row(f"o{i}", ("fir",) if i % 2 else ()) for i in range(40)]
    kept, out, _ = run_filter(tmp_path, monkeypatch, rows)
    assert kept == 20 and len(out) == 20


@given(bad=st.lists(st.booleans(), min_size=0, max_size=8))
@settings(max_examples=25, deadline=None)
def test_property_kept_is_exactly_the_clean_subsequence(tmp_path_factory, bad):
    """Property: the output is the subsequence of clean orders, in input order, and the returned count is its length."""
    from _pytest.monkeypatch import MonkeyPatch

    tmp = tmp_path_factory.mktemp("filter")
    rows = [pair_row(f"o{i}", ("offence_date",) if b else ()) for i, b in enumerate(bad)]
    with MonkeyPatch.context() as mp:
        kept, out, _ = run_filter(tmp, mp, rows)
    expected = [f"o{i}" for i, b in enumerate(bad) if not b]
    assert [r["doc_id"] for r in out] == expected and kept == len(expected)
