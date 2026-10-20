"""Persisted spend ledger and response cache: the HARD spending cap on OpenAI (the team's whole budget is 5.00 USD).

**Guarantee.** Before a request is sent, `Ledger.reserve` takes a SQLite write lock (`BEGIN IMMEDIATE`), sums everything spent
or reserved so far across every process and thread, and refuses (`BudgetExceeded`, before any HTTP request) when
`spent + worst_case > cap`. The worst case is `bound(input tokens) * input price + max_completion_tokens * output price`:

- the input bound is the UTF-8 BYTE count of the request (+ per-message overhead). A BPE token covers at least one byte, so
  tokens <= bytes: this is an upper bound, not an estimate (about 4x too high for English, which only wastes headroom);
- reasoning tokens are billed as output and counted inside `max_completion_tokens`, so the output bound holds too;
- the input is priced at the full (uncached) rate, the highest.

A reservation is held as spent until `settle` replaces it with the real cost from the response `usage` (never more than
reserved if the API honours its limits). A call that fails with an HTTP error response is released (nothing is billed); one
that may have been billed (a timeout) stays reserved as 'unknown'. Because reserve is serialised and counts reservations,
parallel calls cannot overshoot: total spend <= cap <= 5.00 USD (the cap itself is clamped in `config.effective_cap_usd`).
The default cap is 4.50 USD, so 0.50 USD remains for anything outside the guarantee (a price change, a crash mid-call).

**What is stored.** timestamp, run id, model, served model, token counts, cost in micro-USD, purpose label, case id. NEVER prompt
or response text and never the key. The response cache (a separate SQLite file) must hold response text to answer repeats; it
is only used at temperature 0 and sits in the untracked data dir.

CLI: `python -m vakeel_sahayak.models.openai.ledger` (or `make openai-spend`) prints total spent, remaining, per-model and
per-purpose totals.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from vakeel_sahayak.models.openai.config import (
    HARD_MAX_USD,
    Price,
    cache_path,
    effective_cap_usd,
    effective_run_cap_usd,
    ledger_path,
    usd_to_micro,
)
from vakeel_sahayak.models.openai.errors import BudgetExceeded, OpenAIError

log = logging.getLogger("vakeel_sahayak.openai")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    model TEXT NOT NULL,
    served_model TEXT,
    status TEXT NOT NULL,            -- reserved | settled | unknown | released | cache
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_micro INTEGER NOT NULL DEFAULT 0,
    reserved_micro INTEGER NOT NULL DEFAULT 0,
    purpose TEXT NOT NULL DEFAULT '',
    case_id TEXT
)"""
# What a row counts against the cap: its real cost once settled, its worst case while reserved or of unknown outcome.
_COUNTED = "CASE status WHEN 'settled' THEN cost_micro WHEN 'reserved' THEN reserved_micro WHEN 'unknown' THEN reserved_micro ELSE 0 END"
PROCESS_RUN_ID = uuid.uuid4().hex[:12]
_PER_MESSAGE_OVERHEAD = 16
_BASE_OVERHEAD = 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cost_micro(price: Price, input_tokens: int, cached_tokens: int, output_tokens: int) -> int:
    """Cost in micro-USD, rounded UP: uncached input x input price + cached input x cached price + output x output price.

    `input_tokens` is the total prompt tokens (OpenAI's `prompt_tokens`, which includes the cached ones).
    """
    cached = max(0, min(int(cached_tokens), int(input_tokens)))
    total = (Decimal(int(input_tokens) - cached) * price.input + Decimal(cached) * price.cached_input + Decimal(int(output_tokens)) * price.output)
    return int(total.to_integral_value(rounding=ROUND_CEILING))  # USD per million tokens == micro-USD per token


def input_token_bound(messages: list[dict[str, Any]], schema: Any = None) -> int:
    """An UPPER bound of a request's prompt tokens: UTF-8 bytes of every message and of the schema, plus overhead (see module doc)."""
    n = _BASE_OVERHEAD
    for m in messages:
        n += _PER_MESSAGE_OVERHEAD + len(str(m.get("role", "")).encode()) + len(str(m.get("content", "")).encode())
    if schema is not None:
        n += len(json.dumps(schema, ensure_ascii=False, sort_keys=True).encode())
    return n


