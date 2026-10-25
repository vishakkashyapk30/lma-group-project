"""Sarvam spend ledger with a HARD cap in INR, mirroring `models.openai.ledger` (SQLite, worst-case reservation, refusal).

**Guarantee.** Before a metered request is sent, `SarvamLedger.reserve` takes a SQLite write lock (`BEGIN IMMEDIATE`), sums everything
spent or reserved so far across processes and threads, and refuses (`SarvamBudgetExceeded`, before any HTTP request) when
`spent + worst_case > cap`.

- chat worst case: `bound(input tokens) * input price + max_tokens * output price`. The input bound is the UTF-8 byte count of the
  request (a token covers at least one byte, so tokens <= bytes), priced at the uncached rate; reasoning tokens count inside `max_tokens`.
- characters (translate, transliterate, language id, text to speech): `len(text) * price per character` (exact, not a bound).
- a reservation is held as spent until `settle` replaces it by the real cost; a call that failed with an error response is released;
  one that may have been billed (a timeout) stays reserved as 'unknown'.

Units: prices are INR per 1M tokens, which equals micro-INR per token, so all figures are integer micro-INR. Characters: INR per
10,000 characters = 100 micro-INR per character per INR of price.

Cap (INR): env `VS_SARVAM_CAP_INR`, else configs/eval/runs.yaml `budgets.sarvam_cap_inr`, else `sarvam.ledger.default_cap_inr` (25).
Credits may be added, so there is no hard maximum in code; the cap is the team's declared budget. Per-run cap: env `VS_SARVAM_RUN_CAP_INR`
(run id: env `VS_SARVAM_RUN_ID`, else one per process). Not metered: speech-to-text and Vision digitise.

Stored: time, run id, kind, model, token or character counts, costs, purpose, case id. Never prompt text or the key. The response cache
(a separate SQLite file) holds response text, is used for temperature 0 chat only, and sits in the untracked data dir.

CLI: `python -m vakeel_sahayak.models.sarvam.spend [--json]`.
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
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

from vakeel_sahayak.models.openai.config import data_dir
from vakeel_sahayak.models.openai.ledger import ResponseCache, cache_key, input_token_bound
from vakeel_sahayak.models.sarvam.config import sarvam_config
from vakeel_sahayak.models.sarvam.errors import SarvamBudgetExceeded, SarvamError, SarvamUnavailable

log = logging.getLogger("vakeel_sahayak.sarvam")
CAP_ENV = "VS_SARVAM_CAP_INR"
RUN_CAP_ENV = "VS_SARVAM_RUN_CAP_INR"
RUN_ID_ENV = "VS_SARVAM_RUN_ID"
NO_CACHE_ENV = "VS_SARVAM_NO_CACHE"
PROCESS_RUN_ID = uuid.uuid4().hex[:12]
CHAR_KINDS = ("translate", "transliterate", "language_id", "text_to_speech")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'chat',
    model TEXT NOT NULL,
    status TEXT NOT NULL,            -- reserved | settled | unknown | released | cache
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    chars INTEGER NOT NULL DEFAULT 0,
    cost_micro INTEGER NOT NULL DEFAULT 0,
    reserved_micro INTEGER NOT NULL DEFAULT 0,
    purpose TEXT NOT NULL DEFAULT '',
    case_id TEXT
)"""
_COUNTED = "CASE status WHEN 'settled' THEN cost_micro WHEN 'reserved' THEN reserved_micro WHEN 'unknown' THEN reserved_micro ELSE 0 END"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------------------------------------ config


def _inr(raw: Any) -> float | None:
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def inr_to_micro(inr: float) -> int:
    """INR to whole micro-INR (rounded down, so a cap never grows by rounding)."""
    return int(Decimal(str(inr)) * 1_000_000)


def _runs_yaml_cap() -> float | None:
    """`budgets.sarvam_cap_inr` of configs/eval/runs.yaml (None when the file or key is missing)."""
    try:
        import yaml

        from vakeel_sahayak import config as _cfg

        raw = yaml.safe_load((Path(_cfg._REPO_ROOT) / "configs" / "eval" / "runs.yaml").read_text(encoding="utf-8")) or {}
        return _inr((raw.get("budgets") or {}).get("sarvam_cap_inr"))
    except (OSError, ValueError, ImportError, AttributeError):
        return None


