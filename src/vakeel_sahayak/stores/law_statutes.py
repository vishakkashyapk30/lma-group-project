"""law.statutes store: one row per section of IPC, BNS, CrPC, BNSS plus NDPS s.37, UAPA s.43D(5), PMLA s.45 (about 1,000 rows). Index: exact + BM25. (plan §5.1)"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

from vakeel_sahayak.pipelines.concordance.refs import normalise_code, normalise_section
from vakeel_sahayak.schemas.enums import Shelf, StoreName
from vakeel_sahayak.schemas.store_rows import StatuteRow
from vakeel_sahayak.stores.base import SharedStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS statutes (
    code TEXT NOT NULL, section TEXT NOT NULL, text TEXT NOT NULL,
    max_punishment TEXT, bailable INTEGER, cognisable INTEGER,
    PRIMARY KEY (code, section)
)"""
_NOTE = " (summary from configs/bail_sections.yaml; bare-act text arrives with the Open India Law load)"
_TOKEN = re.compile(r"[a-z0-9]+")


def seed_rows() -> list[StatuteRow]:
    """Offline seed: only sections the plan names (bail table, BNS 318(4), IPC 420, NDPS 37, UAPA 43D(5), PMLA 45)."""
    from vakeel_sahayak.config import load_config

    rows = [
        StatuteRow(
            code="BNS", section="318(4)", max_punishment="7 years", bailable=False,
            text="Cheating and thereby dishonestly inducing delivery of property (plan §7.1 example; IPC 420 equivalent).",
        ),
        StatuteRow(code="IPC", section="420", text="Cheating and dishonestly inducing delivery of property (BNS 318(4) equivalent)."),
        StatuteRow(code="NDPS", section="37", text="Twin conditions for bail under the NDPS Act."),
        StatuteRow(code="UAPA", section="43D(5)", text="Twin conditions for bail under the UAPA."),
        StatuteRow(code="PMLA", section="45", text="Twin conditions for bail under the PMLA."),
    ]  # fmt: skip
    for row in load_config().bail_sections:
        topic = str(row["topic"]) + _NOTE
        rows.append(StatuteRow(code="CrPC", section=normalise_section(str(row["crpc"])), text=topic))
        rows.append(StatuteRow(code="BNSS", section=normalise_section(str(row["bnss"])), text=topic))
    return rows


