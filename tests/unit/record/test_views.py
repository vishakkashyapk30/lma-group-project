"""record/views: pure folds from events to the dossier, timeline and audit trail (plan §3.3, §7.1, §7.2).

The dossier, timeline, brief and sparring record are views computed from the event log, never stored truth. Fixture:
tests/fixtures/case_0007/events.jsonl (payload shape documented there and in tests/unit/record/_helpers.py).
Expected values from plan §7.1: arrest 2024-08-20 VERIFIED, first remand 2024-08-21 VERIFIED, custody 167 days COMPUTED.
"""

from __future__ import annotations

import inspect


from tests.unit.record._helpers import field_write, make_event
from vakeel_sahayak.record import views
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import EventKind, FieldStatus


def test_fold_function_signatures():
    """Folds take a list of Events; views is a pure module (no log handle)."""
    for name in ("fold_dossier", "fold_timeline", "audit_trail"):
        assert list(inspect.signature(getattr(views, name)).parameters) == ["events"], name


# ---------------------------------------------------------------------------------------------------------------------
# fold_dossier
# ---------------------------------------------------------------------------------------------------------------------
def test_fold_dossier_arrest_date_is_verified_with_source(sample_events):
    """arrest_date folds to '2024-08-20', VERIFIED, with the remand-order quote as source."""
    d = views.fold_dossier(sample_events)
    assert isinstance(d, CaseDossier)
    f = d.fields.arrest_date
    assert (f.value, f.status) == ("2024-08-20", FieldStatus.VERIFIED)
    assert f.source.doc == "d2 (remand order)" and f.source.page == 4
    assert f.source.quote == "...arrested on 20.08.2024..."


def test_fold_dossier_first_remand_verified(sample_events):
    """first_remand folds to '2024-08-21', VERIFIED."""
    f = views.fold_dossier(sample_events).fields.first_remand
    assert (f.value, f.status) == ("2024-08-21", FieldStatus.VERIFIED)


def test_fold_dossier_custody_days_is_computed_by_date_calc(sample_events):
    """custody_days folds to 167, COMPUTED, source tool date_calc (plan §7.1)."""
    f = views.fold_dossier(sample_events).fields.custody_days
    assert (f.value, f.status) == (167, FieldStatus.COMPUTED)
    assert f.source.tool == "date_calc"


def test_fold_dossier_case_id_and_unwritten_fields_default_to_unsupported(sample_events):
    """case_id comes from the events; a field no event wrote stays an UNSUPPORTED empty TrackedField."""
    d = views.fold_dossier(sample_events)
    assert d.case_id == "case-0007"
    assert d.fields.antecedents.value is None
    assert d.fields.antecedents.status == FieldStatus.UNSUPPORTED


def test_fold_dossier_ignores_non_store_write_events(sample_events):
    """Only STORE_WRITE events to case.facts change the dossier: dropping all other events gives the same view."""
    only_facts = [e for e in sample_events if e.kind == EventKind.STORE_WRITE and e.inputs.get("store") == "case.facts"]
    assert views.fold_dossier(only_facts) == views.fold_dossier(sample_events)
    assert len(only_facts) == 3


def test_fold_dossier_last_write_wins(sample_events):
    """A later write to the same field replaces the earlier one (counsel edit after extraction)."""
    edit = {"value": "2024-08-19", "source": {"chat": "turn 3"}, "status": "USER_EDITED"}
    events = [*sample_events, field_write("case-0007", "arrest_date", edit, actor="counsel")]
    f = views.fold_dossier(events).fields.arrest_date
    assert (f.value, f.status) == ("2024-08-19", FieldStatus.USER_EDITED)


def test_fold_dossier_is_pure_and_deterministic(sample_events):
    """Folding twice gives equal dossiers and does not mutate the input events."""
    snapshot = [e.model_dump() for e in sample_events]
    assert views.fold_dossier(sample_events) == views.fold_dossier(sample_events)
    assert [e.model_dump() for e in sample_events] == snapshot


