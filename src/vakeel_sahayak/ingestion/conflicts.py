"""Conflict handling between documents (plan §4.3 step 5)."""

from __future__ import annotations

from vakeel_sahayak.ingestion.events import SINGLE_VALUED_FIELDS, field_of_label
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.store_rows import TimelineEvent

# Single-valued event fields that are also dossier fields holding one string (plan §7.1); the others stay on the timeline.
DOSSIER_FIELD = {"arrest_date": "arrest_date", "offence_date": "offence_date", "first_remand": "first_remand"}


def detect_conflicts(timeline: list[TimelineEvent]) -> list[tuple[str, list[str]]]:
    """Find fields where documents disagree (e.g. arrest date); keep both values and pass to Peshkar as AMBIGUOUS.

    Only single-valued fields can conflict (arrest, FIR, charge-sheet, offence and first-remand dates); several
    remands or bail outcomes are normal. Events with the same date agree.

    Args:
        timeline: see behaviour

    Returns:
        (field, event ids) pairs, ids in date order.
    """
    by_field: dict[str, list[TimelineEvent]] = {}
    for event in timeline:
        field = field_of_label(event.label)
        if field in SINGLE_VALUED_FIELDS:
            by_field.setdefault(field, []).append(event)
    out: list[tuple[str, list[str]]] = []
    for field, events in by_field.items():
        if len({e.date for e in events}) > 1:
            out.append((field, [e.event_id for e in sorted(events, key=lambda e: (e.date, e.event_id))]))
    return out


def mark_ambiguous(timeline: list[TimelineEvent], conflicts: list[tuple[str, list[str]]]) -> list[TimelineEvent]:
    """Copies of the conflicting events with status AMBIGUOUS and `conflicts_with` naming the others; both values are kept.

    Args:
        timeline: the events
        conflicts: output of `detect_conflicts`

    Returns:
        The changed events only.
    """
    by_id = {e.event_id: e for e in timeline}
    changed: list[TimelineEvent] = []
    for _field, ids in conflicts:
        for event_id in ids:
            event = by_id[event_id]
            others = sorted({*event.conflicts_with, *(i for i in ids if i != event_id)})
            changed.append(event.model_copy(update={"status": FieldStatus.AMBIGUOUS, "conflicts_with": others}))
    return changed