def effective_cap_inr() -> float:
    """The cap in INR: env `VS_SARVAM_CAP_INR`, else runs.yaml `budgets.sarvam_cap_inr`, else `sarvam.ledger.default_cap_inr`; never below 0."""
    default = float(sarvam_config().get("ledger", {}).get("default_cap_inr", 25.0))
    raw = os.environ.get(CAP_ENV)
    if raw is not None and raw.strip():
        val = _inr(raw)
        if val is None:
            log.warning("%s is not a number; using the configured default cap", CAP_ENV)
        else:
            return max(0.0, val)
    val = _runs_yaml_cap()
    return max(0.0, val if val is not None else default)


def effective_run_cap_inr() -> float | None:
    """The optional per-run cap (`VS_SARVAM_RUN_CAP_INR`), never above the total cap; None when unset or invalid."""
    raw = os.environ.get(RUN_CAP_ENV)
    if raw is None or not raw.strip():
        return None
    val = _inr(raw)
    if val is None:
        log.warning("the Sarvam run cap is not a number; ignoring it")
        return None
    return max(0.0, min(val, effective_cap_inr()))


def ledger_path() -> Path:
    """SQLite spend ledger (default `<data>/sarvam/ledger.sqlite`; yaml `sarvam.ledger.path`)."""
    p = sarvam_config().get("ledger", {}).get("path")
    return Path(p) if p else data_dir() / "sarvam" / "ledger.sqlite"


def cache_path() -> Path:
    """SQLite response cache (default `<data>/sarvam/cache.sqlite`; yaml `sarvam.ledger.cache_path`)."""
    p = sarvam_config().get("ledger", {}).get("cache_path")
    return Path(p) if p else data_dir() / "sarvam" / "cache.sqlite"


# ------------------------------------------------------------------------------------------------ prices


@dataclass(frozen=True)
class Price:
    """INR per million tokens (1 INR/M = 1 micro-INR per token)."""

    input: Decimal
    cached_input: Decimal
    output: Decimal


def price_of(model: str, cfg: dict[str, Any] | None = None) -> Price | None:
    """The chat price of a model (case-insensitive exact name; also a `name:version` or `name-YYYY-MM-DD` form of a listed model); None when unlisted."""
    table = {str(k).lower(): v for k, v in ((cfg or sarvam_config()).get("prices_inr_per_1m") or {}).items()}
    name = model.strip().lower()
    entry = table.get(name) or table.get(name.split(":")[0])
    if entry is None and len(name.split("-")) > 3:
        entry = table.get("-".join(name.split("-")[:-3]))
    if entry is None:
        return None
    inp = Decimal(str(entry["input"]))
    return Price(inp, Decimal(str(entry.get("cached", entry["input"]))), Decimal(str(entry["output"])))


def char_price(kind: str, cfg: dict[str, Any] | None = None) -> Decimal | None:
    """INR per 10,000 characters of a non-chat endpoint kind, or None when unlisted."""
    v = ((cfg or sarvam_config()).get("prices_inr_per_10k_chars") or {}).get(kind)
    return None if v is None else Decimal(str(v))


def cost_micro(price: Price, input_tokens: int, cached_tokens: int, output_tokens: int) -> int:
    """Cost in micro-INR, rounded UP: uncached input x input price + cached input x cached price + output x output price."""
    cached = max(0, min(int(cached_tokens), int(input_tokens)))
    total = Decimal(int(input_tokens) - cached) * price.input + Decimal(cached) * price.cached_input + Decimal(int(output_tokens)) * price.output
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def char_cost_micro(inr_per_10k: Decimal, chars: int) -> int:
    """Cost in micro-INR of `chars` characters (100 micro-INR per character per INR/10k), rounded UP."""
    return int((Decimal(int(chars)) * inr_per_10k * 100).to_integral_value(rounding=ROUND_CEILING))


def worst_case_micro(price: Price, messages: list[dict[str, Any]], max_output_tokens: int, schema: Any = None) -> int:
    """Highest possible cost of a chat call: bounded input at the full input price plus `max_output_tokens` at the output price."""
    return cost_micro(price, input_token_bound(messages, schema), 0, max_output_tokens)


# ------------------------------------------------------------------------------------------------ ledger


@dataclass(frozen=True)
class Reservation:
    """A held slice of the budget (settle or release it)."""

    id: int
    reserved_micro: int
    model: str


