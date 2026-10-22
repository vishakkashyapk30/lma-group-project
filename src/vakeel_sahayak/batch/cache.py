"""Shared retrieval cache (plan §11, §6.2).

One cache serves every case of a batch. Its key is the factor, the section family, the before-date month and the
query, the same key `BaseAgent.call_tool` builds for calls to shared stores (`ctx.cache`). Only shared-store results
are cached, never anything read from a case's own stores. The before-date is cut to its month on purpose: two cases
ordered in the same month see the same earlier documents, so they share an answer.

A hit returns exactly what a fresh call would: values are copied on the way in and on the way out, so a caller that
changes a result cannot change what the next case gets. With a `path` the cache also lives in SQLite (JSON values;
`BaseAgent` turns them back into the tool's typed result) so a later session starts warm.

`PlanCache` (variant S14 / A14, `Switches.plan_cache`) lives on top of the same store: it keeps Sutradhar's `RetrievalPlan` per factor under a
signature, so a later case with the same signature reuses the plan instead of asking the model again. See its docstring for the paper and what is adapted.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from typing import Any

from pydantic_core import to_jsonable_python

from vakeel_sahayak.schemas.enums import Factor

_SCHEMA = "CREATE TABLE IF NOT EXISTS retrieval_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


class RetrievalCache:
    """Cache shared across cases; key = factor, section family, before-date month and query (plan §11)."""

    def __init__(self, path: str | None = None, max_entries: int | None = None) -> None:
        """Create the cache.

        Args:
            path: SQLite file for a persistent cache (None: in memory only)
            max_entries: keep at most this many entries in memory, dropping the oldest first (None: no limit)
        """
        self.path = path
        self.max_entries = max_entries
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._hits = self._misses = self._puts = 0
        self._conn: sqlite3.Connection | None = None
        if path:
            self._conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def key(self, factor: Factor | str, section_family: list[str], before: str, query: str) -> str:
        """Build the cache key.

        Args:
            factor: the bail factor (an enum member or its value; '' for a call outside any factor)
            section_family: the charged-section family (order does not matter)
            before: the before-date; only its month (YYYY-MM) counts
            query: the query text

        Returns:
            Key string.
        """
        f = factor.value if isinstance(factor, Factor) else str(factor or "")
        family = ",".join(sorted(str(s) for s in section_family or []))
        return "|".join([f, family, str(before or "")[:7], str(query)])

    def get(self, key: str) -> Any | None:
        """Cached result or None; counts a hit or a miss.

        Args:
            key: a key from `key()`

        Returns:
            A copy of the stored result, or None.
        """
        with self._lock:
            if key in self._data:
                self._hits += 1
                return copy.deepcopy(self._data[key])
            if self._conn is not None:
                row = self._conn.execute("SELECT value FROM retrieval_cache WHERE key = ?", (key,)).fetchone()
                if row is not None:
                    self._hits += 1
                    value = json.loads(row[0])
                    self._remember(key, value)
                    return copy.deepcopy(value)
            self._misses += 1
            return None

    def peek(self, key: str) -> Any | None:
        """The stored value without counting a hit or a miss (the plan cache keeps its own counters, so the retrieval hit rate stays the retrieval hit rate)."""
        with self._lock:
            if key in self._data:
                return copy.deepcopy(self._data[key])
            if self._conn is not None:
                row = self._conn.execute("SELECT value FROM retrieval_cache WHERE key = ?", (key,)).fetchone()
                if row is not None:
                    return json.loads(row[0])
            return None

    def put(self, key: str, value: Any) -> None:
        """Store a result (None is never stored: it would read as a miss).

        Args:
            key: a key from `key()`
            value: the result, as a fresh call returned it
        """
        if value is None:
            return
        with self._lock:
            self._puts += 1
            self._remember(key, copy.deepcopy(value))
            if self._conn is not None:
                payload = json.dumps(to_jsonable_python(value, fallback=str))
                self._conn.execute("INSERT OR REPLACE INTO retrieval_cache(key, value) VALUES (?, ?)", (key, payload))
                self._conn.commit()

    def _remember(self, key: str, value: Any) -> None:
        self._data.pop(key, None)
        self._data[key] = value
        while self.max_entries is not None and len(self._data) > self.max_entries:
            self._data.pop(next(iter(self._data)))

    def __contains__(self, key: str) -> bool:
        """True when the key is stored (does not count as a hit or a miss)."""
        with self._lock:
            if key in self._data:
                return True
            return self._conn is not None and self._conn.execute("SELECT 1 FROM retrieval_cache WHERE key = ?", (key,)).fetchone() is not None

    def __len__(self) -> int:
        """Entries held (on disk when persistent)."""
        with self._lock:
            if self._conn is not None:
                return int(self._conn.execute("SELECT COUNT(*) FROM retrieval_cache").fetchone()[0])
            return len(self._data)

    def clear(self) -> None:
        """Drop every entry and reset the counters."""
        with self._lock:
            self._data.clear()
            self._hits = self._misses = self._puts = 0
            if self._conn is not None:
                self._conn.execute("DELETE FROM retrieval_cache")
                self._conn.commit()

    def close(self) -> None:
        """Close the SQLite file, if any."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def stats(self) -> dict[str, float]:
        """Hit rate etc. for F4 (plan §15.6): hits, misses, lookups, puts, entries, hit_rate (0.0 with no lookups)."""
        with self._lock:
            lookups = self._hits + self._misses
            return {
                "hits": float(self._hits),
                "misses": float(self._misses),
                "lookups": float(lookups),
                "puts": float(self._puts),
                "entries": float(len(self)),
                "hit_rate": self._hits / lookups if lookups else 0.0,
            }



