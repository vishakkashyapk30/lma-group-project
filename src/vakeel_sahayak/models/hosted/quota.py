"""Persisted REQUEST ledger for hosted providers on rate limits (free tiers): requests and tokens per minute and per quota day, per KEY and MODEL.

Free tiers are not billed, so the ledger meters what the provider limits instead of money. The limits belong to a model
(configs/models.yaml `providers.<name>.models.<id>`: rpm, rpd, tpm) and apply per key, because a key stands for one project:

- **reserve before call.** `QuotaLedger.try_reserve` takes a SQLite write lock (`BEGIN IMMEDIATE`), counts the requests and tokens of
  (provider, key, model) in the last 60 seconds and in the current quota day across every process and thread, and answers one of:
  `Slot` (a 'reserved' row was inserted: the request may be sent), `Wait` (seconds until the per-minute window has room: requests per
  minute, a minimum spacing of 60/rpm seconds so parallel workers do not burst, tokens per minute, or a server Retry-After), or `DayFull`
  (the day's requests reached rpd, or the server said the daily quota is spent). The client rotates keys on `Wait`/`DayFull` and waits only
  when every key must wait (`client.HostedLLMClient`).
- **learning.** A 429 for the per-minute limit lowers the key's effective rpm for the model (`learn.factor`, default 0.5, never below 1) for
  `learn.hold_s` seconds (default one hour), and a Retry-After is kept as a not-before time. A 429 that names a per-day quota blocks the key
  for the model until the provider's next reset (midnight Pacific for Google), whatever our own count says.
- **what counts.** Every request that left the machine counts against rpm and rpd, also the ones that failed (a 429, 400 or 5xx may still be
  counted by the provider; counting them errs on the safe side). Tokens per minute count the reported prompt, answer and thinking tokens of a
  settled call and the estimate of a call in flight. A request that never left (a connection error) and a cache hit count nothing.
- **quota day.** The provider's `quota_day_tz` (default UTC). Google resets daily quotas at midnight Pacific: with UTC our day starts 7 or 8
  hours before Google's, so a day's budget can straddle two Google days; the per-day 429 is honoured either way.
- **modes.** What a model accepted (system instruction or folded into the user turn; JSON schema, JSON mode or JSON in the prompt; thinking
  options) is remembered per (provider, model) after a 400, so later calls start in the working mode, and the run manifest records it.

**What is stored.** time, quota day, run id, provider, key FINGERPRINT, model, served model version, HTTP status, token counts, the modes used,
purpose label, case id. NEVER prompt or response text and never a key.

CLI: `python -m vakeel_sahayak.models.hosted.quota [--provider gemini] [--json]` (`make gemini-usage`) prints today's usage per key and model.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import sqlite3
import sys
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

log = logging.getLogger("vakeel_sahayak.hosted")

GOOGLE_RESET_TZ = "America/Los_Angeles"
WINDOW_S = 60.0
_SCHEMA = (
    """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,                -- epoch seconds when the request was reserved (sent right after)
    day TEXT NOT NULL,               -- quota day, YYYY-MM-DD in the provider's quota_day_tz
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    key_fp TEXT NOT NULL,            -- fingerprint of the key (never the key)
    model TEXT NOT NULL,
    served_model TEXT,
    status TEXT NOT NULL,            -- reserved | settled | failed | unknown | not_sent | cache
    http_status INTEGER,
    est_tokens INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    thinking_tokens INTEGER NOT NULL DEFAULT 0,
    mode TEXT,                       -- system/structured mode used, e.g. 'system+schema', 'fold+prompt'
    purpose TEXT NOT NULL DEFAULT '',
    case_id TEXT
)""",
    """
CREATE TABLE IF NOT EXISTS key_state (
    provider TEXT NOT NULL, key_fp TEXT NOT NULL, model TEXT NOT NULL,
    rpm_eff INTEGER, learned_until REAL, blocked_until REAL, not_before REAL,
    PRIMARY KEY (provider, key_fp, model)
)""",
    """
