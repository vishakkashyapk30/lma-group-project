"""Build IPC<->BNS edges from IPC2BNS-Verify (MIT) with typed edges and text diff (plan §2 source 2).

Expected format (the repository has not been downloaded yet, so the loader is deliberately tolerant): one or more
`*.csv`, `*.json` or `*.jsonl` files under `verify_dir`, each row mapping IPC section(s) to BNS section(s); a cell may
be a string or, in JSON, a list of sections. Files are read as UTF-8 (BOM allowed), UTF-16 or Windows-1252. Column names are
matched case-insensitively against these aliases:

- IPC section: ipc, ipc_section, ipc_sec, old_section, old
- BNS section: bns, bns_section, bns_sec, new_section, new
- IPC text: ipc_text, ipc_description, old_text
- BNS text: bns_text, bns_description, new_text
- change note: remarks, change, comment, comments (a leading "new" / "no equivalent" marks NEW / dropped sections)

Rows with several BNS sections for one IPC section (separated by comma, semicolon or '/') become SPLIT edges, several IPC
sections for one BNS section become MERGED, equal text (after normalising whitespace and case) becomes SAME, differing
text REWORDED with a unified diff, and a BNS section without an IPC section is NEW. Once the real files are downloaded,
adjust the alias lists in `_ALIASES` if its headers differ.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.concordance.refs import make_ref
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge

_ALIASES = {
    "ipc": ("ipc", "ipc_section", "ipc_sec", "old_section", "old"),
    "bns": ("bns", "bns_section", "bns_sec", "new_section", "new"),
    "ipc_text": ("ipc_text", "ipc_description", "old_text"),
    "bns_text": ("bns_text", "bns_description", "new_text"),
    "note": ("remarks", "change", "comment", "comments"),
}
_SPLITTER = re.compile(r"\s*[;,/]\s*|\s+and\s+", re.IGNORECASE)
_NONE_MARKERS = {"", "-", "na", "n/a", "none", "nil", "null", "deleted", "omitted"}


def _pick_raw(row: dict[str, Any], field: str) -> Any:
    """Value of the first column of `row` matching the aliases of `field`, as found (string, list or None)."""
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in _ALIASES[field]:
        if alias in lowered and lowered[alias] is not None:
            return lowered[alias]
    return ""


def _pick(row: dict[str, Any], field: str) -> str:
    """Value of the first column of `row` matching the aliases of `field`, as stripped text."""
    value = _pick_raw(row, field)
    return str(value).strip() if not isinstance(value, list) else ", ".join(str(v).strip() for v in value)


def _sections(cell: str | list[Any]) -> list[str]:
    """Split a cell (a string, or a JSON list) that may name several sections; drop 'none' markers and 'section' words."""
    if isinstance(cell, list):
        return [x for item in cell for x in _sections(str(item))]
    if cell.strip().lower() in _NONE_MARKERS:
        return []
    return [
        re.sub(r"^(?:sections?|s\.)\s*", "", p.strip(), flags=re.IGNORECASE) for p in _SPLITTER.split(cell) if p.strip()
    ]


def _read_text(path: Path) -> str:
    """Read a text file, sniffing the encoding: UTF-8 (BOM allowed), UTF-16 (BOM), else Windows-1252."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _read_rows(verify_dir: str) -> list[dict[str, Any]]:
    """Read every CSV, JSON and JSON-lines file under verify_dir into a list of row dicts."""
    rows: list[dict[str, Any]] = []
    for path in sorted(Path(verify_dir).rglob("*")):
        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows.extend(csv.DictReader(io.StringIO(_read_text(path), newline="")))
        elif suffix == ".json":
            data = json.loads(_read_text(path))
            data = data.get("rows", data.get("mappings", [])) if isinstance(data, dict) else data
            rows.extend(r for r in data if isinstance(r, dict))
        elif suffix == ".jsonl":
            lines = (ln for ln in _read_text(path).splitlines() if ln.strip())
            rows.extend(r for r in map(json.loads, lines) if isinstance(r, dict))
    return rows


def _text_edge(old_ref: str, new_ref: str, old_text: str, new_text: str) -> tuple[ConcordanceEdgeType, str | None]:
    """SAME when both texts match after normalisation, else REWORDED with a unified diff; SAME when no text is given."""
    if not old_text or not new_text:
        return ConcordanceEdgeType.SAME, None
    norm = lambda t: " ".join(t.lower().split())  # noqa: E731
    if norm(old_text) == norm(new_text):
        return ConcordanceEdgeType.SAME, None
    old_one, new_one = " ".join(old_text.split()), " ".join(new_text.split())
    diff = "\n".join(difflib.unified_diff([old_one], [new_one], fromfile=old_ref, tofile=new_ref, lineterm=""))
    return ConcordanceEdgeType.REWORDED, diff