def worst_case_micro(price: Price, messages: list[dict[str, Any]], max_output_tokens: int, schema: Any = None) -> int:
    """Highest possible cost of a call: bounded input at the full input price plus `max_output_tokens` at the output price."""
    return cost_micro(price, input_token_bound(messages, schema), 0, max_output_tokens)


@dataclass(frozen=True)
class Reservation:
    """A held slice of the budget (settle or release it)."""

    id: int
    reserved_micro: int
    model: str


class Ledger:
    """SQLite spend ledger, safe across threads and processes (one connection per operation, write-locked transactions)."""

    def __init__(
        self, path: str | Path | None = None, *, cap_usd: float | None = None, run_cap_usd: float | None = None, run_id: str | None = None
    ) -> None:
        """Open (and create) the ledger.

        Args:
            path: SQLite file (default `config.ledger_path()`)
            cap_usd: override the configured cap (tests); still clamped to the hard maximum of 5.00 USD
            run_cap_usd: override the per-run soft cap (tests)
            run_id: label of this run (default env `VS_OPENAI_RUN_ID`, else one random id per process, shared by every ledger object, so the run cap spans all clients of the run)
        """
        self.path = Path(path) if path else ledger_path()
        self._cap_override = None if cap_usd is None else max(0.0, min(float(cap_usd), HARD_MAX_USD))
        self._run_cap_override = run_cap_usd
        self.run_id = run_id or os.environ.get("VS_OPENAI_RUN_ID") or PROCESS_RUN_ID
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def __repr__(self) -> str:
        """Path and run id only."""
        return f"Ledger(path={str(self.path)!r}, run_id={self.run_id!r})"

    # ------------------------------------------------------------------ plumbing

    def _init_db(self) -> None:
        """Create the table and switch to WAL (the journal-mode change ignores the busy timeout, so it is retried while another process holds the file)."""
        for attempt in range(200):
            con = sqlite3.connect(self.path, timeout=120, isolation_level=None)
            try:
                con.execute("PRAGMA busy_timeout=120000")
                con.execute("PRAGMA journal_mode=WAL")
                con.execute(_SCHEMA)
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc) and "busy" not in str(exc) or attempt == 199:
                    raise
                time.sleep(0.02)
            finally:
                con.close()

    @contextlib.contextmanager
    def _tx(self, write: bool = True) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=120, isolation_level=None)
        try:
            con.execute("PRAGMA busy_timeout=120000")
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")
        finally:
            con.close()

    @property
    def cap_micro(self) -> int:
        """The total cap in micro-USD (re-read from config/env at every use, always clamped to 5.00 USD)."""
        return usd_to_micro(self._cap_override if self._cap_override is not None else effective_cap_usd())

    @property
    def run_cap_micro(self) -> int | None:
        """The per-run soft cap in micro-USD, or None."""
        usd = self._run_cap_override if self._run_cap_override is not None else effective_run_cap_usd()
        return None if usd is None else min(usd_to_micro(usd), self.cap_micro)

    def spent_micro(self, con: sqlite3.Connection | None = None, run_id: str | None = None) -> int:
        """Micro-USD spent plus reserved so far (all runs, or one run)."""
        sql = f"SELECT COALESCE(SUM({_COUNTED}), 0) FROM calls" + (" WHERE run_id = ?" if run_id else "")
        args: tuple[Any, ...] = (run_id,) if run_id else ()
        if con is not None:
            return int(con.execute(sql, args).fetchone()[0])
        with self._tx(write=False) as c:
            return int(c.execute(sql, args).fetchone()[0])

    # ------------------------------------------------------------------ reserve / settle

    def reserve(self, model: str, worst_micro: int, purpose: str = "", case_id: str | None = None) -> Reservation:
        """Hold `worst_micro` of the budget for one call, or refuse.

        Raises:
            BudgetExceeded: `spent + worst_case > cap` (or the run cap). Nothing was reserved and no request may be sent.
        """
        worst = int(worst_micro)
        try:
            return self._reserve(model, worst, purpose, case_id)
        except sqlite3.Error as exc:  # nothing was reserved, so nothing may be sent: refuse
            log.error("openai spend ledger unavailable (%s); the call is refused", type(exc).__name__)
            raise OpenAIError("the OpenAI spend ledger is unavailable, so the call was refused (the cap cannot be checked); nothing was sent") from exc

    def _reserve(self, model: str, worst: int, purpose: str, case_id: str | None) -> Reservation:
        with self._tx() as con:
            spent = self.spent_micro(con)
            cap = self.cap_micro
            if spent + worst > cap:
                raise BudgetExceeded(
                    f"OpenAI spending cap: {spent / 1e6:.4f} USD used of {cap / 1e6:.2f}; this call could cost up to {worst / 1e6:.4f}. Refused, nothing was sent",
                    spent, worst, cap, "total",
                )  # fmt: skip
            run_cap = self.run_cap_micro
            if run_cap is not None:
                run_spent = self.spent_micro(con, self.run_id)
                if run_spent + worst > run_cap:
                    raise BudgetExceeded(
                        f"OpenAI run cap: {run_spent / 1e6:.4f} USD used of {run_cap / 1e6:.2f} in this run; this call could cost up to {worst / 1e6:.4f}. Refused, nothing was sent",
                        run_spent, worst, run_cap, "run",
                    )  # fmt: skip
            cur = con.execute(
                "INSERT INTO calls (ts, run_id, model, status, reserved_micro, purpose, case_id) VALUES (?, ?, ?, 'reserved', ?, ?, ?)",
                (_now(), self.run_id, model, worst, purpose[:80], case_id),
            )
            return Reservation(int(cur.lastrowid or 0), worst, model)

    def settle(self, res: Reservation, price: Price, input_tokens: int, cached_tokens: int, output_tokens: int, served_model: str | None = None) -> int:
        """Replace a reservation by the real cost of the call (from the response `usage`). Returns the cost in micro-USD."""
        cost = cost_micro(price, input_tokens, cached_tokens, output_tokens)
        if cost > res.reserved_micro:
            log.warning("openai call cost %d micro-USD, above its reservation of %d (the API exceeded its limits)", cost, res.reserved_micro)
        self._best_effort(
            "UPDATE calls SET status='settled', input_tokens=?, cached_tokens=?, output_tokens=?, cost_micro=?, served_model=? WHERE id=?",
            (int(input_tokens), int(cached_tokens), int(output_tokens), cost, served_model, res.id),
        )
        return cost

    def _best_effort(self, sql: str, args: tuple[Any, ...]) -> None:
        """Update after a call was made: if the ledger cannot be written the row stays 'reserved' (its worst case keeps counting), so the cap stays safe."""
        try:
            with self._tx() as con:
                con.execute(sql, args)
        except sqlite3.Error as exc:
            log.error("openai spend ledger update failed (%s); the reservation stays counted at its worst case", type(exc).__name__)

    def release(self, res: Reservation) -> None:
        """The API answered with an error response: nothing was billed, free the reservation."""
        self._best_effort("UPDATE calls SET status='released' WHERE id=? AND status='reserved'", (res.id,))

    def mark_unknown(self, res: Reservation) -> None:
        """The request may have been billed (a timeout): keep the worst case counted."""
        self._best_effort("UPDATE calls SET status='unknown' WHERE id=? AND status='reserved'", (res.id,))

    def record_cache_hit(self, model: str, purpose: str = "", case_id: str | None = None) -> None:
        """A repeated call answered from the cache: recorded as free."""
        with self._tx() as con:
            con.execute(
                "INSERT INTO calls (ts, run_id, model, status, purpose, case_id) VALUES (?, ?, ?, 'cache', ?, ?)",
                (_now(), self.run_id, model, purpose[:80], case_id),
            )

    def last_served_model(self, model: str) -> str | None:
        """The model id OpenAI reported on the latest settled call of `model` (the snapshot actually served), or None."""
        with self._tx(write=False) as con:
            row = con.execute("SELECT served_model FROM calls WHERE model=? AND status='settled' AND served_model IS NOT NULL ORDER BY id DESC LIMIT 1", (model,)).fetchone()
        return str(row[0]) if row else None

    # ------------------------------------------------------------------ report

    def report(self) -> dict[str, Any]:
        """Totals in USD: spent, remaining, cap, per-model and per-purpose (spent includes held reservations), call and cache-hit counts."""
        with self._tx(write=False) as con:
            spent = self.spent_micro(con)
            by_model = {m: int(v) for m, v in con.execute(f"SELECT model, SUM({_COUNTED}) FROM calls GROUP BY model")}
            by_purpose = {p or "-": int(v) for p, v in con.execute(f"SELECT purpose, SUM({_COUNTED}) FROM calls GROUP BY purpose")}
            n_settled, n_cache, n_unknown, n_released, n_reserved = (
                int(con.execute("SELECT COUNT(*) FROM calls WHERE status=?", (s,)).fetchone()[0]) for s in ("settled", "cache", "unknown", "released", "reserved")
            )
            toks = con.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(cached_tokens),0), COALESCE(SUM(output_tokens),0) FROM calls WHERE status='settled'").fetchone()
        cap = self.cap_micro
        return {
            "spent_usd": spent / 1e6, "cap_usd": cap / 1e6, "remaining_usd": max(0, cap - spent) / 1e6, "hard_max_usd": HARD_MAX_USD,
            "calls": n_settled, "cache_hits": n_cache, "unknown": n_unknown, "released": n_released, "in_flight": n_reserved,
            "input_tokens": int(toks[0]), "cached_tokens": int(toks[1]), "output_tokens": int(toks[2]),
            "by_model_usd": {k: v / 1e6 for k, v in by_model.items()}, "by_purpose_usd": {k: v / 1e6 for k, v in by_purpose.items()},
        }  # fmt: skip