CREATE TABLE IF NOT EXISTS model_modes (
    provider TEXT NOT NULL, model TEXT NOT NULL, system TEXT, structured TEXT, thinking TEXT, updated REAL,
    PRIMARY KEY (provider, model)
)""",
    "CREATE INDEX IF NOT EXISTS requests_pkm_ts ON requests (provider, key_fp, model, ts)",
    "CREATE INDEX IF NOT EXISTS requests_pkm_day ON requests (provider, key_fp, model, day)",
)
_SENT = "('reserved', 'settled', 'failed', 'unknown')"
_TOKENS = "CASE status WHEN 'settled' THEN input_tokens + output_tokens + thinking_tokens WHEN 'reserved' THEN est_tokens WHEN 'unknown' THEN est_tokens ELSE 0 END"
PROCESS_RUN_ID = uuid.uuid4().hex[:12]

_STOPS_LOCK = threading.Lock()
_QUOTA_STOPS = [0]


def note_quota_stop() -> None:
    """Count one daily-quota refusal in this process (the eval driver keeps a case that hit it out of the results)."""
    with _STOPS_LOCK:
        _QUOTA_STOPS[0] += 1


def quota_stops() -> int:
    """Daily-quota refusals seen by this process so far."""
    return _QUOTA_STOPS[0]


def _tz(name: str) -> tzinfo:
    if not name or name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - no tz database: Pacific standard time (the later reset), UTC otherwise
        log.warning("time zone %r is not available; using a fixed offset", name)
        return timezone(timedelta(hours=-8)) if name == GOOGLE_RESET_TZ else timezone.utc


def quota_day(ts: float, tz_name: str = "UTC") -> str:
    """The quota day (YYYY-MM-DD) of an epoch time in a time zone."""
    return datetime.fromtimestamp(ts, _tz(tz_name)).date().isoformat()


def next_midnight(ts: float, tz_name: str = "UTC") -> float:
    """Epoch seconds of the next midnight after `ts` in a time zone."""
    tz = _tz(tz_name)
    d = datetime.fromtimestamp(ts, tz).date() + timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=tz).timestamp()


def iso(ts: float) -> str:
    """Epoch seconds as an ISO time in UTC."""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def estimate_tokens(messages: list[dict[str, Any]], schema: Any = None) -> int:
    """A generous estimate of a request's PROMPT tokens (UTF-8 bytes / 3 plus overhead); it paces requests and guards the per-request size."""
    n = 32
    for m in messages:
        n += 8 + len(str(m.get("content", "")).encode()) // 3
    if schema is not None:
        n += len(json.dumps(schema, ensure_ascii=False, sort_keys=True).encode()) // 3
    return n


@dataclass(frozen=True)
class Slot:
    """A counted request (settle, fail, or mark it not sent)."""

    id: int
    provider: str
    key_fp: str
    model: str
    est_tokens: int


@dataclass(frozen=True)
class Wait:
    """No room in the per-minute window yet: try again after `seconds`."""

    seconds: float


@dataclass(frozen=True)
class DayFull:
    """The key's daily cap for the model is reached (`source` 'ledger' or 'server') until `reset_ts`."""

    used: int
    cap: int
    reset_ts: float
    source: str


def default_path() -> Path:
    """`<data>/hosted/quota.sqlite` (data/ is untracked)."""
    try:
        from vakeel_sahayak.config import load_config

        base = Path(load_config().paths.data_dir)
    except (FileNotFoundError, ValueError):
        base = Path(os.environ.get("VS_DATA_DIR") or "data")
    return base / "hosted" / "quota.sqlite"


