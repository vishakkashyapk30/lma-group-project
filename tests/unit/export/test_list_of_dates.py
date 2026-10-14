"""List of Dates and Events (plan §7.2, §8.2): built from `case.timeline`, one row per dated event with its source (document and
page), sorted by date, conflicting dates side by side. Every date in the exported application comes from `case.timeline`.

ASSUMPTION (rows are `dict[str, str]`, keys not fixed by the plan): `date` (ISO), `event` (the label), `source`
(document and page, e.g. 'd2 (remand order), p.4'; empty when the event has no source) and, for events that conflict with
another, a non-empty `conflict` value naming the other date. ASSUMPTION: conflicting rows are adjacent.
"""

from __future__ import annotations

import pytest

from vakeel_sahayak.export.list_of_dates import build_list_of_dates
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.store_rows import TimelineEvent

EXPECTED_ISO = ["2024-08-10", "2024-08-14", "2024-08-20", "2024-08-21", "2024-09-30", "2024-11-02", "2024-12-05"]
EXPECTED_LABELS = ["Offence", "FIR registered", "Arrest", "First remand", "Sessions Court rejected bail", "Charge sheet filed",
                   "Co-accused-1 granted bail"]


def test_case_0007_has_one_row_per_timeline_event(timeline):
    """Seven events in case-0007's timeline give seven rows."""
    assert len(build_list_of_dates(timeline)) == len(timeline) == 7


def test_rows_are_the_timeline_dates_in_order(timeline):
    """Dates and labels are exactly those of the timeline (nothing invented, nothing dropped), oldest first."""
    rows = build_list_of_dates(timeline)
    assert [r["date"] for r in rows] == EXPECTED_ISO
    assert [r["event"] for r in rows] == EXPECTED_LABELS


def test_rows_are_sorted_even_when_the_timeline_is_not(timeline):
    """An unsorted timeline (events filed in the order pages were read) still yields ascending dates."""
    rows = build_list_of_dates(list(reversed(timeline)))
    assert [r["date"] for r in rows] == EXPECTED_ISO


def test_every_row_names_its_source_document_and_page(timeline):
    """Plan §7.2: each row has its source (document and page): the arrest is 'd2 (remand order)' page 4."""
    rows = {r["event"]: r for r in build_list_of_dates(timeline)}
    assert "d2" in rows["Arrest"]["source"] and "4" in rows["Arrest"]["source"]
    assert "d4" in rows["Charge sheet filed"]["source"] and "9" in rows["Charge sheet filed"]["source"]
    assert "d5" in rows["Co-accused-1 granted bail"]["source"] and "12" in rows["Co-accused-1 granted bail"]["source"]
    assert all(r["source"] for r in rows.values())


def test_event_without_a_source_is_visible_as_such():
    """F5 counts 'dates without a source' (plan §15.6): a sourceless event keeps an empty source so it can be flagged."""
    rows = build_list_of_dates([TimelineEvent(event_id="x1", date="2024-08-20", label="Arrest", source=None)])
    assert rows[0]["date"] == "2024-08-20" and not rows[0]["source"].strip()


def test_conflicting_dates_are_shown_side_by_side():
    """Two documents disagree on the arrest date: both rows appear, adjacent, each marked as in conflict (plan §7.2)."""
    ev = [
        TimelineEvent(event_id="e3", date="2024-08-20", label="Arrest", source=SourceRef(doc="d2", page=4), conflicts_with=["e3b"],
                      status=FieldStatus.AMBIGUOUS),
        TimelineEvent(event_id="e0", date="2024-08-10", label="Offence", source=SourceRef(doc="d1", page=1)),
        TimelineEvent(event_id="e3b", date="2024-08-22", label="Arrest", source=SourceRef(doc="d3", page=6), conflicts_with=["e3"],
                      status=FieldStatus.AMBIGUOUS),
    ]
    rows = build_list_of_dates(ev)
    arrests = [i for i, r in enumerate(rows) if r["event"] == "Arrest"]
    assert len(arrests) == 2 and arrests[1] - arrests[0] == 1
    assert all(rows[i].get("conflict") for i in arrests)
    assert "2024-08-22" in rows[arrests[0]]["conflict"] and "2024-08-20" in rows[arrests[1]]["conflict"]
    assert not rows[0].get("conflict")


def test_empty_timeline_gives_no_rows():
    assert build_list_of_dates([]) == []


def test_rows_are_strings(timeline):
    """The return type is list[dict[str, str]]."""
    for row in build_list_of_dates(timeline):
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in row.items())


def test_building_does_not_mutate_the_timeline(timeline):
    before = [e.model_dump() for e in timeline]
    build_list_of_dates(timeline)
    assert [e.model_dump() for e in timeline] == before


@pytest.mark.parametrize(("iso", "label"), list(zip(EXPECTED_ISO, EXPECTED_LABELS)))
def test_each_row_pairs_the_right_label_with_the_right_date(timeline, iso, label):
    """Row-level check on case-0007: 02.11.2024 is the charge sheet, 21.08.2024 the first remand, and so on."""
    rows = {r["date"]: r["event"] for r in build_list_of_dates(timeline)}
    assert rows[iso] == label
