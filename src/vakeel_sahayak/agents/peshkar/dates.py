"""The List of Dates and Events (plan §7.2): one row per dated event, sorted by date, conflicts side by side.

Pure functions over timeline rows. A row keeps its source (document and page). Two rows that give different dates for
the same single-valued event (the arrest, the FIR, the charge sheet) are marked AMBIGUOUS and point at each other, and
are listed next to each other so counsel sees both; counsel's own edits (USER_EDITED) are never overridden.
"""

from __future__ import annotations

from vakeel_sahayak.ingestion.conflicts import detect_conflicts, mark_ambiguous
from vakeel_sahayak.ingestion.events import field_of_label
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.store_rows import TimelineEvent


def resolve_rows(rows: list[TimelineEvent]) -> tuple[list[TimelineEvent], list[tuple[str, list[str]]]]:
    """Rows with the conflict marks brought up to date, and the conflicts found.

    Args:
        rows: the timeline rows

    Returns:
        (rows, conflicts): every row, with AMBIGUOUS and `conflicts_with` set for events that disagree and cleared for
        events that no longer do; conflicts as (event field, event ids) pairs.
    """
    open_rows = [r for r in rows if r.status != FieldStatus.USER_EDITED]
    conflicts = detect_conflicts(open_rows)
    marked = {r.event_id: r for r in mark_ambiguous(open_rows, conflicts)}
    out: list[TimelineEvent] = []
    for row in rows:
        row = marked.get(row.event_id, row)
        if row.status == FieldStatus.AMBIGUOUS and row.event_id not in marked:  # a stale mark: the other side was corrected
            row = row.model_copy(update={"status": FieldStatus.VERIFIED, "conflicts_with": []})
        out.append(row)
    return out, conflicts


def side_by_side(rows: list[TimelineEvent]) -> list[TimelineEvent]:
    """Sort by date (then id) and move each event's conflicting partners directly after it."""
    ordered = sorted(rows, key=lambda r: (r.date, r.event_id))
    by_id = {r.event_id: r for r in ordered}
    out: list[TimelineEvent] = []
    placed: set[str] = set()
    for row in ordered:
        if row.event_id in placed:
            continue
        out.append(row)
        placed.add(row.event_id)
        for other in row.conflicts_with:
            partner = by_id.get(other)
            if partner is not None and other not in placed:
                out.append(partner)
                placed.add(other)
    return out


def event_field(row: TimelineEvent) -> str | None:
    """The event field a row dates ('arrest_date', 'first_remand', ...), or None for a label Peshkar does not know."""
    return field_of_label(row.label)
