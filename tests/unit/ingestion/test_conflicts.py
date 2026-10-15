"""Conflict handling between documents (plan §4.3 step 5): keep both values, pass them to Peshkar as AMBIGUOUS."""

from __future__ import annotations

from vakeel_sahayak.ingestion.conflicts import detect_conflicts
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.store_rows import TimelineEvent


def ev(event_id: str, date: str, label: str, doc: str = "d1") -> TimelineEvent:
    return TimelineEvent(event_id=event_id, date=date, label=label, source=SourceRef(doc=doc, page=1))


def test_two_arrest_dates_from_two_documents_conflict_and_keep_both_events():
    """Arrest 2024-08-20 (remand order) vs 2024-08-21 (FIR): one conflict on 'arrest' listing BOTH event ids."""
    timeline = [ev("e3", "2024-08-20", "Arrest", "d2"), ev("e9", "2024-08-21", "Arrest", "d1")]
    conflicts = detect_conflicts(timeline)
    assert len(conflicts) == 1
    field, ids = conflicts[0]
    # RECONCILED: the conflict names the dossier field ('arrest_date', plan §4.3 step 5 / §7.1), not the bare label,
    # so Peshkar can mark that field AMBIGUOUS without a second lookup.
    assert field == "arrest_date"
    assert sorted(ids) == ["e3", "e9"]


def test_detect_conflicts_does_not_drop_or_merge_events():
    """The input timeline is left untouched: both values stay available to Peshkar."""
    timeline = [ev("e3", "2024-08-20", "Arrest", "d2"), ev("e9", "2024-08-21", "Arrest", "d1")]
    before = [t.model_copy() for t in timeline]
    detect_conflicts(timeline)
    assert timeline == before


def test_consistent_timeline_has_no_conflicts(timeline):
    """The case-0007 timeline (one value per event) has no conflicts."""
    assert detect_conflicts(timeline) == []


def test_same_date_repeated_is_not_a_conflict():
    """The arrest date stated identically in two documents is agreement, not a conflict."""
    timeline = [ev("e3", "2024-08-20", "Arrest", "d2"), ev("e9", "2024-08-20", "Arrest", "d1")]
    assert detect_conflicts(timeline) == []


def test_different_events_on_different_dates_do_not_conflict():
    """Arrest on 08-20 and first remand on 08-21 are different fields, so nothing conflicts."""
    timeline = [ev("e3", "2024-08-20", "Arrest"), ev("e4", "2024-08-21", "First remand")]
    assert detect_conflicts(timeline) == []


def test_three_statements_two_agree_one_differs():
    """ASSUMPTION: when two documents agree and a third differs, the one conflict lists all three events."""
    timeline = [ev("a", "2024-08-20", "Arrest", "d1"), ev("b", "2024-08-20", "Arrest", "d2"), ev("c", "2024-08-22", "Arrest", "d3")]
    conflicts = detect_conflicts(timeline)
    assert len(conflicts) == 1 and sorted(conflicts[0][1]) == ["a", "b", "c"]


def test_two_independent_conflicts_are_reported_separately():
    """An arrest-date conflict and a charge-sheet-date conflict are two entries."""
    timeline = [
        ev("a1", "2024-08-20", "Arrest", "d1"), ev("a2", "2024-08-21", "Arrest", "d2"),
        ev("c1", "2024-11-02", "Charge sheet filed", "d3"), ev("c2", "2024-11-03", "Charge sheet filed", "d4"),
    ]
    conflicts = detect_conflicts(timeline)
    assert len(conflicts) == 2
    assert {tuple(sorted(ids)) for _, ids in conflicts} == {("a1", "a2"), ("c1", "c2")}