class StatuteStore(SharedStore):
    """law.statutes store: one row per section of IPC, BNS, CrPC, BNSS plus NDPS s.37, UAPA s.43D(5), PMLA s.45 (about 1,000 rows). Index: exact + BM25."""

    name = StoreName.LAW_STATUTES
    shelf = Shelf.LAW
    index_kind = "exact + BM25"

    def __init__(self) -> None:
        """Create an unopened store."""
        self._conn: sqlite3.Connection | None = None
        self._rows: list[StatuteRow] = []
        self._df: Counter[str] = Counter()
        self._tokens: list[list[str]] = []

    def open(self, path: str | None = None) -> None:
        """Open the store: the SQLite file at `path` (default stores/law/statutes.sqlite), or the in-memory seed if absent.

        Args:
            path: see behaviour
        """
        from vakeel_sahayak.config import load_config

        cfg = load_config()
        file_name = cfg.stores["law"]["statutes"]["path"]
        target = Path(path) if path else Path(cfg.paths.stores_dir) / file_name
        if target.is_dir():  # an out_dir written by `build`
            target = target / Path(file_name).name
        if target.is_file():
            self._conn = sqlite3.connect(str(target), check_same_thread=False)
        else:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.execute(_SCHEMA)
            self._conn.executemany(
                "INSERT OR IGNORE INTO statutes VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (r.code, r.section, r.text, r.max_punishment, _tri(r.bailable), _tri(r.cognisable))
                    for r in seed_rows()
                ],
            )
        self._load()

    def close(self) -> None:
        """Close."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def count(self) -> int:
        """Row count.

        Returns:
            Count.
        """
        return len(self._rows)

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build the SQLite file from `source_dir/statutes.jsonl` (one StatuteRow JSON per line); without it, from the offline seed.

        Args:
            source_dir: folder holding statutes.jsonl (Open India Law bare-act extraction)
            out_dir: folder that receives the SQLite file named in configs/stores.yaml
        """
        from vakeel_sahayak.config import load_config
        from vakeel_sahayak.pipelines.text_utils import read_jsonl

        rows: list[StatuteRow] = []
        for raw in read_jsonl(Path(source_dir) / "statutes.jsonl"):
            try:
                row = StatuteRow.model_validate(raw)
                rows.append(row.model_copy(update={"code": normalise_code(row.code), "section": normalise_section(row.section)}))
            except ValueError:  # a malformed line or an unknown act is skipped, not fatal
                continue
        if not rows:
            rows = seed_rows()
        rows = _merge_gap_rows(rows, Path(source_dir).parent / "gaps" / "statutes")
        file_name = Path(load_config().stores["law"]["statutes"]["path"]).name
        target = Path(out_dir) / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.unlink(missing_ok=True)
        conn = sqlite3.connect(str(target))
        try:
            with conn:
                conn.execute(_SCHEMA)
                conn.executemany(
                    "INSERT OR REPLACE INTO statutes VALUES (?, ?, ?, ?, ?, ?)",
                    [(r.code, r.section, r.text, r.max_punishment, _tri(r.bailable), _tri(r.cognisable)) for r in rows],
                )
        finally:
            conn.close()

    def get(self, code: str, section: str) -> StatuteRow:
        """Exact lookup.

        Args:
            code: act code, any spelling ('crpc', 'CrPC')
            section: section, any spelling ('s. 436a')

        Returns:
            StatuteRow.

        Raises:
            LookupError: if the section is not in the store.
        """
        want = (normalise_code(code), normalise_section(section))
        for row in self._rows:
            if (row.code, row.section) == want:
                return row
        raise LookupError(f"{want[0]} {want[1]} not found in law.statutes")

    def search(self, query: str, code: str | None = None, k: int = 5) -> list[StatuteRow]:
        """BM25 over the text.

        Args:
            query: see behaviour
            code: restrict to one act
            k: number of rows

        Returns:
            Rows, best first; rows with no matching term are omitted.
        """
        wanted = normalise_code(code) if code else None
        q = _TOKEN.findall(query.lower())
        n = len(self._rows)
        avg = (sum(len(t) for t in self._tokens) / n) if n else 1.0
        scored: list[tuple[float, int]] = []
        for i, (row, toks) in enumerate(zip(self._rows, self._tokens, strict=True)):
            if wanted and row.code != wanted:
                continue
            tf = Counter(toks)
            score = 0.0
            for term in set(q):
                if tf[term]:
                    idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                    score += idf * tf[term] * 2.2 / (tf[term] + 1.2 * (0.25 + 0.75 * len(toks) / avg))
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda s: (-s[0], s[1]))
        return [self._rows[i] for _, i in scored[:k]]

    def _load(self) -> None:
        """Read all rows and the BM25 statistics (the table is about 1,000 rows)."""
        assert self._conn
        cur = self._conn.execute("SELECT code, section, text, max_punishment, bailable, cognisable FROM statutes")
        self._rows = [
            StatuteRow(code=c, section=s, text=t, max_punishment=m, bailable=_bool(b), cognisable=_bool(g))
            for c, s, t, m, b, g in cur.fetchall()
        ]
        self._tokens = [_TOKEN.findall(f"{r.code} {r.section} {r.text}".lower()) for r in self._rows]
        self._df = Counter(term for toks in self._tokens for term in set(toks))


def _merge_gap_rows(rows: list[StatuteRow], gaps_dir: Path) -> list[StatuteRow]:
    """Add rows from `<gaps_dir>/*.jsonl` (official-source statutes the Open India Law release lacks); a gap row replaces the same (code, section)."""
    from vakeel_sahayak.pipelines.text_utils import read_jsonl

    merged = {(r.code, r.section): r for r in rows}
    for path in sorted(gaps_dir.glob("*.jsonl")):
        for raw in read_jsonl(path):
            try:
                row = StatuteRow.model_validate({k: v for k, v in raw.items() if k in StatuteRow.model_fields})
            except ValueError:
                continue
            row = row.model_copy(update={"code": normalise_code(row.code), "section": normalise_section(row.section)})
            merged[(row.code, row.section)] = row
    return list(merged.values())


def _tri(value: bool | None) -> int | None:
    """Store a nullable bool as 0/1/NULL."""
    return None if value is None else int(value)


def _bool(value: int | None) -> bool | None:
    """Read a nullable bool."""
    return None if value is None else bool(value)
