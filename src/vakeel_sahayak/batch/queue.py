"""Persistent job queue for the batch desk (plan §11, §17).

A SQLite file holds every uploaded file (one case each: a PDF, a zip or a case folder) and two jobs per case, `stage1`
(Munshi + Peshkar + Rights Radar, cheap) and `stage2` (the full brief). The file is the only state, so a session that
ends, or is killed, resumes by opening it again:

- **Idempotent**: enqueueing the same path again returns its case id and adds nothing; enqueueing a stage-2 job twice
  is one job; finishing a job twice keeps the first result.
- **Claim and lease**: `claim` marks a job taken for `lease_seconds`. A job whose lease ran out (the worker died) can be
  claimed again; a claim counts as an attempt, so a job that keeps killing its worker stops at `max_attempts` and is
  `failed` rather than retried forever. `release` hands a job back without costing an attempt (a clean interrupt).
- **Crash-safe**: WAL mode, one transaction per change (`BEGIN IMMEDIATE`), each case's result stored in the same
  transaction that marks it done, so a case is either fully done or still waiting. Nothing is held in memory.

Statuses of a job: queued, claimed, done, failed, skipped. Every case has both jobs from the start; the scheduler marks
a case's stage-2 job `skipped` while it should not get a full run (documents missing) and queues it again when that
changes. Stage 2 is claimed in urgency-rank order.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pydantic_core import to_jsonable_python

STAGE1, STAGE2 = "stage1", "stage2"
QUEUED, CLAIMED, DONE, FAILED, SKIPPED = "queued", "claimed", "done", "failed", "skipped"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LEASE_SECONDS = 900.0
DEFAULT_CASE_HOURS = 0.25  # GPU-hours one full run is planned at, until the case says otherwise

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    seq INTEGER NOT NULL,
    decision TEXT,
    urgency_rank INTEGER,
    est_hours REAL NOT NULL DEFAULT 0.25
);
CREATE TABLE IF NOT EXISTS jobs (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until REAL,
    owner TEXT,
    result TEXT,
    error TEXT,
    updated REAL NOT NULL,
    PRIMARY KEY (case_id, phase)
);
"""


def default_queue_path() -> str:
    """The desk's queue file: `batch/queue.sqlite` under the configured data directory, so a restarted session finds the same queue."""
    from vakeel_sahayak.config import load_config

    return os.path.join(load_config().paths.data_dir, "batch", "queue.sqlite")


