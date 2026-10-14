"""Slot assessment rules (plan §6.2 step 2.3): court reasoning only, factor tag, section-family overlap, date before
the case. Items are paragraph dicts built from tests/fixtures/caselaw/paragraphs.json."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.agents._helpers import CASE_DATE, para_dict
from vakeel_sahayak.agents.sutradhar.slot_rules import assess_slot
from vakeel_sahayak.schemas.enums import Factor, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import SlotResult

FAMILY = ["BNS 318(4)", "IPC 420"]
PARITY = Factor.PARITY_WITH_CO_ACCUSED


@pytest.fixture()
def good(paragraphs):
    """DLHC-2022-1187#14: reasoning, parity tag, family overlap, dated 2022-06-03 (qualifies for parity)."""
    return para_dict(paragraphs, "DLHC-2022-1187", 14)


def variant(item: dict, **overrides) -> dict:
    """A derived paragraph (same shape, other doc/para/date/tags) used to build second qualifying items."""
    return {**item, **overrides}


def second(good: dict) -> dict:
    return variant(good, doc_id="DLHC-2021-0420", para=11, date="2021-03-10", factors=["parity_with_co_accused"])


def assess(items, need, factor=PARITY, family=FAMILY, case_date=CASE_DATE, slot="authority") -> SlotResult:
    return assess_slot(slot, items, need, case_date, factor, family)


def test_result_carries_slot_status_and_items(good):
    """The SlotResult names the slot, has a status and keeps the qualifying items."""
    result = assess([good, second(good)], 2)
    assert isinstance(result, SlotResult)
    assert result.slot == "authority"
    assert result.status == SlotStatus.FILLED
    assert {(i["doc_id"], i["para"]) for i in result.items} == {("DLHC-2022-1187", 14), ("DLHC-2021-0420", 11)}


def test_two_qualifying_items_fill_need_two(good):
    """need=2 with two court-reasoning, factor-tagged, family-overlapping, earlier items is FILLED."""
    assert assess([good, second(good)], 2).status == SlotStatus.FILLED


def test_one_qualifying_item_is_weak_one_of_two(good):
    """need=2 with only one qualifying item is WEAK and the note says '1 of 2' (plan §6.3 'WEAK (1 of 2)')."""
    result = assess([good], 2)
    assert result.status == SlotStatus.WEAK
    assert "1 of 2" in (result.note or "")


def test_no_items_is_missing(good):
    """No items at all is MISSING."""
    assert assess([], 2).status == SlotStatus.MISSING


def test_defense_submission_is_not_authority(paragraphs):
    """A defence-submissions paragraph is advocacy, not authority: it does not count (reasoning only)."""
    defence = para_dict(paragraphs, "DLHC-2022-1187", 9)
    assert defence["part"] == "defense_submissions"
    assert assess([defence], 1).status == SlotStatus.MISSING


def test_prosecution_submission_is_not_authority(paragraphs):
    """A prosecution-submissions paragraph does not count either."""
    prosecution = para_dict(paragraphs, "DLHC-2023-0911", 6)
    assert prosecution["part"] == "prosecution_submissions"
    assert assess([prosecution], 1).status == SlotStatus.MISSING


def test_submission_paragraph_does_not_help_a_reasoning_item_reach_the_need(good, paragraphs):
    """One reasoning item plus one defence paragraph is still '1 of 2'."""
    defence = para_dict(paragraphs, "DLHC-2022-1187", 9)
    result = assess([good, defence], 2)
    assert result.status == SlotStatus.WEAK
    assert "1 of 2" in (result.note or "")


def test_item_dated_after_the_case_does_not_count(paragraphs):
    """DLHC-2025-0099 (2025-03-01) is after the case date 2025-02-03 and never counts (leakage rule)."""
    late = para_dict(paragraphs, "DLHC-2025-0099", 5)
    assert late["date"] > CASE_DATE
    assert assess([late], 1).status == SlotStatus.MISSING


