"""Hybrid search index: BM25 (SQLite FTS5) plus dense vectors, with metadata pre-filters (plan §5.1, §5.5).

SQLite is the always-available backend: rows, the FTS5 full-text table (BM25) and, by default, the dense vectors in one
file, so the stores run on a laptop without torch or LanceDB. LanceDB can hold the dense vectors instead
(`dense_backend="lancedb"`; imported lazily, needs the `lancedb` package). The dense side uses any `Embedder`
(BGE-M3 when installed, otherwise the hashed n-gram fallback, see `models/embeddings.py`).

Search: metadata filters narrow the candidate set first (SQL), then BM25 and cosine rankings are fused by reciprocal rank
fusion, and an authority prior can be blended in. The embedder that built an index is recorded in it and reused at query
time, so query and document vectors always come from the same model.

Opt-in BGE-M3 side vectors (`VS_STORES=bge`, default off): the four vector stores can carry a second vector set in a side
file next to the store (`reasoning.sqlite` -> `reasoning.bge.sqlite`, built by `pipelines/store_builders/bge_vectors.py`)
holding one fp16 BGE-M3 vector per item id. With the opt-in on, a store opened with `side_vectors="bge"` takes its dense
ranking from the side file and embeds queries with BGE-M3 (the local copy under models/hf); BM25, filters and payloads
still come from the main file, which is never modified. A missing side file, a side file that does not match the store,
or missing BGE-M3 weights raise `SideVectorsError` naming the fix: the run never falls back to the hashed vectors.
Without the opt-in nothing is read from the side file and every result is byte-identical to the default.
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

from vakeel_sahayak.models.embeddings import BGE_M3_NAME as BGE_M3_SIDE_NAME
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


STORES_ENV = "VS_STORES"
SIDE_BGE = "bge"
SIDE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS vectors (id INTEGER PRIMARY KEY, vec BLOB NOT NULL);
"""
BGE_MODEL_ID = "BAAI/bge-m3"


class SideVectorsError(RuntimeError):
    """The BGE-M3 side vectors were asked for (`VS_STORES=bge`) but cannot be used; the message names the fix."""


def store_vectors_mode() -> str:
    """Which vector set the shared vector stores search: 'default' (the vectors inside each store) or 'bge' (`VS_STORES=bge`).

    Read from the environment only (never inferred from torch or sentence-transformers being installed).

    Raises:
        ValueError: for a value other than unset, '', 'default', 'hashed' or 'bge'.
    """
    import os

    value = (os.environ.get(STORES_ENV) or "").strip().lower()
    if value in ("", "default", "hashed", "hashed-ngram"):
        return "default"
    if value in (SIDE_BGE, "bge-m3", "bgem3"):
        return SIDE_BGE
    raise ValueError(f"{STORES_ENV}={value!r}: use 'bge' (opt-in BGE-M3 side vectors) or leave it unset")


def side_vectors_path(store_path: str | Path, kind: str = SIDE_BGE) -> Path:
    """The side file of a store file: `caselaw/reasoning.sqlite` -> `caselaw/reasoning.bge.sqlite`."""
    p = Path(store_path)
    return p.with_name(f"{p.stem}.{kind}.sqlite")


def side_meta(side_path: str | Path) -> dict[str, str]:
    """The meta table of a side file (empty when the file does not exist)."""
    p = Path(side_path)
    if not p.is_file():
        return {}
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        return {k: v for k, v in conn.execute("SELECT key, value FROM meta")}
    finally:
        conn.close()