class SarvamLedger:
    """SQLite spend ledger, safe across threads and processes (one connection per operation, write-locked transactions)."""

    def __init__(self, path: str | Path | None = None, *, cap_inr: float | None = None, run_cap_inr: float | None = None, run_id: str | None = None) -> None:
        """Open (and create) the ledger. `cap_inr` / `run_cap_inr` override the configured caps (tests)."""
        self.path = Path(path) if path else ledger_path()
        self._cap_override = None if cap_inr is None else max(0.0, float(cap_inr))
        self._run_cap_override = run_cap_inr
        self.run_id = run_id or os.environ.get(RUN_ID_ENV) or PROCESS_RUN_ID
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def __repr__(self) -> str:
        """Path and run id only."""
        return f"SarvamLedger(path={str(self.path)!r}, run_id={self.run_id!r})"

    def _init_db(self) -> None:
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
        """The total cap in micro-INR (re-read from env/config at every use)."""
        return inr_to_micro(self._cap_override if self._cap_override is not None else effective_cap_inr())

    @property
    def run_cap_micro(self) -> int | None:
        """The per-run cap in micro-INR, or None."""
        inr = self._run_cap_override if self._run_cap_override is not None else effective_run_cap_inr()
        return None if inr is None else min(inr_to_micro(inr), self.cap_micro)

    def spent_micro(self, con: sqlite3.Connection | None = None, run_id: str | None = None) -> int:
        """Micro-INR spent plus reserved so far (all runs, or one run)."""
        sql = f"SELECT COALESCE(SUM({_COUNTED}), 0) FROM calls" + (" WHERE run_id = ?" if run_id else "")
        args: tuple[Any, ...] = (run_id,) if run_id else ()
        if con is not None:
            return int(con.execute(sql, args).fetchone()[0])
        with self._tx(write=False) as c:
            return int(c.execute(sql, args).fetchone()[0])

    # ------------------------------------------------------------------ reserve / settle

    def reserve(self, model: str, worst_micro: int, purpose: str = "", case_id: str | None = None, kind: str = "chat") -> Reservation:
        """Hold `worst_micro` of the budget for one call, or refuse.

        Raises:
            SarvamBudgetExceeded: `spent + worst_case > cap` (or the run cap). Nothing was reserved and no request may be sent.
            SarvamError: the ledger file is unusable (nothing was reserved, so nothing may be sent).
        """
        try:
            return self._reserve(model, int(worst_micro), purpose, case_id, kind)
        except sqlite3.Error as exc:
            log.error("sarvam spend ledger unavailable (%s); the call is refused", type(exc).__name__)
            raise SarvamError("the Sarvam spend ledger is unavailable, so the call was refused (the cap cannot be checked); nothing was sent") from exc

    def _reserve(self, model: str, worst: int, purpose: str, case_id: str | None, kind: str) -> Reservation:
        with self._tx() as con:
            spent = self.spent_micro(con)
            cap = self.cap_micro
            if spent + worst > cap:
                raise SarvamBudgetExceeded(
                    f"Sarvam spending cap: INR {spent / 1e6:.4f} used of {cap / 1e6:.2f}; this call could cost up to INR {worst / 1e6:.4f}. Refused, nothing was sent",
                    spent, worst, cap, "total",
                )  # fmt: skip
            run_cap = self.run_cap_micro
            if run_cap is not None:
                run_spent = self.spent_micro(con, self.run_id)
                if run_spent + worst > run_cap:
                    raise SarvamBudgetExceeded(
                        f"Sarvam run cap: INR {run_spent / 1e6:.4f} used of {run_cap / 1e6:.2f} in this run; this call could cost up to INR {worst / 1e6:.4f}. Refused, nothing was sent",
                        run_spent, worst, run_cap, "run",
                    )  # fmt: skip
            cur = con.execute(
                "INSERT INTO calls (ts, run_id, kind, model, status, reserved_micro, purpose, case_id) VALUES (?, ?, ?, ?, 'reserved', ?, ?, ?)",
                (_now(), self.run_id, kind, model, worst, purpose[:80], case_id),
            )
            return Reservation(int(cur.lastrowid or 0), worst, model)

    def settle(self, res: Reservation, price: Price, input_tokens: int, cached_tokens: int, output_tokens: int) -> int:
        """Replace a chat reservation by the real cost (from the response `usage`). Returns micro-INR."""
        cost = cost_micro(price, input_tokens, cached_tokens, output_tokens)
        if cost > res.reserved_micro:
            log.warning("sarvam call cost %d micro-INR, above its reservation of %d (the API exceeded its limits)", cost, res.reserved_micro)
        self._best_effort(
            "UPDATE calls SET status='settled', input_tokens=?, cached_tokens=?, output_tokens=?, cost_micro=? WHERE id=?",
            (int(input_tokens), int(cached_tokens), int(output_tokens), cost, res.id),
        )
        return cost

    def settle_chars(self, res: Reservation, chars: int, cost: int) -> int:
        """Replace a character-priced reservation by its cost (the character price is exact, so cost == reservation)."""
        self._best_effort("UPDATE calls SET status='settled', chars=?, cost_micro=? WHERE id=?", (int(chars), int(cost), res.id))
        return int(cost)

    def _best_effort(self, sql: str, args: tuple[Any, ...]) -> None:
        """Update after a call was made: if the ledger cannot be written the row stays 'reserved' (its worst case keeps counting)."""
        try:
            with self._tx() as con:
                con.execute(sql, args)
        except sqlite3.Error as exc:
            log.error("sarvam spend ledger update failed (%s); the reservation stays counted at its worst case", type(exc).__name__)

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
                "INSERT INTO calls (ts, run_id, kind, model, status, purpose, case_id) VALUES (?, ?, 'chat', ?, 'cache', ?, ?)",
                (_now(), self.run_id, model, purpose[:80], case_id),
            )

    # ------------------------------------------------------------------ report

    def report(self) -> dict[str, Any]:
        """Totals in INR: spent (incl. held reservations), remaining, cap, per model / kind / purpose, counts and tokens."""
        with self._tx(write=False) as con:
            spent = self.spent_micro(con)
            by_model = {m: int(v) for m, v in con.execute(f"SELECT model, SUM({_COUNTED}) FROM calls GROUP BY model")}
            by_kind = {k: int(v) for k, v in con.execute(f"SELECT kind, SUM({_COUNTED}) FROM calls GROUP BY kind")}
            by_purpose = {p or "-": int(v) for p, v in con.execute(f"SELECT purpose, SUM({_COUNTED}) FROM calls GROUP BY purpose")}
            n = {s: int(con.execute("SELECT COUNT(*) FROM calls WHERE status=?", (s,)).fetchone()[0]) for s in ("settled", "cache", "unknown", "released", "reserved")}
            toks = con.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(cached_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(SUM(chars),0) FROM calls WHERE status='settled'").fetchone()
        cap = self.cap_micro
        return {
            "spent_inr": spent / 1e6, "cap_inr": cap / 1e6, "remaining_inr": max(0, cap - spent) / 1e6,
            "calls": n["settled"], "cache_hits": n["cache"], "unknown": n["unknown"], "released": n["released"], "in_flight": n["reserved"],
            "input_tokens": int(toks[0]), "cached_tokens": int(toks[1]), "output_tokens": int(toks[2]), "chars": int(toks[3]),
            "by_model_inr": {k: v / 1e6 for k, v in by_model.items()}, "by_kind_inr": {k: v / 1e6 for k, v in by_kind.items()},
            "by_purpose_inr": {k: v / 1e6 for k, v in by_purpose.items()},
        }  # fmt: skip


# ------------------------------------------------------------------------------------------------ metering of one call


class Meter:
    """The reserve -> request -> settle protocol the API client uses (ledger and cache opened on first use; injected in tests)."""

    def __init__(self, ledger: SarvamLedger | None = None, cache: ResponseCache | None = None, config: dict[str, Any] | None = None) -> None:
        """Hold the pieces; nothing is opened yet."""
        self._ledger = ledger
        self._cache = cache
        self.cfg = config
        self._lock = threading.Lock()

    @property
    def ledger(self) -> SarvamLedger:
        """The spend ledger (opened on first use)."""
        if self._ledger is None:
            with self._lock:
                if self._ledger is None:
                    self._ledger = SarvamLedger()
        return self._ledger

    @property
    def cache(self) -> ResponseCache:
        """The response cache (opened on first use)."""
        if self._cache is None:
            with self._lock:
                if self._cache is None:
                    self._cache = ResponseCache(cache_path())
        return self._cache

    # chat
    def begin_chat(
        self, model: str, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None, purpose: str, case_id: str | None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[tuple[str, int, int] | None, Price, Reservation | None, str | None]:
        """Cache lookup (temperature 0), then price and reserve. Returns (cached (text, in, out), price, reservation, cache key).

        Raises:
            SarvamUnavailable: the model has no price (a call whose cost cannot be capped is refused).
            SarvamBudgetExceeded: over the cap.
        """
        price = price_of(model, self.cfg)
        if price is None:
            raise SarvamUnavailable(f"no price for model {model!r} in configs/models.yaml sarvam.prices_inr_per_1m; refusing to call a model whose cost cannot be capped")
        key = None
        if temperature == 0 and os.environ.get(NO_CACHE_ENV, "").strip() not in ("1", "true", "yes"):
            key = cache_key("sarvam:" + model, messages, json_schema, temperature, {"max_tokens": max_tokens, **(extra or {})})
            hit = self.cache.get(key)
            if hit is not None:
                self.ledger.record_cache_hit(model, purpose, case_id)
                return hit, price, None, key
        worst = worst_case_micro(price, messages, max_tokens, json_schema)
        return None, price, self.ledger.reserve(model, worst, purpose, case_id, "chat"), key

    def finish_chat(self, res: Reservation, price: Price, usage: dict[str, Any]) -> int:
        """Settle a chat reservation from the response `usage`."""
        details = usage.get("prompt_tokens_details") or {}
        return self.ledger.settle(res, price, int(usage.get("prompt_tokens", 0) or 0), int(details.get("cached_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0))

    def cache_put(self, key: str | None, model: str, text: str, prompt_tokens: int, completion_tokens: int, finish: str | None) -> None:
        """Remember a complete answer (finish reason 'stop') of a temperature-0 call."""
        if key is not None and finish == "stop" and text.strip():
            self.cache.put(key, model, text, prompt_tokens, completion_tokens)

    # characters
    def begin_chars(self, kind: str, chars: int, model: str, purpose: str = "", case_id: str | None = None) -> tuple[Reservation, int]:
        """Reserve a character-priced call. Returns (reservation, cost in micro-INR).

        Raises:
            SarvamUnavailable: the endpoint kind has no price.
            SarvamBudgetExceeded: over the cap.
        """
        p = char_price(kind, self.cfg)
        if p is None:
            raise SarvamUnavailable(f"no character price for {kind!r} in configs/models.yaml sarvam.prices_inr_per_10k_chars; refusing the call")
        cost = char_cost_micro(p, chars)
        return self.ledger.reserve(model, cost, purpose or kind, case_id, kind), cost

    def finish_chars(self, res: Reservation, chars: int, cost: int) -> None:
        """Settle a character-priced reservation."""
        self.ledger.settle_chars(res, chars, cost)

    def abort(self, res: Reservation, exc: BaseException) -> None:
        """After a failed request: an HTTP error response was not billed (release); a transport failure may have been (keep reserved)."""
        from vakeel_sahayak.models.sarvam.errors import SarvamHttpError

        if isinstance(exc, SarvamHttpError):
            self.ledger.release(res)
        elif isinstance(exc, SarvamUnavailable) and "could not be reached" not in str(exc):
            self.ledger.release(res)  # no key: nothing was sent
        else:
            self.ledger.mark_unknown(res)


# ------------------------------------------------------------------------------------------------ CLI


def report(path: str | Path | None = None) -> dict[str, Any]:
    """The configured ledger's `SarvamLedger.report()`."""
    return SarvamLedger(path).report()


def format_report(rep: dict[str, Any]) -> str:
    """The report as text for the CLI."""
    lines = [
        f"Sarvam spend: INR {rep['spent_inr']:.4f} of cap {rep['cap_inr']:.2f}; remaining INR {rep['remaining_inr']:.4f}",
        f"calls {rep['calls']}  cache hits {rep['cache_hits']}  unknown-outcome {rep['unknown']}  in flight {rep['in_flight']}  "
        f"tokens in/cached/out {rep['input_tokens']}/{rep['cached_tokens']}/{rep['output_tokens']}  chars {rep['chars']}",
        "per model:",
        *[f"  {k:<28}{v:>10.4f} INR" for k, v in sorted(rep["by_model_inr"].items())],
        "per kind:",
        *[f"  {k:<28}{v:>10.4f} INR" for k, v in sorted(rep["by_kind_inr"].items())],
        "per purpose:",
        *[f"  {k:<28}{v:>10.4f} INR" for k, v in sorted(rep["by_purpose_inr"].items())],
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.models.sarvam.spend [--json]`: print the spend report."""
    args = list(sys.argv[1:] if argv is None else argv)
    rep = report()
    print(json.dumps(rep, indent=2) if "--json" in args else format_report(rep))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
