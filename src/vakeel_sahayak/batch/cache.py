"""Shared retrieval cache (plan §11, §6.2).

One cache serves every case of a batch. Its key is the factor, the section family, the before-date month and the
query, the same key `BaseAgent.call_tool` builds for calls to shared stores (`ctx.cache`). Only shared-store results
are cached, never anything read from a case's own stores. The before-date is cut to its month on purpose: two cases
ordered in the same month see the same earlier documents, so they share an answer.

A hit returns exactly what a fresh call would: values are copied on the way in and on the way out, so a caller that
changes a result cannot change what the next case gets. With a `path` the cache also lives in SQLite (JSON values;
`BaseAgent` turns them back into the tool's typed result) so a later session starts warm.
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