class QuotaLedger:
    """SQLite request ledger, safe across threads and processes (one connection per operation, write-locked transactions)."""

    def __init__(
        self, path: str | Path | None = None, *, run_id: str | None = None, clock: Callable[[], float] = time.time,
        learn_factor: float = 0.5, learn_hold_s: float = 3600.0,
    ) -> None:  # fmt: skip
        """Open (and create) the ledger.

        Args:
            path: SQLite file (default `<data>/hosted/quota.sqlite`)
            run_id: label of this run (default env `VS_HOSTED_RUN_ID`, else one random id per process)
            clock: time source (tests)
            learn_factor, learn_hold_s: how far and how long a per-minute 429 lowers the effective rpm
        """
        self.path = Path(path) if path else default_path()
        self.run_id = run_id or os.environ.get("VS_HOSTED_RUN_ID") or PROCESS_RUN_ID
        self.clock = clock
        self.learn_factor = min(1.0, max(0.05, float(learn_factor)))
        self.learn_hold_s = max(0.0, float(learn_hold_s))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def __repr__(self) -> str:
        """Path and run id only."""
        return f"QuotaLedger(path={str(self.path)!r}, run_id={self.run_id!r})"

    # ------------------------------------------------------------------ plumbing

    def _init_db(self) -> None:
        for attempt in range(200):
            con = sqlite3.connect(self.path, timeout=120, isolation_level=None)
            try:
                con.execute("PRAGMA busy_timeout=120000")
                con.execute("PRAGMA journal_mode=WAL")
                for stmt in _SCHEMA:
                    con.execute(stmt)
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

    @staticmethod
    def _state(con: sqlite3.Connection, provider: str, key_fp: str, model: str) -> tuple[Any, Any, Any, Any]:
        row = con.execute(
            "SELECT rpm_eff, learned_until, blocked_until, not_before FROM key_state WHERE provider=? AND key_fp=? AND model=?", (provider, key_fp, model)
        ).fetchone()  # fmt: skip
        return (None, None, None, None) if row is None else tuple(row)  # type: ignore[return-value]

    def _effective_rpm(self, con: sqlite3.Connection, provider: str, key_fp: str, model: str, rpm: int, now: float) -> int:
        eff, until, _, _ = self._state(con, provider, key_fp, model)
        if eff and until and now < until:
            return max(1, min(int(eff), rpm))
        return max(1, rpm)

    @staticmethod
    def _day_count(con: sqlite3.Connection, provider: str, key_fp: str, model: str, day: str) -> int:
        return int(con.execute(
            f"SELECT COUNT(*) FROM requests WHERE provider=? AND key_fp=? AND model=? AND day=? AND status IN {_SENT}", (provider, key_fp, model, day)
        ).fetchone()[0])  # fmt: skip

    def _put_state(self, con: sqlite3.Connection, provider: str, key_fp: str, model: str, **kw: Any) -> None:
        eff, until, blocked, nb = self._state(con, provider, key_fp, model)
        cur = {"rpm_eff": eff, "learned_until": until, "blocked_until": blocked, "not_before": nb, **kw}
        con.execute(
            "INSERT INTO key_state (provider, key_fp, model, rpm_eff, learned_until, blocked_until, not_before) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(provider, key_fp, model) DO UPDATE SET rpm_eff=excluded.rpm_eff, learned_until=excluded.learned_until, "
            "blocked_until=excluded.blocked_until, not_before=excluded.not_before",
            (provider, key_fp, model, cur["rpm_eff"], cur["learned_until"], cur["blocked_until"], cur["not_before"]),
        )

    # ------------------------------------------------------------------ reserve

    def try_reserve(
        self, provider: str, key_fp: str, model: str, limits: dict[str, int], est_tokens: int = 0, *, day_tz: str = "UTC", purpose: str = "",
        case_id: str | None = None, mode: str | None = None,
    ) -> Slot | Wait | DayFull:  # fmt: skip
        """One attempt under the write lock (see the module doc). Never sleeps.

        Raises:
            sqlite3.Error: the ledger cannot be used (the caller refuses the call: the limits cannot be checked).
        """
        rpd, tpm = int(limits.get("rpd", 0)), int(limits.get("tpm", 0))
        with self._tx() as con:
            now = self.clock()
            day = quota_day(now, day_tz)
            _, _, blocked, not_before = self._state(con, provider, key_fp, model)
            used = self._day_count(con, provider, key_fp, model, day)
            if blocked and now < float(blocked):
                return DayFull(used, used, float(blocked), "server")
            if used >= rpd:
                return DayFull(used, rpd, next_midnight(now, day_tz), "ledger")
            rpm = self._effective_rpm(con, provider, key_fp, model, int(limits.get("rpm", 1)), now)
            rows = con.execute(
                f"SELECT ts, {_TOKENS} FROM requests WHERE provider=? AND key_fp=? AND model=? AND ts > ? AND status IN {_SENT} ORDER BY ts",
                (provider, key_fp, model, now - WINDOW_S),
            ).fetchall()
            wait = 0.0
            if not_before and now < float(not_before):
                wait = float(not_before) - now
            if len(rows) >= rpm:
                wait = max(wait, float(rows[len(rows) - rpm][0]) + WINDOW_S - now)
            if rows:
                wait = max(wait, float(rows[-1][0]) + WINDOW_S / rpm - now)
            tokens = sum(int(r[1] or 0) for r in rows)
            if rows and tpm and tokens + est_tokens > tpm:
                left = tokens
                for ts, tok in rows:
                    left -= int(tok or 0)
                    if left + est_tokens <= tpm:
                        wait = max(wait, float(ts) + WINDOW_S - now)
                        break
                else:
                    wait = max(wait, float(rows[-1][0]) + WINDOW_S - now)
            if wait > 0:
                return Wait(wait)
            cur = con.execute(
                "INSERT INTO requests (ts, day, run_id, provider, key_fp, model, status, est_tokens, mode, purpose, case_id) "
                "VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?, ?, ?, ?)",
                (now, day, self.run_id, provider, key_fp, model, int(est_tokens), mode, purpose[:80], case_id),
            )
            return Slot(int(cur.lastrowid or 0), provider, key_fp, model, int(est_tokens))

    # ------------------------------------------------------------------ outcomes

    def _best_effort(self, sql: str, args: tuple[Any, ...]) -> None:
        try:
            with self._tx() as con:
                con.execute(sql, args)
        except sqlite3.Error as exc:  # the row stays 'reserved', which keeps counting: safe
            log.error("hosted request ledger update failed (%s); the request stays counted", type(exc).__name__)

    def settle(self, slot: Slot, input_tokens: int, output_tokens: int, thinking_tokens: int = 0, served_model: str | None = None, mode: str | None = None) -> None:
        """The call answered: record the reported token counts, the served model version and the mode that worked."""
        self._best_effort(
            "UPDATE requests SET status='settled', input_tokens=?, output_tokens=?, thinking_tokens=?, served_model=?, http_status=200, mode=COALESCE(?, mode) WHERE id=?",
            (int(input_tokens), int(output_tokens), int(thinking_tokens), served_model, mode, slot.id),
        )

    def fail(self, slot: Slot, http_status: int) -> None:
        """The API answered with an error status: the request still counts against rpm and rpd, with no tokens."""
        self._best_effort("UPDATE requests SET status='failed', http_status=? WHERE id=? AND status='reserved'", (int(http_status), slot.id))

    def not_sent(self, slot: Slot) -> None:
        """The request never left the machine (a connection error): it counts nothing."""
        self._best_effort("UPDATE requests SET status='not_sent' WHERE id=? AND status='reserved'", (slot.id,))

    def mark_unknown(self, slot: Slot) -> None:
        """The request may have reached the provider (a timeout): it keeps counting, with its estimated tokens."""
        self._best_effort("UPDATE requests SET status='unknown' WHERE id=? AND status='reserved'", (slot.id,))

    def record_cache_hit(self, provider: str, model: str, purpose: str = "", case_id: str | None = None, day_tz: str = "UTC") -> None:
        """A repeated call answered from the cache: recorded, counts nothing."""
        now = self.clock()
        self._best_effort(
            "INSERT INTO requests (ts, day, run_id, provider, key_fp, model, status, purpose, case_id) VALUES (?, ?, ?, ?, '-', ?, 'cache', ?, ?)",
            (now, quota_day(now, day_tz), self.run_id, provider, model, purpose[:80], case_id),
        )

    def note_429(self, provider: str, key_fp: str, model: str, rpm: int, *, per_day: bool = False, retry_after: float | None = None, reset_tz: str = GOOGLE_RESET_TZ) -> int:
        """Learn from a 429: per-day blocks the key for the model until the provider's next reset; per-minute lowers the effective rpm and keeps
        the Retry-After. Returns the effective rpm after the change."""
        now = self.clock()
        try:
            with self._tx() as con:
                _, _, blocked, nb = self._state(con, provider, key_fp, model)
                if per_day:
                    self._put_state(con, provider, key_fp, model, blocked_until=max(float(blocked or 0), next_midnight(now, reset_tz)))
                else:
                    cur = self._effective_rpm(con, provider, key_fp, model, rpm, now)
                    kw: dict[str, Any] = {"rpm_eff": max(1, int(math.floor(cur * self.learn_factor))), "learned_until": now + self.learn_hold_s}
                    if retry_after:
                        kw["not_before"] = max(float(nb or 0), now + float(retry_after))
                    self._put_state(con, provider, key_fp, model, **kw)
                return self._effective_rpm(con, provider, key_fp, model, rpm, now)
        except sqlite3.Error as exc:
            log.error("hosted request ledger update failed (%s)", type(exc).__name__)
            return rpm

    def defer(self, provider: str, key_fp: str, model: str, seconds: float) -> None:
        """Keep the key off this model for `seconds` (a Retry-After on a 5xx)."""
        now = self.clock()
        try:
            with self._tx() as con:
                _, _, _, nb = self._state(con, provider, key_fp, model)
                self._put_state(con, provider, key_fp, model, not_before=max(float(nb or 0), now + float(seconds)))
        except sqlite3.Error as exc:
            log.error("hosted request ledger update failed (%s)", type(exc).__name__)

    # ------------------------------------------------------------------ modes

    def modes(self, provider: str, model: str) -> dict[str, str]:
        """What the model was last seen to accept: {'system': 'system'|'fold', 'structured': 'schema'|'json_mode'|'prompt', 'thinking': 'on'|'off'} (empty when never learned)."""
        try:
            with self._tx(write=False) as con:
                row = con.execute("SELECT system, structured, thinking FROM model_modes WHERE provider=? AND model=?", (provider, model)).fetchone()
        except sqlite3.Error:
            return {}
        return {} if row is None else {k: v for k, v in zip(("system", "structured", "thinking"), row) if v}

    def set_modes(self, provider: str, model: str, **modes: str) -> None:
        """Remember a mode the model needs (after a 400 that named a parameter, or the smoke probe)."""
        cur = self.modes(provider, model)
        cur.update({k: v for k, v in modes.items() if v})
        self._best_effort(
            "INSERT INTO model_modes (provider, model, system, structured, thinking, updated) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(provider, model) DO UPDATE SET system=excluded.system, structured=excluded.structured, thinking=excluded.thinking, updated=excluded.updated",
            (provider, model, cur.get("system"), cur.get("structured"), cur.get("thinking"), self.clock()),
        )

    # ------------------------------------------------------------------ report

    def last_served_model(self, provider: str, model: str) -> str | None:
        """The model version the provider reported on the latest settled call of `model`, or None."""
        with self._tx(write=False) as con:
            row = con.execute(
                "SELECT served_model FROM requests WHERE provider=? AND model=? AND status='settled' AND served_model IS NOT NULL ORDER BY id DESC LIMIT 1", (provider, model)
            ).fetchone()  # fmt: skip
        return str(row[0]) if row else None

    def run_models(self, provider: str, run_id: str | None = None) -> dict[str, int]:
        """Settled calls per model in a run (default this run): the manifest records every model a run used."""
        with self._tx(write=False) as con:
            rows = con.execute(
                "SELECT model, COUNT(*) FROM requests WHERE provider=? AND run_id=? AND status='settled' GROUP BY model", (provider, run_id or self.run_id)
            ).fetchall()  # fmt: skip
        return {str(m): int(n) for m, n in rows}

    def remaining_today(self, provider: str, key_fp: str, model: str, limits: dict[str, int], day_tz: str = "UTC") -> int:
        """Requests the ledger still allows today for (provider, key, model) (0 while a per-day block holds)."""
        with self._tx(write=False) as con:
            now = self.clock()
            _, _, blocked, _ = self._state(con, provider, key_fp, model)
            if blocked and now < float(blocked):
                return 0
            return max(0, int(limits.get("rpd", 0)) - self._day_count(con, provider, key_fp, model, quota_day(now, day_tz)))

    def report(self, provider: str, keys: list[str], models: dict[str, dict[str, int]], day_tz: str = "UTC") -> dict[str, Any]:
        """Today's usage per key fingerprint and model: requests, failed, cache hits, tokens, remaining, effective rpm, block; plus totals.

        Args:
            provider: provider name
            keys: fingerprints of the configured keys (keys seen in the ledger today are added)
            models: model id -> limits (models seen in the ledger today are added with zero limits)
        """
        with self._tx(write=False) as con:
            now = self.clock()
            day = quota_day(now, day_tz)
            seen = con.execute("SELECT DISTINCT key_fp, model FROM requests WHERE provider=? AND day=? AND key_fp != '-'", (provider, day)).fetchall()
            all_keys = list(dict.fromkeys([*keys, *(str(k) for k, _ in seen)]))
            all_models = dict(models)
            for _, m in seen:
                all_models.setdefault(str(m), {"rpm": 0, "rpd": 0, "tpm": 0})
            per: dict[str, dict[str, Any]] = {}
            totals = {"requests": 0, "remaining": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
            for k in all_keys:
                for m, lim in all_models.items():
                    sent = self._day_count(con, provider, k, m, day)
                    failed = int(con.execute("SELECT COUNT(*) FROM requests WHERE provider=? AND key_fp=? AND model=? AND day=? AND status='failed'", (provider, k, m, day)).fetchone()[0])
                    toks = con.execute(
                        "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(thinking_tokens),0) FROM requests "
                        "WHERE provider=? AND key_fp=? AND model=? AND day=? AND status='settled'", (provider, k, m, day),
                    ).fetchone()  # fmt: skip
                    _, _, blocked, _ = self._state(con, provider, k, m)
                    blocked_now = bool(blocked and now < float(blocked))
                    remaining = 0 if blocked_now else max(0, int(lim.get("rpd", 0)) - sent)
                    per[f"{k}/{m}"] = {
                        "key": k, "model": m, "requests": sent, "failed": failed, "remaining": remaining, "limits": dict(lim),
                        "effective_rpm": self._effective_rpm(con, provider, k, m, int(lim.get("rpm", 1) or 1), now),
                        "input_tokens": int(toks[0]), "output_tokens": int(toks[1]), "thinking_tokens": int(toks[2]),
                        "blocked_until": iso(float(blocked)) if blocked_now else None,
                    }  # fmt: skip
                    totals["requests"] += sent
                    totals["remaining"] += remaining
                    for t, v in zip(("input_tokens", "output_tokens", "thinking_tokens"), toks):
                        totals[t] += int(v)
            cache = int(con.execute("SELECT COUNT(*) FROM requests WHERE provider=? AND day=? AND status='cache'", (provider, day)).fetchone()[0])
        return {
            "provider": provider, "day": day, "day_tz": day_tz, "reset_at": iso(next_midnight(now, day_tz)), "keys": all_keys,
            "cache_hits": cache, **totals, "by_key_model": per,
        }  # fmt: skip


def format_report(rep: dict[str, Any]) -> str:
    """The report as text for the CLI (keys by fingerprint only)."""
    lines = [
        f"{rep['provider']}: quota day {rep['day']} ({rep['day_tz']}; Google resets at midnight Pacific); ledger day ends {rep['reset_at']}",
        f"keys {len(rep['keys'])} ({', '.join(rep['keys']) or 'none set'}); requests today {rep['requests']}, remaining {rep['remaining']}, cache hits {rep['cache_hits']}; "
        f"tokens in/out/thinking {rep['input_tokens']}/{rep['output_tokens']}/{rep['thinking_tokens']}",
        "limits are from configs/models.yaml (as shown in AI Studio on 2026-10-28; re-check there). Per key and model:",
    ]
    for v in rep["by_key_model"].values():
        if not v["requests"] and not v["limits"].get("rpd"):
            continue
        extra = f"  BLOCKED until {v['blocked_until']}" if v.get("blocked_until") else ""
        lim = v["limits"]
        lines.append(
            f"  {v['key']}  {v['model']:<26} {v['requests']:>5} used (failed {v['failed']})  {v['remaining']:>6} left of {lim.get('rpd', 0)}  "
            f"rpm {v['effective_rpm']}/{lim.get('rpm', 0)}  tpm {lim.get('tpm', 0)}{extra}"
        )
    return "\n".join(lines)


def provider_report(provider: str, ledger: QuotaLedger | None = None) -> dict[str, Any]:
    """Today's report of a configured provider (keys by fingerprint, every configured model)."""
    from vakeel_sahayak.models.hosted.keys import pool
    from vakeel_sahayak.models.registry import get_provider

    spec = get_provider(provider)
    if spec is None:
        raise ValueError(f"no provider {provider!r} in configs/models.yaml providers:")
    models = {m: spec.limits_for(m) for m in (spec.models or {})} or {spec.default_model: spec.limits_for(spec.default_model)}
    return (ledger or QuotaLedger()).report(spec.name, [k.fp for k in pool(spec.key_env)], models, spec.quota_day_tz)


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.models.hosted.quota [--provider NAME] [--json]`: print today's usage per key and model."""
    args = list(sys.argv[1:] if argv is None else argv)
    provider = args[args.index("--provider") + 1] if "--provider" in args and args.index("--provider") + 1 < len(args) else "gemini"
    rep = provider_report(provider)
    print(json.dumps(rep, indent=2) if "--json" in args else format_report(rep))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