def test_fold_dossier_full_roundtrip_equals_fixture_dossier(dossier):
    """Events that write every field of the fixture dossier fold back to exactly that dossier's fields."""
    from tests.unit.record._helpers import dossier_events

    folded = views.fold_dossier(dossier_events(dossier.case_id, dossier))
    assert folded.fields == dossier.fields


# ---------------------------------------------------------------------------------------------------------------------
# fold_timeline
# ---------------------------------------------------------------------------------------------------------------------
def test_fold_timeline_returns_the_three_filed_events_sorted_by_date(sample_events):
    """The fixture files three timeline events: Arrest 2024-08-20, First remand 2024-08-21, Charge sheet 2024-11-02."""
    tl = views.fold_timeline(sample_events)
    assert [(e.event_id, e.date, e.label) for e in tl] == [
        ("e3", "2024-08-20", "Arrest"),
        ("e4", "2024-08-21", "First remand"),
        ("e6", "2024-11-02", "Charge sheet filed"),
    ]
    assert all(e.status == FieldStatus.VERIFIED for e in tl)
    assert tl[0].source.doc == "d2 (remand order)" and tl[0].source.page == 4


def test_fold_timeline_sorts_by_date_not_by_event_order(sample_events):
    """Reversing the event order still gives date order."""
    tl = views.fold_timeline(list(reversed(sample_events)))
    assert [e.date for e in tl] == ["2024-08-20", "2024-08-21", "2024-11-02"]


def test_fold_timeline_empty_without_timeline_writes():
    """No case.timeline writes means an empty timeline."""
    assert views.fold_timeline([make_event(kind=EventKind.AGENT_MESSAGE)]) == []
    assert views.fold_timeline([]) == []


# ---------------------------------------------------------------------------------------------------------------------
# audit_trail
# ---------------------------------------------------------------------------------------------------------------------
def test_audit_trail_has_one_row_per_event_in_order(sample_events):
    """The audit trail lists every event, in log order (plan §3.3 use 1)."""
    rows = views.audit_trail(sample_events)
    assert len(rows) == len(sample_events) == 17
    assert [r["time"] for r in rows] == [e.ts for e in sample_events]
    assert [r["tool"] for r in rows][:3] == ["inspect_page", "inspect_page", "file_item"]


def test_audit_trail_rows_carry_actor_tool_sources_and_time(sample_events):
    """Each row states who acted, which tool, the sources and the time (ASSUMPTION: keys actor, tool, sources, time)."""
    rows = views.audit_trail(sample_events)
    for row, ev in zip(rows, sample_events, strict=True):
        assert {"actor", "tool", "sources", "time"} <= set(row), row
        assert str(getattr(row["actor"], "value", row["actor"])) == str(getattr(ev.actor, "value", ev.actor))
        assert row["tool"] == ev.tool
        assert row["time"] == ev.ts
        assert len(row["sources"]) == len(ev.sources)


def test_audit_trail_surfaces_source_quote(sample_events):
    """The arrest write's row exposes its source document and quote so a lawyer can trace it."""
    row = views.audit_trail(sample_events)[2]  # ev003, the Arrest timeline write
    assert row["actor"] in ("MUNSHI", sample_events[2].actor)
    assert row["tool"] == "file_item"
    assert "...arrested on 20.08.2024..." in str(row["sources"])
    assert "d2 (remand order)" in str(row["sources"])


def test_audit_trail_order_follows_input_order():
    """Rows are not re-sorted: input order is preserved (the log is already in order)."""
    evs = [
        make_event(event_id="b", ts="2025-02-03T09:02:00Z", actor="MUNSHI", tool="t1"),
        make_event(event_id="a", ts="2025-02-03T09:01:00Z", actor="PESHKAR", tool="t2"),
    ]
    assert [r["tool"] for r in views.audit_trail(evs)] == ["t1", "t2"]


def test_audit_trail_empty():
    """No events give no rows."""
    assert views.audit_trail([]) == []