def write_side_vectors(side_path: str | Path, ids: Any, vectors: Any, meta: dict[str, Any], *, chunk: int = 20_000) -> int:
    """Write a side file: one fp16 vector per item id, plus the meta table (`embedder`, `dim`, `dtype`, `rows` are set here).

    The file is written next to its final name and renamed at the end, so a half-written side file never exists under it.

    Args:
        side_path: target file (replaced)
        ids: item ids (int), any order; must be unique
        vectors: array-like (n, dim); stored as float16
        meta: extra meta entries (model revision, corpus text hash, ...)
        chunk: rows per insert batch

    Returns:
        Rows written.
    """
    import numpy as np

    ids_a = np.asarray(ids, dtype=np.int64)
    vec_a = np.asarray(vectors, dtype=np.float16)
    if vec_a.ndim != 2 or len(ids_a) != len(vec_a):
        raise ValueError(f"ids ({len(ids_a)}) and vectors {vec_a.shape} do not line up")
    if len(np.unique(ids_a)) != len(ids_a):
        raise ValueError("side vector ids must be unique")
    target = Path(side_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(str(tmp))
    try:
        conn.executescript(SIDE_SCHEMA)
        for start in range(0, len(ids_a), chunk):
            conn.executemany(
                "INSERT INTO vectors (id, vec) VALUES (?, ?)",
                ((int(i), v.tobytes()) for i, v in zip(ids_a[start : start + chunk], vec_a[start : start + chunk], strict=True)),
            )
        full = {**{k: str(v) for k, v in meta.items()}, "embedder": str(meta.get("embedder", BGE_M3_SIDE_NAME)),
                "dim": str(vec_a.shape[1]), "dtype": "float16", "rows": str(len(ids_a))}  # fmt: skip
        conn.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", sorted(full.items()))
        conn.commit()
    finally:
        conn.close()
    tmp.replace(target)
    return len(ids_a)


def read_side_vectors(side_path: str | Path) -> tuple[Any, Any]:
    """(ids int64, vectors float32) of a side file in id order; the fp16 vectors are widened to float32 here."""
    import numpy as np

    meta = side_meta(side_path)
    dim, n = int(meta["dim"]), int(meta["rows"])
    conn = sqlite3.connect(f"file:{Path(side_path)}?mode=ro", uri=True)
    try:
        ids = np.empty(n, dtype=np.int64)
        mat = np.empty((n, dim), dtype=np.float16)
        i = -1
        for i, (item_id, blob) in enumerate(conn.execute("SELECT id, vec FROM vectors ORDER BY id")):
            if i >= n:
                raise SideVectorsError(f"{side_path}: more vectors than its meta 'rows' ({n})")
            ids[i] = item_id
            mat[i] = np.frombuffer(blob, dtype=np.float16)
        if i + 1 != n:
            raise SideVectorsError(f"{side_path}: {i + 1} vectors, its meta says {n}")
    finally:
        conn.close()
    return ids, mat.astype(np.float32)


_BGE_QUERY: dict[int | None, Embedder] = {}  # one loaded BGE-M3 per process, shared by the four stores


def _bge_query_embedder(max_length: int | None = None) -> Embedder:
    """BGE-M3 for queries against the side vectors, truncated like the documents were (`max_length` from the side file's meta);
    the local copy under models/hf is required (no silent Hub download)."""
    from vakeel_sahayak.models.embeddings import bge_m3_available
    from vakeel_sahayak.models.nli import local_checkpoint

    if not bge_m3_available():
        raise SideVectorsError(
            f"{STORES_ENV}=bge embeds queries with BGE-M3, which needs sentence-transformers and torch: "
            "pip install 'vakeel_sahayak[models]' (CPU torch is enough), or unset VS_STORES"
        )
    if local_checkpoint(BGE_MODEL_ID) is None:
        raise SideVectorsError(
            f"{STORES_ENV}=bge needs the BGE-M3 weights in models/hf/BAAI--bge-m3 (or VS_MODELS_DIR): run `make models`, or unset VS_STORES"
        )
    if max_length not in _BGE_QUERY:
        from vakeel_sahayak.models.embeddings import Bgem3EmbeddingClient

        _BGE_QUERY[max_length] = Bgem3EmbeddingClient(max_seq_length=max_length)
    return _BGE_QUERY[max_length]


BM25_PRUNE_MIN_ROWS = 20_000
BM25_COMMON_SHARE = 0.15
_DF_CACHE: dict[tuple[Any, str], int] = {}
_ROWS: dict[tuple[str, int, int], int] = {}
_MATRICES: dict[tuple[str, int, int], tuple[Any, Any]] = {}  # per-process cache of the dense matrices of file-backed indexes


class HybridIndex:
    """BM25 + dense index in one SQLite file (or in memory), see the module docstring."""

    def __init__(
        self,
        path: str | Path | None = None,
        embedder: Embedder | None = None,
        *,
        dense_backend: str = "sqlite",
        lance_dir: str | Path | None = None,
        side_vectors: str | None = None,
        side_embedder: Embedder | None = None,
    ) -> None:
        """Open or create an index.

        Args:
            path: SQLite file; None or ':memory:' keeps it in memory
            embedder: embedder for a new index; an existing index keeps the embedder recorded in it
            dense_backend: 'sqlite' (vectors in the file) or 'lancedb' (optional, lazy import)
            lance_dir: LanceDB directory when `dense_backend='lancedb'`
            side_vectors: None (default) searches the vectors in the file; 'bge' searches the BGE-M3 side file
                (`side_vectors_path`), read-only; the shared vector stores pass `store_vectors_mode()` here
            side_embedder: query embedder for the side vectors (tests); None loads BGE-M3 from models/hf

        Raises:
            ValueError: when `embedder` differs from the one recorded in an existing, non-empty index.
            SideVectorsError: with `side_vectors='bge'`, when the side file or the BGE-M3 weights are missing or the side file does not match.
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
        self._matrix: tuple[Any, Any] | None = None  # (ids, vectors) of every row, loaded on the first dense search (see `_dense`)
        self._embedder = self._resolve_embedder(embedder)
        self._side_path: Path | None = None
        self._side_meta: dict[str, str] = {}
        self._dense_embedder: Embedder = self._embedder
        if side_vectors not in (None, "default"):
            self._open_side(side_vectors, side_embedder)

    # setup ---------------------------------------------------------------------------------------------------------

    def _open_side(self, kind: str, side_embedder: Embedder | None) -> None:
        """Check and attach the side vector file (`side_vectors='bge'`); the matrix itself is read on the first dense search."""
        if kind != SIDE_BGE:
            raise ValueError(f"unknown side vector set {kind!r}: use 'bge'")
        if self.path is None:
            raise SideVectorsError(f"{STORES_ENV}=bge needs a file-backed store (an in-memory index has no side file)")
        if self._dense_backend != "sqlite":
            raise SideVectorsError(f"{STORES_ENV}=bge works with dense_backend='sqlite' only, not {self._dense_backend!r}")
        side = side_vectors_path(self.path, kind)
        fix = (
            "build it with `python -m vakeel_sahayak.pipelines.store_builders.bge_vectors apply` (docs/handoff/bge-vectors-2026-10-28.md), "
            "install it with `make data` (bundle part 'bge'), or unset VS_STORES"
        )
        if not side.is_file():
            raise SideVectorsError(f"{STORES_ENV}=bge: no BGE-M3 side file {side} for store {self.path}: {fix}")
        meta = side_meta(side)
        if meta.get("embedder") != BGE_M3_SIDE_NAME:
            raise SideVectorsError(f"{side} records embedder {meta.get('embedder')!r}, not {BGE_M3_SIDE_NAME!r}: {fix}")
        rows = self.count()
        if int(meta.get("rows") or -1) != rows:
            raise SideVectorsError(f"{side} holds {meta.get('rows')} vectors but {self.path} has {rows} rows (stale side file): {fix}")
        self._side_path, self._side_meta = side, meta
        max_length = int(meta["max_length"]) if meta.get("max_length") else None
        self._dense_embedder = side_embedder if side_embedder is not None else _bge_query_embedder(max_length)

    @property
    def store_embedder(self) -> str:
        """Name of the embedder behind the dense ranking: the file's own, or 'bge-m3' with the side vectors."""
        if self._side_path is not None:
            return self._side_meta["embedder"]
        return embedder_name_of(self._embedder)

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
        if self._side_path is not None:
            raise SideVectorsError(f"{self.path} is open with the read-only BGE-M3 side vectors ({STORES_ENV}=bge): unset VS_STORES to write to it")
        added = 0
        self._matrix = None  # the cached vectors no longer cover every row
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
        key_prefixes: list[str] | None = None,
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
            key_prefixes: only rows whose key starts with one of these (S5 graph expansion: `'DLHC-2022-1187#'` selects one
                judgment's paragraphs); None or empty leaves the rows unrestricted

        Returns:
            Hits, best first, ties broken by key.
        """
        where, params = self._where(filters or {}, facets or {}, before)
        if key_prefixes:
            marks = " OR ".join("substr(i.key, 1, ?) = ?" for _ in key_prefixes)
            where = f"({marks})" + (f" AND {where}" if where else "")
            params = [v for p in key_prefixes for v in (len(p), p)] + list(params)
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
        terms = self._informative_terms(terms)
        match = " OR ".join(f'"{t}"' for t in terms)
        sql = "SELECT i.id FROM fts JOIN items i ON i.id = fts.rowid WHERE fts MATCH ?"
        sql += f" AND {where}" if where else ""
        sql += " ORDER BY bm25(fts), i.id LIMIT ?"
        return [r[0] for r in self._conn.execute(sql, [match, *params, limit])]

    def _informative_terms(self, terms: list[str]) -> list[str]:
        """On a large store, drop the query terms that occur in more than `BM25_COMMON_SHARE` of the rows (at least the 2 rarest stay).

        FTS5 scores every row a term matches, so a query holding 'of', 'is' or 'bail' (in 90% of 161,000 bail paragraphs) ranked the whole store:
        about 150 seconds per search. Such terms carry almost no BM25 weight, and the dense ranking in the fusion still sees the whole query.
        Stores under `BM25_PRUNE_MIN_ROWS` rows (every test fixture) and `VS_BM25_PRUNE=0` keep every term. The document counts come from
        a doclist-only `count(*)` per term, cached per store file."""
        import os

        if len(terms) < 3 or os.environ.get("VS_BM25_PRUNE", "1") == "0":
            return terms
        total = self._row_count()
        if total < BM25_PRUNE_MIN_ROWS:
            return terms
        key = self._file_key() or ("memory", id(self), 0)
        df: dict[str, int] = {}
        for t in terms:
            if (key, t) not in _DF_CACHE:
                _DF_CACHE[(key, t)] = int(self._conn.execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (f'"{t}"',)).fetchone()[0])
            df[t] = _DF_CACHE[(key, t)]
        keep = [t for t in terms if df[t] <= BM25_COMMON_SHARE * total]
        if len(keep) < 2:
            keep = sorted(terms, key=lambda t: (df[t], terms.index(t)))[:2]
            keep.sort(key=terms.index)
        return keep

    def _row_count(self) -> int:
        """Rows in the index (cached for a file-backed index, whose rows do not change while it is searched)."""
        key = self._file_key()
        if key is not None and key in _ROWS:
            return _ROWS[key]
        n = self.count()
        if key is not None:
            _ROWS[key] = n
        return n

    def _dense(self, query: str, where: str, params: list[Any], limit: int) -> list[int]:
        """Item ids ranked by cosine similarity among the filtered rows."""
        if not query.strip():
            return []
        qvec = self._dense_embedder.embed([query])[0]
        if not any(qvec):
            return []
        if self._dense_backend == "lancedb":
            return self._lance_search(qvec, where, params, limit)
        if self._side_path is not None:
            return self._dense_cached(self._load_side_matrix(), qvec, where, params, limit)
        matrix = self._load_matrix()
        if matrix is not None:
            return self._dense_cached(matrix, qvec, where, params, limit)
        sql = "SELECT i.id, i.vec FROM items i" + (f" WHERE {where}" if where else "")
        rows = self._conn.execute(sql, params).fetchall()
        scored = _cosine_rank([(r[0], r[1]) for r in rows if r[1]], qvec)
        return [item_id for item_id, sim in scored[:limit] if sim > 0]

    def _load_matrix(self) -> tuple[Any, Any] | None:
        """Every row's id and vector as numpy arrays, read once per open index (None without numpy or when no row has a vector).

        A file-backed store of 100,000+ rows otherwise re-reads all its vector blobs (hundreds of MB, interleaved with the payload
        text) on every search, which took tens of seconds per call; the cache makes later searches a filtered matrix product.
        The ranking is the same (cosine, ties by id); `add` drops the cache."""
        if self._matrix is not None:
            return self._matrix or None  # type: ignore[return-value]
        try:
            import numpy as np
        except ImportError:
            return None
        key = self._file_key()
        if key is not None and key in _MATRICES:  # the tools open and close a store per call: the cache outlives the instance, per process
            self._matrix = _MATRICES[key]
            return self._matrix
        ids, blobs = [], []
        for item_id, blob in self._conn.execute("SELECT id, vec FROM items WHERE vec IS NOT NULL ORDER BY id"):
            ids.append(item_id)
            blobs.append(blob)
        if not ids:
            self._matrix = ()  # type: ignore[assignment]
            return None
        mat = np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(ids), -1)
        self._matrix = (np.asarray(ids, dtype=np.int64), mat)
        if key is not None:
            _MATRICES[key] = self._matrix
        return self._matrix

    def _load_side_matrix(self) -> tuple[Any, Any]:
        """The side file's ids and vectors (fp16 on disk, float32 in memory), read once per process and checked against the store's ids."""
        import numpy as np

        assert self._side_path is not None
        st = self._side_path.stat()
        key = (str(self._side_path.resolve()), st.st_mtime_ns, st.st_size)
        if key in _MATRICES:
            return _MATRICES[key]
        ids, mat = read_side_vectors(self._side_path)
        own = np.fromiter((r[0] for r in self._conn.execute("SELECT id FROM items ORDER BY id")), dtype=np.int64)
        if len(own) != len(ids) or not np.array_equal(own, ids):
            raise SideVectorsError(
                f"{self._side_path} does not cover the item ids of {self.path} (stale side file): rebuild it with "
                "`python -m vakeel_sahayak.pipelines.store_builders.bge_vectors apply`, or unset VS_STORES"
            )
        _MATRICES[key] = (ids, mat)
        return _MATRICES[key]

    def _file_key(self) -> tuple[str, int, int] | None:
        """(path, mtime, size) of a file-backed index, so a rebuilt store never reuses stale vectors; None in memory."""
        if self.path is None:
            return None
        st = self.path.stat()
        return (str(self.path.resolve()), st.st_mtime_ns, st.st_size)

    def _dense_cached(self, matrix: tuple[Any, Any], qvec: list[float], where: str, params: list[Any], limit: int) -> list[int]:
        """Cosine ranking over the cached matrix, restricted to the rows the SQL filter allows."""
        import numpy as np

        ids, mat = matrix
        if where:
            allowed = np.fromiter((r[0] for r in self._conn.execute("SELECT i.id FROM items i WHERE " + where, params)), dtype=np.int64)
            keep = np.isin(ids, allowed, assume_unique=True)
            ids, mat = ids[keep], mat[keep]
        if not len(ids):
            return []
        sims = mat @ np.asarray(qvec, dtype=np.float32)
        order = np.argsort(-sims, kind="stable")[:limit]
        return [int(ids[i]) for i in order if sims[i] > 0]

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


VECTOR_STORES = ("caselaw.reasoning", "caselaw.similar", "advocacy.arguments", "advocacy.objections")


def _main_embedder(path: Path) -> str | None:
    """The embedder recorded in a store file (read-only), None when the file or the record is missing."""
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='embedder'").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def store_vectors_manifest() -> dict[str, Any]:
    """What the run's dense retrieval searched, for the run manifest: `mode` ('default' or 'bge', from VS_STORES), `store_embedder`
    (the one embedder behind the four vector stores, 'mixed' when they differ, None when no store is built) and, per store, the
    embedder of the file and, with the opt-in, the side file's model revision, row count and corpus text hash. Reads meta tables only."""
    from vakeel_sahayak.schemas.enums import StoreName
    from vakeel_sahayak.stores.paths import resolve_shared_path

    mode = store_vectors_mode()
    stores: dict[str, Any] = {}
    for name in VECTOR_STORES:
        path = Path(resolve_shared_path(StoreName(name), None))
        entry: dict[str, Any] = {"embedder": _main_embedder(path)}
        if mode == SIDE_BGE:
            meta = side_meta(side_vectors_path(path))
            entry = {"embedder": meta.get("embedder"), "file_embedder": entry["embedder"], "side_file": side_vectors_path(path).name,
                     "model_revision": meta.get("model_revision"), "rows": meta.get("rows"), "text_sha256": meta.get("text_sha256")}  # fmt: skip
        stores[name] = entry
    names = {e["embedder"] for e in stores.values() if e["embedder"]}
    embedder = None if not names else (names.pop() if len(names) == 1 else "mixed")
    return {"mode": mode, "store_embedder": embedder, "stores": stores}