@pytest.mark.parametrize(
    "item_date, counts",
    [("2025-02-02", True), ("2025-02-03", False), ("2025-02-04", False)],
)
def test_date_boundary_is_strictly_before_the_case_date(good, item_date, counts):
    """Strictly before: an order dated on the case date itself does not count."""
    # ASSUMPTION: strict '<', consistent with the shared-store rule `date < before` used by the fakes.
    result = assess([variant(good, date=item_date)], 1)
    assert (result.status == SlotStatus.FILLED) == counts


def test_item_without_the_factor_tag_does_not_count(paragraphs):
    """DLHC-2021-0420#11 is tagged custody_period only: it does not count for parity."""
    custody = para_dict(paragraphs, "DLHC-2021-0420", 11)
    assert "parity_with_co_accused" not in custody["factors"]
    assert assess([custody], 1).status == SlotStatus.MISSING


def test_same_item_counts_for_the_factor_it_is_tagged_with(good):
    """DLHC-2022-1187#14 carries both parity and charge_sheet_filed: it serves both factors (shared results, plan §6.1)."""
    assert assess([good], 1, factor=Factor.CHARGE_SHEET_FILED).status == SlotStatus.FILLED
    assert assess([good], 1, factor=Factor.CUSTODY_PERIOD).status == SlotStatus.MISSING


def test_sole_item_without_family_overlap_is_weak_not_filled(good):
    """An otherwise good paragraph from another offence family cannot FILL the slot; it is only WEAK evidence."""
    # ASSUMPTION: wrong-family evidence is kept as WEAK support (widened family), never FILLED and not discarded.
    other = variant(good, section_family=["IPC 302", "BNS 103"], sections=["IPC 302"])
    assert assess([other], 1).status == SlotStatus.WEAK


def test_family_mismatch_item_does_not_count_towards_the_need(good):
    """With need=2, one overlapping item plus one wrong-family item stays WEAK."""
    other = variant(second(good), section_family=["IPC 302"], sections=["IPC 302"])
    assert assess([good, other], 2).status == SlotStatus.WEAK


@pytest.mark.parametrize("n_items, expected", [(0, SlotStatus.MISSING), (1, SlotStatus.FILLED), (2, SlotStatus.FILLED)])
def test_need_required_wants_at_least_one(good, n_items, expected):
    """need='required' needs >=1 qualifying item."""
    items = [good, second(good)][:n_items]
    assert assess(items, "required").status == expected


def test_need_optional_without_items_never_raises_and_is_missing():
    """need='optional' with nothing found does not raise; ASSUMPTION: status MISSING (the loop ignores optional slots)."""
    assert assess([], "optional").status == SlotStatus.MISSING


def test_need_optional_with_an_item_is_filled(good):
    """An optional slot with a qualifying item is FILLED."""
    assert assess([good], "optional").status == SlotStatus.FILLED


def test_extra_qualifying_items_beyond_the_need_are_fine(good):
    """More qualifying items than needed is still FILLED."""
    assert assess([good, second(good)], 1).status == SlotStatus.FILLED


@given(k=st.integers(0, 5), need=st.integers(1, 4), n_late=st.integers(0, 3))
def test_status_follows_the_count_of_qualifying_items(k, need, n_late):
    """Property: FILLED iff qualifying >= need, WEAK iff 0 < qualifying < need, MISSING iff none; non-qualifying
    (post-dated) items never change the outcome."""
    from tests.fakes.data import load_paragraphs

    base = para_dict(load_paragraphs(), "DLHC-2022-1187", 14)
    qualifying = [variant(base, doc_id=f"DLHC-2020-{i:04d}", para=i + 1, date="2020-01-01") for i in range(k)]
    late = [variant(base, doc_id=f"DLHC-2026-{i:04d}", para=i + 1, date="2026-01-01") for i in range(n_late)]
    status = assess(qualifying + late, need).status
    if k == 0:
        assert status == SlotStatus.MISSING
    elif k < need:
        assert status == SlotStatus.WEAK
    else:
        assert status == SlotStatus.FILLED