# ---------------------------------------------------------------------------------------------------------------- plan templates (S14 / A14)
PLAN_KEY = "plan"
PER_CASE_ARGS = ("before",)  # arguments a template never keeps: the new case's own value is filled in by Sutradhar's tidy step
FREE_TEXT_ARGS = ("query",)  # arguments the template keeps (the model's wording); every other argument is re-filled from the new case


class PlanCache:
    """Reuse of a RetrievalPlan across cases with the same signature (variant S14 / A14, `Switches.plan_cache`).

    Paper (adapted, not reproduced): Zhang, Wornow, Wan and Olukotun, "Agentic Plan Caching: Test-Time Memory for Fast and Cost-Efficient LLM Agents", NeurIPS 2025 (arXiv 2506.14852),
    https://neurips.cc/virtual/2025/poster/116166; related: Wang et al., "Agent Workflow Memory", ICML 2025,
    https://proceedings.mlr.press/v267/wang25bx.html. The idea: extract a reusable plan template from a finished run, keep it under a keyword of the task, and
    when a similar task arrives let a cheap step adapt the template instead of planning from scratch with the large model.

    What we took: a template per task signature, a lookup before planning, and the saving counted in tokens. What we changed, and why: (1) the signature is
    structural, not a keyword extracted by a model: factor, stance, section family, month of the order date, the factor's slot layout, the switches that
    shape a plan and a `store_version` string (a batch changes it when a store is rebuilt, which invalidates every template). (2) The "adaptation" is a
    rule: the template keeps the model's free-text queries and the choice and order of steps; every argument that comes from the case (`case_id`, dates,
    section codes, the facts text, the `similar_orders` signature) is re-filled from the new case's own rule-built step, and `before` is left to Sutradhar's tidy step.
    (3) Only the first-round plan of a factor is cached; re-plans are rule-based already. (4) Nothing read from a case's own stores is cached: a template holds
    steps, never results. The evaluation question (claim C31, extended) is whether G1 recall stays within the confidence interval of the no-cache run.

    Signals (`stats()`): hits, misses, lookups, hit_rate, tokens_saved (the tokens the planning call cost when the template was made, summed over hits),
    tokens_spent (planning calls that were made), templates.
    """

    def __init__(self, cache: RetrievalCache, store_version: str = "") -> None:
        """Wrap a retrieval cache; `store_version` is part of every key (change it and every template is a miss)."""
        self.cache = cache
        self.store_version = store_version
        self._lock = threading.RLock()
        self.hits = self.misses = self.tokens_saved = self.tokens_spent = 0

    # ------------------------------------------------------------------ keys

    def signature(self, work: Any, switches: Any) -> str:
        """The key of a factor's plan: see the class docstring. `work` is Sutradhar's `FactorWork` (factor, stance, pctx, slots)."""
        pctx = work.pctx
        layout = [[name, str(getattr(sw, "need", "")), [str(getattr(s, "value", s)) for s in sw.sources]] for name, sw in sorted(work.slots.items()) if sw.sources]
        parts = {
            "factor": str(getattr(work.factor, "value", work.factor)), "stance": str(getattr(work.stance, "value", work.stance)),
            "family": sorted(pctx.family), "month": str(pctx.before or "")[:7], "layout": layout,
            "filters": bool(switches.retrieval_filters), "dossier": bool(switches.uses_dossier), "knockout": switches.knockout_store,
            "version": self.store_version,
        }
        return f"{PLAN_KEY}|" + json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    # ------------------------------------------------------------------ lookup and store

    def lookup(self, key: str, fresh: dict[tuple[str, str], Any] | None = None) -> dict[str, Any] | None:
        """The template under `key`, adapted to the new case, or None (a miss).

        Args:
            key: from `signature`
            fresh: the new case's own rule-built steps by (slot, tool), used to re-fill case-bound arguments

        Returns:
            dict with `steps` (list of {slot, tool, args}) and `tokens_saved`, or None.
        """
        with self._lock:
            template = self.cache.peek(key)
            if not isinstance(template, dict) or "steps" not in template:
                self.misses += 1
                return None
            self.hits += 1
            saved = int(template.get("tokens", 0))
            self.tokens_saved += saved
        steps = []
        for step in template["steps"]:
            args = dict(step.get("args") or {})
            new = (fresh or {}).get((step["slot"], step["tool"]))
            if new is not None:
                bound = {k: v for k, v in dict(getattr(new, "args", {}) or {}).items() if k not in FREE_TEXT_ARGS}
                args = {**args, **bound}
            steps.append({"slot": step["slot"], "tool": step["tool"], "args": args})
        return {"steps": steps, "tokens_saved": saved}

    def store(self, key: str, steps: list[dict[str, Any]], tokens: int) -> None:
        """Keep a plan as a template (case-specific arguments stripped) with the tokens its planning call cost."""
        clean = []
        for step in steps:
            args = {k: v for k, v in dict(step.get("args") or {}).items() if k not in PER_CASE_ARGS and k != "case_id"}
            clean.append({"slot": step["slot"], "tool": step["tool"], "args": args})
        with self._lock:
            self.tokens_spent += int(tokens)
            self.cache.put(key, {"steps": clean, "tokens": int(tokens)})

    def stats(self) -> dict[str, float]:
        """Hit rate and tokens saved (S14 signals)."""
        with self._lock:
            lookups = self.hits + self.misses
            return {
                "hits": float(self.hits), "misses": float(self.misses), "lookups": float(lookups),
                "hit_rate": self.hits / lookups if lookups else 0.0,
                "tokens_saved": float(self.tokens_saved), "tokens_spent": float(self.tokens_spent),
                "templates": float(sum(1 for k in list(self.cache._data) if str(k).startswith(PLAN_KEY + "|"))),
            }


def plans_of(cache: RetrievalCache, store_version: str | None = None) -> PlanCache:
    """The plan cache that rides on a retrieval cache (one per cache, so every agent of a batch shares its counters); `store_version` sets it when given."""
    plans = cache.__dict__.get("_plans")
    if plans is None:
        plans = cache.__dict__["_plans"] = PlanCache(cache, store_version or "")
    elif store_version is not None:
        plans.store_version = store_version
    return plans