class TriageQueue:
    """Queue of files and full-run jobs; each case's output saved as soon as it is done so sessions resume (plan §11, §17)."""

    def __init__(
        self,
        db_path: str | None = None,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Open or create the queue.

        Args:
            db_path: SQLite file holding queued and finished cases, so a session that ends resumes (plan §11, §17); None opens the desk's own
                file, `batch/queue.sqlite` under the data directory (`VS_DATA_DIR`); ":memory:" keeps it in memory
            max_attempts: claims allowed per job before it is marked failed
            lease_seconds: how long a claim holds before another worker may take the job
            clock: seconds since the epoch (replaced in tests)
        """
        self.db_path = db_path or default_queue_path()
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds
        self._clock = clock
        self._lock = threading.RLock()
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------ plumbing

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """One write transaction: all of it or none of it."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def close(self) -> None:
        """Close the database."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> TriageQueue:
        """Context manager: the queue itself."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close on exit."""
        self.close()

    def _known(self, conn: sqlite3.Connection, case_id: str) -> None:
        if conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone() is None:
            raise KeyError(f"unknown case {case_id!r}")

    # ------------------------------------------------------------------ files in

    def enqueue_files(self, paths: list[str]) -> list[str]:
        """Add uploaded files (folder or zip contents) and return case ids.

        One path is one case. A path already in the queue keeps its case id and its progress (re-enqueueing after a
        restart is safe); new paths get the next `case-NNNN` with a queued stage-1 and stage-2 job.

        Args:
            paths: files, zips or case folders, in the order they were uploaded

        Returns:
            Case ids, in the order of `paths`.
        """
        ids: list[str] = []
        now = self._clock()
        with self._tx() as c:
            for raw in paths:
                path = os.path.abspath(str(raw))
                row = c.execute("SELECT case_id FROM cases WHERE path = ?", (path,)).fetchone()
                if row is None:
                    seq = (c.execute("SELECT COALESCE(MAX(seq), 0) FROM cases").fetchone()[0]) + 1
                    case_id = f"case-{seq:04d}"
                    c.execute("INSERT INTO cases(case_id, path, seq, est_hours) VALUES (?, ?, ?, ?)", (case_id, path, seq, DEFAULT_CASE_HOURS))
                    for phase in (STAGE1, STAGE2):
                        c.execute("INSERT INTO jobs(case_id, phase, status, updated) VALUES (?, ?, ?, ?)", (case_id, phase, QUEUED, now))
                else:
                    case_id = row[0]
                ids.append(case_id)
        return ids

    def add_cases(self, case_ids: list[str]) -> None:
        """Register cases that already exist elsewhere (their own case folders), with no file; a known id is left alone.

        Their stage-1 job is marked done (nothing to read) and their stage-2 job queued.
        """
        now = self._clock()
        with self._tx() as c:
            for case_id in case_ids:
                if c.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
                    continue
                seq = (c.execute("SELECT COALESCE(MAX(seq), 0) FROM cases").fetchone()[0]) + 1
                c.execute("INSERT INTO cases(case_id, path, seq, est_hours) VALUES (?, ?, ?, ?)", (case_id, f"case://{case_id}", seq, DEFAULT_CASE_HOURS))
                c.execute("INSERT INTO jobs(case_id, phase, status, updated) VALUES (?, ?, ?, ?)", (case_id, STAGE1, DONE, now))
                c.execute("INSERT INTO jobs(case_id, phase, status, updated) VALUES (?, ?, ?, ?)", (case_id, STAGE2, QUEUED, now))

    def enqueue_stage2(self, case_id: str, *, urgency_rank: int | None = None, est_hours: float | None = None) -> bool:
        """Queue a case's full run: a skipped job is queued again; a queued, claimed, done or failed one is left as it is.

        Args:
            case_id: the case
            urgency_rank: its rank (1 = most urgent); stage-2 jobs are taken in this order
            est_hours: GPU-hours the full run is planned at

        Returns:
            True when a skipped job was queued again.
        """
        with self._tx() as c:
            self._known(c, case_id)
            if urgency_rank is not None:
                c.execute("UPDATE cases SET urgency_rank = ? WHERE case_id = ?", (urgency_rank, case_id))
            if est_hours is not None:
                c.execute("UPDATE cases SET est_hours = ? WHERE case_id = ?", (est_hours, case_id))
            cur = c.execute("UPDATE jobs SET status = 'queued', updated = ? WHERE case_id = ? AND phase = 'stage2' AND status = 'skipped'", (self._clock(), case_id))
            return cur.rowcount > 0

    def skip_stage2(self, case_id: str) -> bool:
        """Hold a case's full run (documents missing, say): a queued job becomes skipped; nothing else changes.

        Returns:
            True when a queued job was skipped.
        """
        with self._tx() as c:
            self._known(c, case_id)
            cur = c.execute("UPDATE jobs SET status = 'skipped', updated = ? WHERE case_id = ? AND phase = 'stage2' AND status = 'queued'", (self._clock(), case_id))
            return cur.rowcount > 0

    def path_of(self, case_id: str) -> str:
        """The file or folder a case came from."""
        with self._lock:
            row = self._conn.execute("SELECT path FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown case {case_id!r}")
        return row[0]

    def case_ids(self) -> list[str]:
        """Every case, in upload order."""
        with self._lock:
            return [r[0] for r in self._conn.execute("SELECT case_id FROM cases ORDER BY seq")]

    # ------------------------------------------------------------------ per-case planning data

    def set_plan(self, case_id: str, *, decision: str | None = None, urgency_rank: int | None = None, est_hours: float | None = None) -> None:
        """Record what the scheduler decided for a case (any argument left None stays as it was)."""
        with self._tx() as c:
            self._known(c, case_id)
            for col, val in (("decision", decision), ("urgency_rank", urgency_rank), ("est_hours", est_hours)):
                if val is not None:
                    c.execute(f"UPDATE cases SET {col} = ? WHERE case_id = ?", (val, case_id))  # noqa: S608 - column names are fixed above

    def set_ranks(self, ranks: dict[str, int]) -> None:
        """Update the urgency rank of many cases in one transaction (re-prioritising)."""
        with self._tx() as c:
            c.executemany("UPDATE cases SET urgency_rank = ? WHERE case_id = ?", [(r, cid) for cid, r in ranks.items()])

    def plan_of(self, case_id: str) -> dict[str, Any]:
        """{'decision', 'urgency_rank', 'est_hours'} of a case."""
        with self._lock:
            row = self._conn.execute("SELECT decision, urgency_rank, est_hours FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown case {case_id!r}")
        return {"decision": row[0], "urgency_rank": row[1], "est_hours": row[2]}

    # ------------------------------------------------------------------ claim, finish, fail

    def reclaim_expired(self) -> list[tuple[str, str]]:
        """Return jobs whose lease ran out to the queue (or fail them, when their attempts are spent).

        Returns:
            (case_id, phase) of the jobs touched.
        """
        with self._tx() as c:
            return self._reclaim(c)

    def _reclaim(self, c: sqlite3.Connection, force: bool = False) -> list[tuple[str, str]]:
        now = self._clock()
        cond = "status = 'claimed'" + ("" if force else " AND lease_until <= ?")
        rows = c.execute(f"SELECT case_id, phase, attempts FROM jobs WHERE {cond}", () if force else (now,)).fetchall()  # noqa: S608
        for r in rows:
            spent = r["attempts"] >= self.max_attempts
            c.execute(
                "UPDATE jobs SET status = ?, lease_until = NULL, owner = NULL, error = COALESCE(error, ?), updated = ? WHERE case_id = ? AND phase = ?",
                (FAILED if spent else QUEUED, "worker lost: attempts spent" if spent else None, now, r["case_id"], r["phase"]),
            )
        return [(r["case_id"], r["phase"]) for r in rows]

    def release_all_claims(self) -> list[tuple[str, str]]:
        """Return every claimed job to the queue now, whatever its lease (used when a new session starts after the old one died).

        Only safe when no other worker is running on this file. Each such claim already cost an attempt.
        """
        with self._tx() as c:
            return self._reclaim(c, force=True)

    def claim(self, phase: str = STAGE2, *, owner: str = "worker", limit: int = 1, case_ids: list[str] | None = None, lease_seconds: float | None = None) -> list[str]:
        """Take up to `limit` queued jobs for this worker, one attempt each.

        Stage 1 goes in upload order; stage 2 in urgency-rank order (unranked last).

        Args:
            phase: 'stage1' or 'stage2'
            owner: who is taking them (shown in the log; a job is released by its owner)
            limit: how many
            case_ids: only these cases
            lease_seconds: lease for these claims (default: the queue's)

        Returns:
            Case ids claimed.
        """
        lease = self.lease_seconds if lease_seconds is None else lease_seconds
        order = "c.seq" if phase == STAGE1 else "COALESCE(c.urgency_rank, 1000000000), c.seq"
        with self._tx() as c:
            self._reclaim(c)
            rows = c.execute(
                f"SELECT j.case_id FROM jobs j JOIN cases c ON c.case_id = j.case_id WHERE j.phase = ? AND j.status = 'queued' ORDER BY {order}",  # noqa: S608
                (phase,),
            ).fetchall()
            taken: list[str] = []
            now = self._clock()
            for r in rows:
                if len(taken) >= limit:
                    break
                if case_ids is not None and r["case_id"] not in case_ids:
                    continue
                c.execute(
                    "UPDATE jobs SET status = 'claimed', attempts = attempts + 1, lease_until = ?, owner = ?, updated = ? WHERE case_id = ? AND phase = ?",
                    (now + lease, owner, now, r["case_id"], phase),
                )
                taken.append(r["case_id"])
            return taken

    def mark_done(self, case_id: str, result: Any = None, phase: str = STAGE2) -> None:
        """Persist completion, with the case's result, in one transaction. Finishing a finished job keeps its first result.

        Args:
            case_id: the case
            result: anything JSON-able (pydantic models are dumped); stored with the status
            phase: 'stage1' or 'stage2'
        """
        payload = json.dumps(to_jsonable_python(result, fallback=str)) if result is not None else None
        with self._tx() as c:
            self._known(c, case_id)
            now = self._clock()
            c.execute("INSERT OR IGNORE INTO jobs(case_id, phase, status, updated) VALUES (?, ?, ?, ?)", (case_id, phase, QUEUED, now))
            c.execute(
                "UPDATE jobs SET status = 'done', result = ?, error = NULL, lease_until = NULL, owner = NULL, updated = ? WHERE case_id = ? AND phase = ? AND status != 'done'",
                (payload, now, case_id, phase),
            )

    def fail(self, case_id: str, error: str, phase: str = STAGE2) -> str:
        """A job's attempt failed: queue it again, or mark it failed when its attempts are spent.

        Returns:
            The job's new status ('queued' or 'failed').
        """
        with self._tx() as c:
            row = c.execute("SELECT attempts, status FROM jobs WHERE case_id = ? AND phase = ?", (case_id, phase)).fetchone()
            if row is None:
                raise KeyError(f"no {phase} job for {case_id!r}")
            if row["status"] == DONE:
                return DONE
            status = FAILED if row["attempts"] >= self.max_attempts else QUEUED
            c.execute(
                "UPDATE jobs SET status = ?, error = ?, lease_until = NULL, owner = NULL, updated = ? WHERE case_id = ? AND phase = ?",
                (status, error[:2000], self._clock(), case_id, phase),
            )
            return status

    def decline(self, case_id: str, reason: str) -> None:
        """Take a case out of the batch for good (a sensitive matter, plan §16): both of its jobs become skipped, so it gets no card and no full run."""
        with self._tx() as c:
            c.execute(
                "UPDATE jobs SET status = 'skipped', error = ?, lease_until = NULL, owner = NULL, updated = ? WHERE case_id = ? AND status != 'done'",
                (reason[:2000], self._clock(), case_id),
            )

    def release(self, case_id: str, phase: str = STAGE2) -> None:
        """Hand a claimed job back without costing an attempt (the worker was interrupted cleanly)."""
        with self._tx() as c:
            c.execute(
                "UPDATE jobs SET status = 'queued', attempts = MAX(attempts - 1, 0), lease_until = NULL, owner = NULL, updated = ? "
                "WHERE case_id = ? AND phase = ? AND status = 'claimed'",
                (self._clock(), case_id, phase),
            )

    def requeue(self, case_id: str, phase: str = STAGE2) -> None:
        """Put a failed job back with a fresh set of attempts (a person decided to retry it)."""
        with self._tx() as c:
            c.execute("UPDATE jobs SET status = 'queued', attempts = 0, error = NULL, updated = ? WHERE case_id = ? AND phase = ? AND status = 'failed'", (self._clock(), case_id, phase))

    # ------------------------------------------------------------------ looking

    def status(self, case_id: str, phase: str = STAGE2) -> str | None:
        """A job's status, or None when the case has no such job."""
        with self._lock:
            row = self._conn.execute("SELECT status FROM jobs WHERE case_id = ? AND phase = ?", (case_id, phase)).fetchone()
        return row[0] if row else None

    def attempts(self, case_id: str, phase: str = STAGE2) -> int:
        """Claims made on a job so far."""
        with self._lock:
            row = self._conn.execute("SELECT attempts FROM jobs WHERE case_id = ? AND phase = ?", (case_id, phase)).fetchone()
        return int(row[0]) if row else 0

    def error_of(self, case_id: str, phase: str = STAGE2) -> str | None:
        """The last error of a job."""
        with self._lock:
            row = self._conn.execute("SELECT error FROM jobs WHERE case_id = ? AND phase = ?", (case_id, phase)).fetchone()
        return row[0] if row else None

    def result(self, case_id: str, phase: str = STAGE2) -> Any:
        """A finished job's saved result (None when not done or none was saved)."""
        with self._lock:
            row = self._conn.execute("SELECT result FROM jobs WHERE case_id = ? AND phase = ? AND status = 'done'", (case_id, phase)).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def done_ids(self, phase: str = STAGE2) -> list[str]:
        """Cases whose job in this phase is done, in upload order."""
        return self._ids_with(phase, DONE)

    def pending_ids(self, phase: str = STAGE1) -> list[str]:
        """Cases whose job in this phase is queued or claimed, in upload order."""
        with self._lock:
            return [r[0] for r in self._conn.execute(
                "SELECT j.case_id FROM jobs j JOIN cases c ON c.case_id = j.case_id WHERE j.phase = ? AND j.status IN ('queued', 'claimed') ORDER BY c.seq", (phase,))]  # fmt: skip

    def _ids_with(self, phase: str, status: str) -> list[str]:
        with self._lock:
            return [r[0] for r in self._conn.execute(
                "SELECT j.case_id FROM jobs j JOIN cases c ON c.case_id = j.case_id WHERE j.phase = ? AND j.status = ? ORDER BY c.seq", (phase, status))]  # fmt: skip

    def failed_ids(self, phase: str = STAGE2) -> list[str]:
        """Cases whose job in this phase failed for good."""
        return self._ids_with(phase, FAILED)

    def counts(self, phase: str = STAGE2) -> dict[str, int]:
        """Jobs of a phase by status (queued, claimed, done, failed, skipped; zero when none)."""
        out = {QUEUED: 0, CLAIMED: 0, DONE: 0, FAILED: 0, SKIPPED: 0}
        with self._lock:
            for r in self._conn.execute("SELECT status, COUNT(*) FROM jobs WHERE phase = ? GROUP BY status", (phase,)):
                out[r[0]] = int(r[1])
        return out

    def next_stage2(self, gpu_budget_hours: float) -> list[str]:
        """Pick cases for full runs within the session's GPU budget, in urgency order.

        Looks only: nothing is claimed. Walks the queued stage-2 jobs by urgency rank and takes each while its planned
        hours still fit what is left of the budget, and stops at the first that does not (a less urgent case never jumps
        ahead of a more urgent one), so a smaller budget gets a prefix of a larger budget's list.

        Args:
            gpu_budget_hours: GPU-hours left in this session

        Returns:
            Case ids, most urgent first.
        """
        picked: list[str] = []
        left = float(gpu_budget_hours)
        with self._lock:
            now = self._clock()
            rows = self._conn.execute(
                "SELECT j.case_id, c.est_hours FROM jobs j JOIN cases c ON c.case_id = j.case_id "
                "WHERE j.phase = 'stage2' AND (j.status = 'queued' OR (j.status = 'claimed' AND j.lease_until <= ? AND j.attempts < ?)) "
                "ORDER BY COALESCE(c.urgency_rank, 1000000000), c.seq",
                (now, self.max_attempts),
            ).fetchall()
        for r in rows:
            if r["est_hours"] > left + 1e-9:
                break
            picked.append(r["case_id"])
            left -= r["est_hours"]
        return picked
