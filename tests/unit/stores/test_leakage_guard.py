"""Run-time leakage guard (plan §2: 'At run time, every query only sees documents dated before the case's order').

apply_before_filter(filters, before) adds the date constraint to a store query's filters and raises if the date is absent.
ASSUMPTION: the result's key name for the constraint is not fixed by the plan, so tests only require the date string to appear
somewhere in the result's keys or values. ASSUMPTION: a missing or empty `before` raises ValueError (as the in-memory fakes do).
"""

from __future__ import annotations

import copy

import pytest

from vakeel_sahayak.stores.leakage_guard import apply_before_filter


def flatten(obj) -> str:
    return repr(obj)


@pytest.mark.parametrize("before", ["2025-02-03", "2022-06-03", "2024-12-31"])
def test_before_date_is_added_to_filters(before):
    """The returned filters carry the before date."""
    out = apply_before_filter({"factor": "parity_with_co_accused"}, before)
    assert before in flatten(out)


def test_existing_filters_are_preserved():
    """Other filters (factor, outcome, court) survive unchanged in the result."""
    filters = {"factor": "parity_with_co_accused", "outcome": "granted", "court": "Delhi HC"}
    out = apply_before_filter(filters, "2025-02-03")
    for k, v in filters.items():
        assert out[k] == v


def test_original_filters_not_mutated():
    """The caller's dict is not mutated (a copy is returned)."""
    filters = {"outcome": "granted"}
    snapshot = copy.deepcopy(filters)
    out = apply_before_filter(filters, "2025-02-03")
    assert filters == snapshot
    assert out is not filters
    assert out != snapshot


def test_empty_filters_still_get_the_date():
    """An empty filter dict is valid input and comes back constrained."""
    out = apply_before_filter({}, "2025-02-03")
    assert "2025-02-03" in flatten(out)


def test_nested_filters_not_mutated():
    """Nested values (lists) of the input are not modified either."""
    filters = {"section_family": ["IPC 420", "BNS 318(4)"]}
    snapshot = copy.deepcopy(filters)
    apply_before_filter(filters, "2025-02-03")
    assert filters == snapshot


@pytest.mark.parametrize("before", [None, "", "   "])
def test_missing_or_empty_before_raises(before):
    """A query without a before date is refused (ValueError)."""
    with pytest.raises(ValueError):
        apply_before_filter({"outcome": "granted"}, before)


def test_applying_twice_with_different_dates_keeps_the_stricter_visible():
    """Re-applying with an earlier date yields a result containing that earlier date (no silent widening)."""
    first = apply_before_filter({}, "2025-02-03")
    second = apply_before_filter(first, "2023-01-01")
    assert "2023-01-01" in flatten(second)
