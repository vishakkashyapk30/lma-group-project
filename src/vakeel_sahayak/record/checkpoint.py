"""SQLite checkpointer for resume after an interrupted run (plan §3.3, §17).

The plan wires LangGraph's SqliteSaver here (thread id = case id) and names a plain state machine as the fallback.
`Checkpointer` serves both on one SQLite file: when langgraph's SQLite saver is installed, the saver API (`put`,
`get_tuple`, `list`, ...) is delegated to a `SqliteSaver` on the same connection; the dependency-free `save` / `latest`
store keeps a JSON-able graph state per case with the id of the last event it includes, so a resumed run restores the
state and replays only the events after it.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.ids import utc_now

_SCHEMA = """
CREATE TABLE IF NOT EXISTS state_snapshots (  -- (langgraph's saver owns the tables 'checkpoints' and 'writes')
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       TEXT NOT NULL,
    ts            TEXT NOT NULL,
    last_event_id TEXT,
    state         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_snapshots_case ON state_snapshots (case_id, seq);
"""


class Checkpointer:
    """Append-only checkpoint store; the latest row of a case is its resume point."""

    def __init__(self, path: str | None = None) -> None:
        """Open or create the checkpoint file (':memory:' when path is None)."""
        self.path = path or ":memory:"
        if path:
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        if path:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._saver: Any = None
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            self._saver = SqliteSaver(self._conn)
        except ImportError:  # langgraph-checkpoint-sqlite is optional: the plain state machine needs only save/latest
            pass

    def __getattr__(self, name: str) -> Any:
        """The LangGraph saver API (`put`, `get_tuple`, `list`, `put_writes`, ...) of the underlying SqliteSaver."""
        saver = self.__dict__.get("_saver")
        if saver is None or name.startswith("__"):
            raise AttributeError(name)
        return getattr(saver, name)

    def save(self, case_id: str, state: dict[str, Any], last_event_id: str | None = None) -> int:
        """Store a state snapshot (state must be JSON-serialisable).

        Args:
            case_id: see behaviour
            state: graph state
            last_event_id: last event already reflected in `state`

        Returns:
            The checkpoint's sequence number.
        """
        blob = json.dumps(state, default=str, ensure_ascii=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO state_snapshots (case_id, ts, last_event_id, state) VALUES (?, ?, ?, ?)",
                (case_id, utc_now(), last_event_id, blob),
            )
        return int(cur.lastrowid or 0)

    def latest(self, case_id: str) -> tuple[dict[str, Any], str | None] | None:
        """Latest snapshot and its last_event_id, or None if the case never checkpointed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT state, last_event_id FROM state_snapshots WHERE case_id = ? ORDER BY seq DESC LIMIT 1", (case_id,)
            ).fetchone()
        return (json.loads(row["state"]), row["last_event_id"]) if row else None

    def count(self, case_id: str) -> int:
        """Number of snapshots stored for a case."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM state_snapshots WHERE case_id = ?", (case_id,)).fetchone()
        return int(row["n"])

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()


def open_checkpointer(path: str | None = None) -> Checkpointer:
    """Create the SQLite checkpointer used to resume after an Ada session ends (plan §3.3).

    Args:
        path: SQLite file; None keeps it in memory

    Returns:
        A checkpointer object.
    """
    return Checkpointer(path)


def resume_state(case_id: str, checkpointer: Checkpointer) -> dict[str, Any]:
    """Load the latest graph state for a case so interrupted work (a session cut at 6 h) resumes (plan §17).

    Args:
        case_id: see behaviour
        checkpointer: see behaviour

    Returns:
        Graph state; an empty dict for a case that never checkpointed.
    """
    saver = checkpointer.__dict__.get("_saver")
    if saver is not None:  # LangGraph's thread id is the case id
        tup = saver.get_tuple({"configurable": {"thread_id": case_id, "checkpoint_ns": ""}})
        if tup is not None:
            return dict(tup.checkpoint.get("channel_values") or {})
    found = checkpointer.latest(case_id)
    return found[0] if found else {}


def checkpoint_case(case_id: str, state: dict[str, Any], log: EventLog, checkpointer: Checkpointer) -> int:
    """Save `state` tagged with the log's latest event, so resume knows where the state ends."""
    last = log.last(case_id)
    return checkpointer.save(case_id, state, last.event_id if last else None)


def events_since_checkpoint(case_id: str, log: EventLog, checkpointer: Checkpointer) -> list[Event]:
    """Events appended after the latest checkpoint (all events if there is none); replay these on resume."""
    found = checkpointer.latest(case_id)
    return log.read_after(case_id, found[1] if found else None)