def report(path: str | Path | None = None) -> dict[str, Any]:
    """The configured ledger's `Ledger.report()`."""
    return Ledger(path).report()


def format_report(rep: dict[str, Any]) -> str:
    """The report as text for the CLI."""
    lines = [
        f"OpenAI spend: {rep['spent_usd']:.4f} USD of cap {rep['cap_usd']:.2f} (hard maximum {rep['hard_max_usd']:.2f}); remaining {rep['remaining_usd']:.4f} USD",
        f"calls {rep['calls']}  cache hits {rep['cache_hits']}  unknown-outcome {rep['unknown']}  in flight {rep['in_flight']}  "
        f"tokens in/cached/out {rep['input_tokens']}/{rep['cached_tokens']}/{rep['output_tokens']}",
        "per model:",
        *[f"  {k:<28}{v:>10.4f} USD" for k, v in sorted(rep["by_model_usd"].items())],
        "per purpose:",
        *[f"  {k:<28}{v:>10.4f} USD" for k, v in sorted(rep["by_purpose_usd"].items())],
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.models.openai.ledger [--json]`: print the spend report."""
    args = list(sys.argv[1:] if argv is None else argv)
    rep = report()
    print(json.dumps(rep, indent=2) if "--json" in args else format_report(rep))
    return 0


# ------------------------------------------------------------------------------------------------ response cache


def cache_key(model: str, messages: list[dict[str, Any]], schema: Any, temperature: float, extra: dict[str, Any] | None = None) -> str:
    """Content hash of a call: model, messages, schema, temperature (and the settings that change the answer)."""
    blob = json.dumps({"m": model, "msg": messages, "s": schema, "t": temperature, "x": extra or {}}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResponseCache:
    """Content-hash response cache in SQLite. Only temperature-0 calls are cached, so a repeated call never costs twice."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Open (and create) the cache file."""
        self.path = Path(path) if path else cache_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = self._con()
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, ts TEXT NOT NULL, model TEXT NOT NULL, text TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER)")
        finally:
            con.close()

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=60, isolation_level=None)
        con.execute("PRAGMA busy_timeout=60000")
        return con

    def get(self, key: str) -> tuple[str, int, int] | None:
        """(text, input tokens, output tokens) of a cached call, or None."""
        con = self._con()
        try:
            row = con.execute("SELECT text, input_tokens, output_tokens FROM cache WHERE key=?", (key,)).fetchone()
        finally:
            con.close()
        return None if row is None else (str(row[0]), int(row[1] or 0), int(row[2] or 0))

    def put(self, key: str, model: str, text: str, input_tokens: int, output_tokens: int) -> None:
        """Store a response."""
        con = self._con()
        try:
            con.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?, ?)", (key, _now(), model, text, int(input_tokens), int(output_tokens)))
        finally:
            con.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
