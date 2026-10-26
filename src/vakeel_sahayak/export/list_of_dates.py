"""List of Dates and Events built from case.timeline (plan §7.2).

Every date in an exported application comes from `case.timeline` with its source; a model never writes a date (plan §8.2).
Rows are plain strings so the same rows feed the application, the standalone List of Dates and the F5 check (plan §15.6).
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.export.docx_style import court_date, heading, new_document, paragraph, table
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.store_rows import TimelineEvent

_ISO_IN_TEXT = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def source_text(source: SourceRef | None) -> str:
    """'d2 (remand order), p.4'; 'computed (date_calc)' for a tool value; '' when the event has no source."""
    if source is None:
        return ""
    if source.doc:
        return f"{source.doc}, p.{source.page}" if source.page is not None else source.doc
    if source.tool:
        return f"computed ({source.tool})"
    if source.chat:
        return f"stated by counsel ({source.chat})"
    return ""


def build_list_of_dates(timeline: list[TimelineEvent]) -> list[dict[str, str]]:
    """One row per dated event, sorted, with source (document, page); conflicting dates side by side.

    Args:
        timeline: the case's dated events, in any order

    Returns:
        Rows {date (ISO), event, source, conflict}. `conflict` names the other dates of an event that documents disagree on,
        and those rows sit next to each other; it is '' otherwise.
    """
    by_id = {e.event_id: e for e in timeline}
    ordered = sorted(timeline, key=lambda e: (e.date, e.event_id))
    rows: list[dict[str, str]] = []
    placed: set[str] = set()
    for event in ordered:
        if event.event_id in placed:
            continue
        group = [event] + sorted((by_id[c] for c in event.conflicts_with if c in by_id and c not in placed), key=lambda e: (e.date, e.event_id))
        for e in group:
            placed.add(e.event_id)
            others = [by_id[c] for c in e.conflicts_with if c in by_id]
            rows.append({
                "date": e.date,
                "event": e.label,
                "source": source_text(e.source),
                "conflict": "; ".join(f"{o.date} ({source_text(o.source) or 'no source'})" for o in others),
            })  # fmt: skip
    return rows


def table_rows(rows: list[dict[str, str]]) -> list[list[str]]:
    """The rows as table cells: dd.mm.yyyy date, the event (with a conflict note), the source or a visible gap."""
    out = []
    for r in rows:
        event = r["event"]
        if r.get("conflict"):
            event += f" (documents disagree; also recorded as {_ISO_IN_TEXT.sub(lambda m: court_date(m.group(0)), r['conflict'])})"
        out.append([court_date(r["date"]), event, r["source"] or "No source on record"])
    return out


def add_list_of_dates(doc: Any, rows: list[dict[str, str]]) -> None:
    """The List of Dates table, or a line saying there are no dated events."""
    if rows:
        table(doc, ["Date", "Event", "Source"], table_rows(rows), widths_cm=[3.0, 8.5, 4.5])
    else:
        paragraph(doc, "No dated events are on record.", italic=True)


def write_list_of_dates_docx(timeline: list[TimelineEvent], case_id: str, out_path: str) -> str:
    """The List of Dates and Events as its own DOCX (plan §7.2), for the export bundle.

    Args:
        timeline: the case's dated events
        case_id: the case (shown in the heading; names stay pseudonymised)
        out_path: where to write the file

    Returns:
        out_path.
    """
    doc = new_document(title=f"List of Dates and Events, {case_id}")
    heading(doc, "LIST OF DATES AND EVENTS", size=14, space_before=0)
    paragraph(doc, f"Case {case_id}. Every date below is taken from the case record with the document and page it comes from.", italic=True)
    add_list_of_dates(doc, build_list_of_dates(timeline))
    doc.save(out_path)
    return out_path
