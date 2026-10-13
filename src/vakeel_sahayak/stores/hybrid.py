"""Hybrid search index: BM25 (SQLite FTS5) plus dense vectors, with metadata pre-filters (plan §5.1, §5.5).

SQLite is the always-available backend: rows, the FTS5 full-text table (BM25) and, by default, the dense vectors in one
file, so the stores run on a laptop without torch or LanceDB. LanceDB can hold the dense vectors instead
(`dense_backend="lancedb"`; imported lazily, needs the `lancedb` package). The dense side uses any `Embedder`
(BGE-M3 when installed, otherwise the hashed n-gram fallback, see `models/embeddings.py`).

Search: metadata filters narrow the candidate set first (SQL), then BM25 and cosine rankings are fused by reciprocal rank
fusion, and an authority prior can be blended in. The embedder that built an index is recorded in it and reused at query
time, so query and document vectors always come from the same model.
"""

from __future__ import annotations

import json
import re
import sqlite3
from array import array
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.models.embeddings import Embedder, get_embedder

RRF_K = 60
MAX_QUERY_TERMS = 64
_TERM = re.compile(r"[A-Za-z0-9]+")
_FILTER_COLUMNS = {"court": "court_n", "outcome": "outcome_n", "part": "part", "doc_type": "doc_type"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, date TEXT,
    court_n TEXT, outcome_n TEXT, part TEXT, doc_type TEXT, authority REAL NOT NULL DEFAULT 0, vec BLOB);