def load_ipc_bns_edges(verify_dir: str, texts: dict[str, str] | None = None) -> list[ConcordanceEdge]:
    """Parse IPC2BNS-Verify files into typed IPC<->BNS edges (see the module docstring for the expected format).

    Args:
        verify_dir: directory holding the downloaded CSV/JSON/JSONL files
        texts: section text by reference ('IPC 420'), used when the Verify rows carry none

    Returns:
        Edges, de-duplicated, in file order.
    """
    texts = texts or {}
    pairs: list[tuple[str, str, str, str]] = []  # (ipc, bns, ipc_text, bns_text); '' marks a missing side
    for row in _read_rows(verify_dir):
        ipcs, bnss = _sections(_pick_raw(row, "ipc")), _sections(_pick_raw(row, "bns"))
        note = _pick(row, "note").lower()
        if not bnss and not ipcs:
            continue
        if not ipcs or note.startswith(("new", "no ipc")):
            pairs.extend(("", b, "", _pick(row, "bns_text") or texts.get(make_ref("BNS", b), "")) for b in bnss)
        elif bnss:
            pairs.extend(
                (
                    i,
                    b,
                    _pick(row, "ipc_text") or texts.get(make_ref("IPC", i), ""),
                    _pick(row, "bns_text") or texts.get(make_ref("BNS", b), ""),
                )
                for i in ipcs
                for b in bnss
            )
    by_ipc: dict[str, set[str]] = defaultdict(set)
    by_bns: dict[str, set[str]] = defaultdict(set)
    for i, b, _, _ in pairs:
        if i:
            by_ipc[i].add(b)
        by_bns[b].add(i)
    edges: dict[tuple[str, str], ConcordanceEdge] = {}
    for i, b, it, bt in pairs:
        new_ref = make_ref("BNS", b)
        if not i:
            edge = ConcordanceEdge(old_ref="", new_ref=new_ref, type=ConcordanceEdgeType.NEW)
        else:
            old_ref = make_ref("IPC", i)
            if len(by_ipc[i]) > 1:
                etype, diff = ConcordanceEdgeType.SPLIT, _text_edge(old_ref, new_ref, it, bt)[1]
            elif len({x for x in by_bns[b] if x}) > 1:
                etype, diff = ConcordanceEdgeType.MERGED, _text_edge(old_ref, new_ref, it, bt)[1]
            else:
                etype, diff = _text_edge(old_ref, new_ref, it, bt)
            edge = ConcordanceEdge(old_ref=old_ref, new_ref=new_ref, type=etype, text_diff=diff)
        edges.setdefault((edge.old_ref, edge.new_ref), edge)
    return list(edges.values())


def write_edges_sqlite(edges: list[ConcordanceEdge], out_path: str) -> int:
    """Write edges to the law.concordance SQLite file (table `edges`), replacing its contents.

    Returns:
        Number of edges written.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(out_path)
    try:
        with conn:
            conn.execute("DROP TABLE IF EXISTS edges")
            conn.execute(
                "CREATE TABLE edges (old_ref TEXT NOT NULL, new_ref TEXT NOT NULL, type TEXT NOT NULL, "
                "text_diff TEXT, PRIMARY KEY (old_ref, new_ref))"
            )
            conn.executemany(
                "INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?)",
                [(e.old_ref, e.new_ref, e.type.value, e.text_diff) for e in edges],
            )
    finally:
        conn.close()
    return len(edges)


def write_edges_jsonl(edges: list[ConcordanceEdge], out_path: str) -> int:
    """Write edges as `concordance_edges.jsonl` (one ConcordanceEdge JSON object per line), the input of the store build.

    Returns:
        Number of edges written.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("".join(e.model_dump_json() + "\n" for e in edges), encoding="utf-8")
    return len(edges)


def read_statute_texts(statutes_path: str) -> dict[str, str]:
    """Section text by reference from a statute file: a JSON list of {code, section, text} rows or the statutes SQLite.

    Args:
        statutes_path: JSON list file or SQLite file (table `statutes`, columns code, section, text)

    Returns:
        Mapping like {'IPC 420': 'text...'}.
    """
    path = Path(statutes_path)
    if path.read_bytes()[:15] == b"SQLite format 3":
        conn = sqlite3.connect(str(path))
        try:
            rows = conn.execute("SELECT code, section, text FROM statutes").fetchall()
        finally:
            conn.close()
    else:
        data = json.loads(_read_text(path))
        rows = [(r["code"], r["section"], r.get("text", "")) for r in data]
    return {make_ref(c, sec): t or "" for c, sec, t in rows}


def build_ipc_bns_edges(verify_dir: str, statutes_path: str, out_path: str) -> int:
    """Write typed edges as JSON lines (the input `concordance_edges.jsonl` of `ConcordanceStore.build`).

    When the Verify files carry no section text, the texts come from the statutes file so the edge type and diff can
    still be computed. A section named in the Verify files but absent from the statutes file cannot be typed and is
    never guessed.

    Args:
        verify_dir: see behaviour
        statutes_path: JSON list or SQLite statute table, or '' to skip
        out_path: JSONL file to write

    Returns:
        Edge count.

    Raises:
        ValueError: when a section in the Verify files is missing from the statutes file.
    """
    texts: dict[str, str] = {}
    if statutes_path and Path(statutes_path).is_file():
        texts = read_statute_texts(statutes_path)
    edges = load_ipc_bns_edges(verify_dir, texts)
    if texts:
        missing = sorted({r for e in edges for r in (e.old_ref, e.new_ref) if r and r not in texts})
        if missing:
            raise ValueError(f"sections not in the statutes file, cannot type their edges: {', '.join(missing)}")
    return write_edges_jsonl(edges, out_path)
