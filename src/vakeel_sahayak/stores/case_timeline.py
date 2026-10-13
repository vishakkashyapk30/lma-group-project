"""case.timeline store: dated events with sources (tens of rows). Index: exact. (plan §5.1)"""

from __future__ import annotations

import sqlite3

from vakeel_sahayak.schemas.enums import Shelf, StoreName
from vakeel_sahayak.schemas.ids import check_case_id, check_iso_date
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.stores.base import CaseStore
from vakeel_sahayak.stores.case_sqlite import connect_case_db
from vakeel_sahayak.stores.paths import resolve_case_path


class TimelineStore(CaseStore):
    """case.timeline store: dated events with sources (tens of rows). Index: exact."""

    name = StoreName.CASE_TIMELINE
    shelf = Shelf.CASE
    index_kind = "exact"

    def __init__(self) -> None:
        """Create an unbound, unopened store."""
        self._case_id: str | None = None
        self._conn: sqlite3.Connection | None = None

    def open(self, path: str | None = None) -> None:
        """Open the store (creating it if new): table `timeline` of `case.sqlite` of the bound case.

        Args:
            path: file, folder, or ':memory:'; default data/cases/<case_id>/case.sqlite
        """
        if not self._case_id:
            raise ValueError("bind_case(case_id) before open()")
        self._conn = connect_case_db(resolve_case_path(self.name, self._case_id, path))

    def close(self) -> None:
        """Close."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def count(self) -> int:
        """Row count.

        Returns:
            Count.
        """
        return int(self._need().execute("SELECT COUNT(*) FROM timeline").fetchone()[0])

    def bind_case(self, case_id: str) -> None:
        """Select the case.

        Args:
            case_id: see behaviour
        """
        self._case_id = check_case_id(case_id)

    def _need(self) -> sqlite3.Connection:
        """The open connection (raises if the store was never opened)."""
        if self._conn is None:
            raise RuntimeError("case.timeline is not open")
        return self._conn

    def add_event(self, event: TimelineEvent) -> None:
        """Insert an event (an event with the same id is replaced).

        Args:
            event: see behaviour
        """
        conn = self._need()
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO timeline (event_id, date, payload) VALUES (?, ?, ?)",
                (event.event_id, event.date, event.model_dump_json()),
            )

    def get(self, start: str | None = None, end: str | None = None) -> list[TimelineEvent]:
        """Events sorted by date; conflicts side by side.

        Args:
            start: earliest ISO date (inclusive)
            end: latest ISO date (inclusive)

        Returns:
            Events by date then id; an event that conflicts with another is followed directly by the events it conflicts with.

        Raises:
            ValueError: for a malformed date.
        """
        sql, params = "SELECT payload FROM timeline", []
        conds = []
        if start:
            conds.append("date >= ?")
            params.append(check_iso_date(start))
        if end:
            conds.append("date <= ?")
            params.append(check_iso_date(end))
        sql += (" WHERE " + " AND ".join(conds) if conds else "") + " ORDER BY date, event_id"
        events = [TimelineEvent.model_validate_json(r[0]) for r in self._need().execute(sql, params)]
        return _conflicts_adjacent(events)


def _conflicts_adjacent(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Move each event's conflicting partners directly after it (dates differ, so sorting alone would separate them)."""
    by_id = {e.event_id: e for e in events}
    out: list[TimelineEvent] = []
    placed: set[str] = set()
    for event in events:
        if event.event_id in placed:
            continue
        out.append(event)
        placed.add(event.event_id)
        for other in event.conflicts_with:
            partner = by_id.get(other)
            if partner and other not in placed:
                out.append(partner)
                placed.add(other)
    return out