CREATE TABLE IF NOT EXISTS facets (item_id INTEGER NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS facets_lookup ON facets (kind, value, item_id);
CREATE INDEX IF NOT EXISTS items_date ON items (date);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text, content='', tokenize='porter unicode61');
"""


@dataclass
class IndexRow:
    """One document to index: the text searched, the payload returned, and the metadata filters."""

    key: str
    text: str
    payload: dict[str, Any]
    date: str | None = None
    court: str | None = None
    outcome: str | None = None
    part: str | None = None
    doc_type: str | None = None
    authority: float = 0.0
    facets: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Hit:
    """A search result: the stored payload, the final score in [0, 1] and the authority prior."""

    key: str
    payload: dict[str, Any]
    score: float
    authority: float = 0.0


def embedder_name_of(embedder: Any) -> str:
    """Name of an embedder: its `name`, else its class name (test doubles carry no name)."""
    return str(getattr(embedder, "name", None) or type(embedder).__name__)


def _default_embedder() -> Embedder:
    """The configured embedder, looked up at call time so a replaced `models.factory.get_embedder` is honoured."""
    from vakeel_sahayak.models import factory

    return factory.get_embedder()  # type: ignore[return-value]


def _norm(value: str | None) -> str | None:
    """Case-folded filter value."""
    return value.strip().lower() if value else None


class HybridIndex:
    """BM25 + dense index in one SQLite file (or in memory), see the module docstring."""

    def __init__(
        self,
        path: str | Path | None = None,
        embedder: Embedder | None = None,
        *,
        dense_backend: str = "sqlite",
        lance_dir: str | Path | None = None,
    ) -> None:
        """Open or create an index.

        Args:
            path: SQLite file; None or ':memory:' keeps it in memory
            embedder: embedder for a new index; an existing index keeps the embedder recorded in it
            dense_backend: 'sqlite' (vectors in the file) or 'lancedb' (optional, lazy import)
            lance_dir: LanceDB directory when `dense_backend='lancedb'`

        Raises:
            ValueError: when `embedder` differs from the one recorded in an existing, non-empty index.
        """
        in_memory = path is None or str(path) == ":memory:"
        if not in_memory:
            Path(path).parent.mkdir(parents=True, exist_ok=True)  # type: ignore[arg-type]
        self.path = None if in_memory else Path(path)  # type: ignore[arg-type]
        self._conn = sqlite3.connect(":memory:" if in_memory else str(path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._dense_backend = dense_backend
        self._lance_dir = Path(lance_dir) if lance_dir else (self.path.with_suffix(".lance") if self.path else None)
        self._lance_table = None
        self._embedder = self._resolve_embedder(embedder)

    # setup ---------------------------------------------------------------------------------------------------------

    def _resolve_embedder(self, requested: Embedder | None) -> Embedder:
        """The index's embedder: the recorded one if present (checked against `requested`), else the requested or default.

        The default comes from `models.factory.get_embedder` (all model calls go through `models/`, plan §12).
        """
        row = self._conn.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()
        recorded = row[0] if row else None
        if recorded:
            if requested is not None and embedder_name_of(requested) == recorded:
                return requested
            if requested is None:
                default = _default_embedder()
                return default if embedder_name_of(default) == recorded else get_embedder(recorded)
            if self.count():
                raise ValueError(f"index was built with {recorded!r}, not {embedder_name_of(requested)!r}")
        chosen = requested or _default_embedder()
        self._conn.execute("INSERT OR REPLACE INTO meta VALUES ('embedder', ?)", (embedder_name_of(chosen),))
        self._conn.commit()
        return chosen

    @property
    def embedder_name(self) -> str:
        """Name of the embedder this index uses."""
        return embedder_name_of(self._embedder)

    # writing -------------------------------------------------------------------------------------------------------

    def add(self, rows: Iterable[IndexRow], batch_size: int = 256) -> int:
        """Index documents (vectors are computed here); commits at the end.

        Args:
            rows: documents to add; keys must be unique
            batch_size: documents embedded per call

        Returns:
            Number of documents added.
        """
        added = 0
        batch: list[IndexRow] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                added += self._add_batch(batch)
                batch = []
        if batch:
            added += self._add_batch(batch)
        self._conn.commit()
        return added

    def _add_batch(self, batch: list[IndexRow]) -> int:
        """Embed and insert one batch."""
        vectors = self._embedder.embed([r.text for r in batch])
        lance_rows = []
        for row, vec in zip(batch, vectors, strict=True):
            blob = None if self._dense_backend == "lancedb" else array("f", vec).tobytes()
            cur = self._conn.execute(
                "INSERT INTO items (key, payload, date, court_n, outcome_n, part, doc_type, authority, vec) VALUES (?,?,?,?,?,?,?,?,?)",
                (row.key, json.dumps(row.payload, ensure_ascii=False, default=str), row.date or None, _norm(row.court),
                 _norm(row.outcome), row.part, row.doc_type, float(row.authority), blob),
            )  # fmt: skip
            item_id = cur.lastrowid
            self._conn.execute("INSERT INTO fts (rowid, text) VALUES (?, ?)", (item_id, row.text))
            self._conn.executemany(
                "INSERT INTO facets VALUES (?, ?, ?)",
                [(item_id, kind, v) for kind, values in row.facets.items() for v in set(values)],
            )
            lance_rows.append({"id": item_id, "vector": vec, "date": row.date or "", "court_n": _norm(row.court) or "",
                               "outcome_n": _norm(row.outcome) or "", "part": row.part or "", "doc_type": row.doc_type or ""})  # fmt: skip
        if self._dense_backend == "lancedb":
            self._lance_add(lance_rows)
        return len(batch)

    # reading -------------------------------------------------------------------------------------------------------

    def count(self) -> int:
        """Number of indexed documents."""
        return int(self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])

    def get(self, key: str) -> dict[str, Any] | None:
        """Payload stored under a key, or None."""
        row = self._conn.execute("SELECT payload FROM items WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def payloads(self, where: str = "", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """All payloads (optionally `WHERE <where>` on the items table), in insertion order."""
        sql = "SELECT payload FROM items" + (f" WHERE {where}" if where else "") + " ORDER BY id"
        return [json.loads(r[0]) for r in self._conn.execute(sql, params)]

    def search(
        self,
        query: str,
        *,
        filters: dict[str, str | None] | None = None,
        facets: dict[str, list[str]] | None = None,
        before: str | None = None,
        k: int = 10,
        candidates: int = 100,
        authority_weight: float = 0.0,
    ) -> list[Hit]:
        """Hybrid search with metadata pre-filters.

        Args:
            query: free text
            filters: exact (case-insensitive) filters on `court`, `outcome`, `part`, `doc_type`; None values are ignored
            facets: any-of filters per facet kind, e.g. {'family': ['BNS 318(4)'], 'factor': ['parity_with_co_accused']}
            before: only documents dated strictly before this ISO date (documents without a date are excluded)
            k: number of hits
            candidates: depth of each ranking before fusion
            authority_weight: share of the final score taken from the stored authority prior, in [0, 1)

        Returns:
            Hits, best first, ties broken by key.
        """
        where, params = self._where(filters or {}, facets or {}, before)
        candidates = max(candidates, k)  # a deep request (k=1000) must not be capped by the fusion depth
        bm25 = self._bm25(query, where, params, candidates)
        dense = self._dense(query, where, params, candidates)
        fused: dict[int, float] = {}
        for ranking in (bm25, dense):
            for rank, item_id in enumerate(ranking, start=1):
                fused[item_id] = fused.get(item_id, 0.0) + 1.0 / (RRF_K + rank)
        if not fused:
            return []
        top = 2.0 / (RRF_K + 1)
        info = self._fetch(list(fused))
        hits = []
        for item_id, rrf in fused.items():
            key, payload, authority = info[item_id]
            score = (1 - authority_weight) * (rrf / top) + authority_weight * authority
            hits.append(Hit(key=key, payload=payload, score=round(score, 6), authority=authority))
        hits.sort(key=lambda h: (-h.score, h.key))
        return hits[:k]

    def _where(self, filters: dict[str, str | None], facets: dict[str, list[str]], before: str | None) -> tuple[str, list[Any]]:
        """SQL conditions (on alias `i`) and parameters for the filters."""
        conds: list[str] = []
        params: list[Any] = []
        if before:
            conds.append("i.date IS NOT NULL AND i.date <> '' AND i.date < ?")
            params.append(before)
        for name, value in filters.items():
            if value is None:
                continue
            if name not in _FILTER_COLUMNS:
                raise ValueError(f"unknown filter {name!r}: use {sorted(_FILTER_COLUMNS)}")
            column = _FILTER_COLUMNS[name]
            conds.append(f"i.{column} = ?")
            params.append(value.strip().lower() if column.endswith("_n") else value)
        for kind, values in facets.items():
            if not values:
                continue
            marks = ",".join("?" for _ in values)
            conds.append(f"i.id IN (SELECT item_id FROM facets WHERE kind = ? AND value IN ({marks}))")
            params.extend([kind, *values])
        return (" AND ".join(conds), params)

    def _bm25(self, query: str, where: str, params: list[Any], limit: int) -> list[int]:
        """Item ids ranked by FTS5 BM25 among the filtered rows."""
        terms = list(dict.fromkeys(t.lower() for t in _TERM.findall(query)))[:MAX_QUERY_TERMS]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in terms)
        sql = "SELECT i.id FROM fts JOIN items i ON i.id = fts.rowid WHERE fts MATCH ?"
        sql += f" AND {where}" if where else ""
        sql += " ORDER BY bm25(fts), i.id LIMIT ?"
        return [r[0] for r in self._conn.execute(sql, [match, *params, limit])]

    def _dense(self, query: str, where: str, params: list[Any], limit: int) -> list[int]:
        """Item ids ranked by cosine similarity among the filtered rows."""
        if not query.strip():
            return []
        qvec = self._embedder.embed([query])[0]
        if not any(qvec):
            return []
        if self._dense_backend == "lancedb":
            return self._lance_search(qvec, where, params, limit)
        sql = "SELECT i.id, i.vec FROM items i" + (f" WHERE {where}" if where else "")
        rows = self._conn.execute(sql, params).fetchall()
        scored = _cosine_rank([(r[0], r[1]) for r in rows if r[1]], qvec)
        return [item_id for item_id, sim in scored[:limit] if sim > 0]

    def _fetch(self, ids: list[int]) -> dict[int, tuple[str, dict[str, Any], float]]:
        """key, payload and authority of the given item ids."""
        out: dict[int, tuple[str, dict[str, Any], float]] = {}
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            marks = ",".join("?" for _ in chunk)
            for item_id, key, payload, authority in self._conn.execute(
                f"SELECT id, key, payload, authority FROM items WHERE id IN ({marks})", chunk
            ):
                out[item_id] = (key, json.loads(payload), float(authority))
        return out

    def close(self) -> None:
        """Close the database."""
        self._conn.close()

    # optional LanceDB dense backend ---------------------------------------------------------------------------------

    def _lance(self):  # noqa: ANN202
        """The LanceDB table (created lazily). Imports `lancedb` only here."""
        if self._lance_table is None:
            try:
                import lancedb
            except ImportError as exc:
                raise ImportError("dense_backend='lancedb' needs the 'lancedb' package (pip install lancedb)") from exc
            if self._lance_dir is None:
                raise ValueError("dense_backend='lancedb' needs a file-backed index or an explicit lance_dir")
            db = lancedb.connect(str(self._lance_dir))
            self._lance_table = db.open_table("vectors") if "vectors" in db.table_names() else None
            self._lance_db = db
        return self._lance_table

    def _lance_add(self, rows: list[dict[str, Any]]) -> None:
        """Append vectors and scalar columns to the LanceDB table."""
        table = self._lance()
        if table is None:
            self._lance_table = self._lance_db.create_table("vectors", data=rows)
        else:
            table.add(rows)

    def _lance_search(self, qvec: list[float], where: str, params: list[Any], limit: int) -> list[int]:
        """Nearest ids from LanceDB, then restricted to the SQL-filtered rows (facets live in SQLite)."""
        table = self._lance()
        if table is None:
            return []
        ids = [int(r["id"]) for r in table.search(qvec).limit(limit * 5).to_list()]
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        sql = f"SELECT i.id FROM items i WHERE i.id IN ({marks})" + (f" AND {where}" if where else "")
        allowed = {r[0] for r in self._conn.execute(sql, [*ids, *params])}
        return [i for i in ids if i in allowed][:limit]


def _cosine_rank(rows: list[tuple[int, bytes]], qvec: list[float]) -> list[tuple[int, float]]:
    """(id, similarity) for each stored vector, best first; vectors are unit length, so the dot product is the cosine."""
    if not rows:
        return []
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        mat = np.frombuffer(b"".join(b for _, b in rows), dtype=np.float32).reshape(len(rows), -1)
        sims = mat @ np.asarray(qvec, dtype=np.float32)
        order = np.argsort(-sims, kind="stable")
        return [(rows[i][0], float(sims[i])) for i in order]
    scored = []
    for item_id, blob in rows:
        vec = array("f")
        vec.frombytes(blob)
        scored.append((item_id, sum(a * b for a, b in zip(vec, qvec, strict=True))))
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored
