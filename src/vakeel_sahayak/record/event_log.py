"""SQLite-backed append-only event log (plan §3.3)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.ids import new_event_id, utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id  TEXT NOT NULL UNIQUE,
    case_id   TEXT NOT NULL,
    ts        TEXT NOT NULL,
    kind      TEXT NOT NULL,
    actor     TEXT NOT NULL,
    tool      TEXT,
    parent_id TEXT,
    body      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_case ON events (case_id, seq);
CREATE INDEX IF NOT EXISTS ix_events_parent ON events (parent_id);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'event log is append-only'); END;
"""

_APPROVAL_KINDS = (EventKind.GATE_APPROVED, EventKind.CHANGE_SET_APPROVED)


class ApprovalNotFromCounsel(PermissionError):
    """Raised when something other than counsel tries to append an approval event (plan §3.1, §16)."""


class EventLog:
    """Append-only SQLite event log; every agent action is an Event (plan §3.3). Logs hold pseudonymised text only (plan §16).

    Append-only is enforced twice: this class has no update or delete method, and SQLite triggers abort any
    UPDATE or DELETE. Reopening a file continues the same log, so an interrupted run can resume (plan §17).
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Open or create the log.

        Args:
            db_path: SQLite file; one per case on the laptop. None keeps the log in memory.
        """
        self.db_path = db_path or ":memory:"
        if db_path:
            Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        if db_path:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @classmethod
    def for_case(cls, case_id: str, data_dir: str | None = None) -> EventLog:
        """Open the log of one case at <cases_dir>/<case_id>/events.sqlite (configs/stores.yaml `event_log`).

        Args:
            case_id: validated case id
            data_dir: override of the cases directory

        Returns:
            The case's event log.
        """
        from vakeel_sahayak.config import load_config
        from vakeel_sahayak.schemas.ids import check_case_id

        check_case_id(case_id)
        cfg = load_config()
        template = (cfg.stores.get("event_log") or {}).get("path", "cases/{case_id}/events.sqlite")
        rel = template.format(case_id=case_id).removeprefix("cases/")
        base = Path(data_dir or cfg.paths.cases_dir)
        return cls(str(base / rel))

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    def append(self, event: Event) -> Event:
        """Append one event (assigns id/time if missing). Re-appending an existing event_id is a no-op, so replays are safe.

        Args:
            event: the event to append

        Returns:
            The stored event.

        Raises:
            ApprovalNotFromCounsel: for GATE_APPROVED / CHANGE_SET_APPROVED events whose actor is not counsel.
        """
        if event.kind in _APPROVAL_KINDS and str(getattr(event.actor, "value", event.actor)) != COUNSEL:
            raise ApprovalNotFromCounsel(f"{event.kind.value} may only be recorded by counsel, not {event.actor!r}")
        updates: dict[str, str] = {}
        if not event.event_id:
            updates["event_id"] = new_event_id()
        if not event.ts:
            updates["ts"] = utc_now()
        if updates:
            event = event.model_copy(update=updates)
        actor = str(getattr(event.actor, "value", event.actor))
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO events (event_id, case_id, ts, kind, actor, tool, parent_id, body) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.case_id,
                    event.ts,
                    event.kind.value,
                    actor,
                    event.tool,
                    event.parent_id,
                    event.model_dump_json(),
                ),
            )
        stored = self.get(event.event_id)
        assert stored is not None
        return stored

    def get(self, event_id: str) -> Event | None:
        """Fetch one event by id.

        Args:
            event_id: see behaviour

        Returns:
            The event or None.
        """
        with self._lock:
            row = self._conn.execute("SELECT body FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return _decode(row) if row else None

    def read(
        self, case_id: str, kind: EventKind | None = None, actor: str | None = None, since: str | None = None
    ) -> list[Event]:
        """Read events for a case in order.

        Args:
            case_id: see behaviour
            kind: filter by kind
            actor: filter by actor
            since: ISO time lower bound (inclusive)

        Returns:
            Matching events.
        """
        return [e for _, e in self._read_rows(case_id, kind=kind, actor=actor, since=since)]

    def read_after(self, case_id: str, event_id: str | None) -> list[Event]:
        """Events of a case appended after `event_id` (all of them if None); used to resume from a checkpoint.

        Args:
            case_id: see behaviour
            event_id: last event already processed

        Returns:
            Later events in order.
        """
        after = self.seq_of(event_id) if event_id else 0
        return [e for _, e in self._read_rows(case_id, after_seq=after or 0)]

    def seq_of(self, event_id: str) -> int | None:
        """Position of an event in the log (monotone, gap-free per file), or None if unknown."""
        with self._lock:
            row = self._conn.execute("SELECT seq FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return int(row["seq"]) if row else None

    def last(self, case_id: str) -> Event | None:
        """Most recent event of a case."""
        with self._lock:
            row = self._conn.execute(
                "SELECT body FROM events WHERE case_id = ? ORDER BY seq DESC LIMIT 1", (case_id,)
            ).fetchone()
        return _decode(row) if row else None

    def children(self, event_id: str) -> list[Event]:
        """Events causally downstream of one event (used by truth maintenance, plan §10).

        Args:
            event_id: root event

        Returns:
            Descendant events (children, grandchildren, ...) in log order.
        """
        sql = (
            "WITH RECURSIVE down(id) AS (SELECT event_id FROM events WHERE parent_id = ? "
            "UNION SELECT e.event_id FROM events e JOIN down d ON e.parent_id = d.id) "
            "SELECT body FROM events WHERE event_id IN (SELECT id FROM down) ORDER BY seq"
        )
        with self._lock:
            rows = self._conn.execute(sql, (event_id,)).fetchall()
        return [_decode(r) for r in rows]

    def subscribe(
        self,
        case_id: str,
        from_start: bool = False,
        poll_interval: float = 0.2,
        idle_timeout: float | None = None,
    ) -> Iterator[Event]:
        """Yield new events as they arrive; feeds the SSE route and the live agent trace (plan §3.3).

        Args:
            case_id: see behaviour
            from_start: also replay the events already in the log
            poll_interval: seconds between polls of the database
            idle_timeout: stop after this many seconds without a new event (None waits forever)

        Returns:
            An event iterator.
        """
        with self._lock:
            row = self._conn.execute("SELECT MAX(seq) AS m FROM events WHERE case_id = ?", (case_id,)).fetchone()
        cursor = 0 if from_start else int(row["m"] or 0)
        idle_since = time.monotonic()
        while True:
            batch = self._read_rows(case_id, after_seq=cursor)
            if batch:
                idle_since = time.monotonic()
                for seq, event in batch:
                    cursor = seq
                    yield event
            elif idle_timeout is not None and time.monotonic() - idle_since >= idle_timeout:
                return
            else:
                time.sleep(poll_interval)

    def _read_rows(
        self,
        case_id: str,
        kind: EventKind | None = None,
        actor: str | None = None,
        since: str | None = None,
        after_seq: int = 0,
    ) -> list[tuple[int, Event]]:
        """Run the filtered SELECT shared by read, read_after and subscribe."""
        clauses, params = ["case_id = ?", "seq > ?"], [case_id, after_seq]
        if kind is not None:
            clauses.append("kind = ?")
            params.append(EventKind(kind).value)
        if actor is not None:
            clauses.append("actor = ?")
            params.append(str(getattr(actor, "value", actor)))
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        sql = f"SELECT seq, body FROM events WHERE {' AND '.join(clauses)} ORDER BY seq"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [(int(r["seq"]), _decode(r)) for r in rows]


def _decode(row: sqlite3.Row) -> Event:
    """Rebuild an Event from its stored JSON body."""
    return Event.model_validate(json.loads(row["body"]))
