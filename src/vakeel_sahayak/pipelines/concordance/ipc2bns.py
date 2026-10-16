"""Build IPC<->BNS edges from IPC2BNS-Verify (MIT) with typed edges and text diff (plan §2 source 2).

**Real layout** (repository `MS-406/IPC2BNS-Verify`, commit 8d3e770; `verify_dir` is its root or a copy of the files below):

- `data/eval_ground_truth/concordance_v1.csv`: header `ipc_section,bns_section,status`, 563 rows. The header is misleading: the
  first column is a generated question, the second holds a Python-literal dict
  `{'IPC Section', 'IPC Heading', 'IPC Descriptions', 'BNS Section', 'BNS Heading', 'BNS description'}` and the third is
  always `exact`. `BNS Section` is a clause-level reference ('318(4)', '8(4), (5)', '331(2, 4)', '351(2) & (3)', '326(a)',
  '180 Explanation') or 'Repealed in BNS' (29 rows: no BNS counterpart, so no edge is written). The two descriptions are the bare-act
  text behind an act-title line, a number and a heading; they are reduced to the body before comparing.
- `data/phase2_cleaned/bns_sections.jsonl`: the authors' relationship labels (`relationship_type`: renumbered, modified, merged,
  split, new_in_bns); the BNS sections labelled `new_in_bns` become NEW edges (no IPC counterpart). The other labels are not used: the
  edge types are computed from the section mapping and the texts, as in the plan.

Other files of the repository (benchmarks, reports) are ignored when `concordance_v1.csv` is found.

**Generic layout** (used when `concordance_v1.csv` is absent, and by the unit tests): one or more `*.csv`, `*.json` or `*.jsonl`
files under `verify_dir`, each row mapping IPC section(s) to BNS section(s); a cell may be a string or, in JSON, a list of sections.
Files are read as UTF-8 (BOM allowed), UTF-16 or Windows-1252. Column names are matched case-insensitively against these aliases:

- IPC section: ipc, ipc_section, ipc_sec, old_section, old
- BNS section: bns, bns_section, bns_sec, new_section, new
- IPC text: ipc_text, ipc_description, old_text
- BNS text: bns_text, bns_description, new_text
- change note: remarks, change, comment, comments (a leading "new" / "no equivalent" marks NEW / dropped sections)

Rows with several BNS sections for one IPC section (separated by comma, semicolon, '&' or '/') become SPLIT edges, several IPC
sections for one BNS section become MERGED, equal text (after normalising whitespace and case) becomes SAME, differing
text REWORDED with a unified diff, and a BNS section without an IPC section is NEW.
"""

from __future__ import annotations

import ast
import csv
import difflib
import io
import json
import logging
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.concordance.refs import make_ref
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge

log = logging.getLogger(__name__)

_ALIASES = {
    "ipc": ("ipc", "ipc_section", "ipc_sec", "old_section", "old"),
    "bns": ("bns", "bns_section", "bns_sec", "new_section", "new"),
    "ipc_text": ("ipc_text", "ipc_description", "old_text"),
    "bns_text": ("bns_text", "bns_description", "new_text"),
    "note": ("remarks", "change", "comment", "comments"),
}
_SPLITTER = re.compile(r"\s*[;,/&]\s*|\s+and\s+", re.IGNORECASE)
_NONE_MARKERS = {"", "-", "na", "n/a", "none", "nil", "null", "deleted", "omitted"}
_NONE_PREFIXES = ("repealed", "omitted", "not applicable", "no equivalent", "no bns", "no ipc")
VERIFY_CSV = "concordance_v1.csv"
_COMMA_IN_PARENS = re.compile(r"(\d+[A-Za-z]*)\(([^()]*,[^()]*)\)")


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
    """Split a cell (a string, or a JSON list) that may name several sections; drop 'none' markers and 'section' words.

    '8(4), (5)' gives ['8(4)', '8(5)'] (a clause alone takes the section before it), '331(2, 4)' gives ['331(2)', '331(4)'] and
    a trailing 'Explanation' is dropped ('180 Explanation' is section 180).
    """
    if isinstance(cell, list):
        return [x for item in cell for x in _sections(str(item))]
    low = cell.strip().lower()
    if low in _NONE_MARKERS or low.startswith(_NONE_PREFIXES):
        return []
    cell = _COMMA_IN_PARENS.sub(lambda m: ", ".join(f"{m.group(1)}({c.strip()})" for c in m.group(2).split(",")), cell)
    out: list[str] = []
    for part in _SPLITTER.split(cell):
        part = re.sub(r"^(?:sections?|s\.)\s*", "", part.strip(), flags=re.IGNORECASE)
        part = re.sub(r"\s+explanations?\b.*$", "", part, flags=re.IGNORECASE)
        if not part:
            continue
        if part.startswith("(") and out:
            part = re.match(r"\d+[A-Za-z]*", out[-1]).group(0) + part if re.match(r"\d+[A-Za-z]*", out[-1]) else part
        out.append(part)
    return out


def _read_text(path: Path) -> str:
    """Read a text file, sniffing the encoding: UTF-8 (BOM allowed), UTF-16 (BOM), else Windows-1252."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _body(text: str, heading: str, act_title: re.Pattern[str]) -> str:
    """Reduce a bare-act description to its body: no act-title line, chapter title, section number and heading, clause marker or footnote marks."""
    lines = [ln.strip() for ln in text.replace("\xa0", " ").splitlines() if ln.strip()]
    if lines and act_title.match(lines[0].lstrip('"')):
        lines = lines[1:]
    if lines:
        lines[0] = lines[0].lstrip('" ')
    number = re.compile(r"^\d+[A-Za-z]*\s*\.(?:\s+(.*))?$")
    start = next((k for k, ln in enumerate(lines[:4]) if number.match(ln)), None)
    if start is not None:  # drops a chapter line before the number line; a heading ending in '.' (BNS style) goes with its line
        lines = lines[start:]
        rest = (number.match(lines[0]).group(1) or "").strip()
        lines = lines[1:] if not rest or rest.endswith(".") else [rest, *lines[1:]]
    body = " ".join(lines)
    if heading.strip():
        words = r"\s+".join(re.escape(w) for w in heading.strip().rstrip(".").split())
        body = re.sub(r"^\s*" + words + r"[\s.\u2014\u2013-]*", "", body, count=1, flags=re.IGNORECASE)
    body = re.sub(r"^\s*\(\w{1,3}\)\s*", "", body)
    body = re.sub(r"\b\d{1,2}\[|\](?=\s|[.,;:]|$)", "", body)
    body = re.sub(r"(?<=[.;])\s+(?:Of|OF)\s+(?:[A-Z][A-Za-z'-]*\s*,?\s*(?:and\s+|of\s+|the\s+)?){1,12}$", "", " ".join(body.split()))  # next chapter's title
    return " ".join(body.split())


_IPC_TITLE = re.compile(r"(?i)^(?:the\s+)?indian\s+penal\s+code")
_BNS_TITLE = re.compile(r"(?i)^(?:the\s+)?bharatiya\s+nyaya\s+sanhita")


def _read_verify_csv(path: Path) -> list[dict[str, Any]]:
    """Rows of `concordance_v1.csv` as {ipc, bns, ipc_text, bns_text}; rows whose cell cannot be parsed are skipped."""
    rows: list[dict[str, Any]] = []
    for record in list(csv.reader(io.StringIO(_read_text(path), newline="")))[1:]:
        if len(record) < 2:
            continue
        try:
            cell = ast.literal_eval(record[1])
        except (ValueError, SyntaxError):
            continue
        if not isinstance(cell, dict):
            continue
        rows.append(
            {
                "ipc": str(cell.get("IPC Section", "")),
                "bns": str(cell.get("BNS Section", "")),
                "ipc_text": _body(str(cell.get("IPC Descriptions", "")), str(cell.get("IPC Heading", "")), _IPC_TITLE),
                "bns_text": _body(str(cell.get("BNS description", "")), str(cell.get("BNS Heading", "")), _BNS_TITLE),
            }
        )
    return rows


def _read_new_in_bns(path: Path) -> list[dict[str, Any]]:
    """BNS sections the authors label `new_in_bns` (`phase2_cleaned/bns_sections.jsonl`), as rows with no IPC section."""
    rows = []
    for line in _read_text(path).splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("relationship_type") == "new_in_bns" and rec.get("section_number"):
                rows.append({"ipc": "", "bns": str(rec["section_number"])})
    return rows


def _read_rows(verify_dir: str) -> list[dict[str, Any]]:
    """Rows of the real IPC2BNS-Verify files when `concordance_v1.csv` is found, else of every CSV, JSON and JSONL file under verify_dir."""
    root = Path(verify_dir)
    real = sorted(root.rglob(VERIFY_CSV))
    if real:
        rows = _read_verify_csv(real[0])
        for new_path in sorted(root.rglob("bns_sections.jsonl")):
            rows.extend(_read_new_in_bns(new_path))
        return rows
    rows = []
    for path in sorted(root.rglob("*")):
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


def _text_of(texts: dict[str, str], code: str, section: str) -> str:
    """Section text from a statutes mapping: the exact reference, else the section without its clause ('BNS 318(4)' -> 'BNS 318')."""
    ref = make_ref(code, section)
    return texts.get(ref) or texts.get(ref.split("(")[0], "")


def load_ipc_bns_edges(
    verify_dir: str, texts: dict[str, str] | None = None, untyped: set[str] | None = None
) -> list[ConcordanceEdge]:
    """Parse IPC2BNS-Verify files into typed IPC<->BNS edges (see the module docstring for the expected format).

    Args:
        verify_dir: directory holding the downloaded CSV/JSON/JSONL files
        texts: section text by reference ('IPC 420'), used when the Verify rows carry none
        untyped: when given, receives the references for which no text was found anywhere

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
            pairs.extend(("", b, "", _pick(row, "bns_text") or _text_of(texts, "BNS", b)) for b in bnss)
        elif bnss:
            pairs.extend(
                (
                    i,
                    b,
                    _pick(row, "ipc_text") or _text_of(texts, "IPC", i),
                    _pick(row, "bns_text") or _text_of(texts, "BNS", b),
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
        if untyped is not None:
            untyped.update(r for r, t in ((make_ref("IPC", i) if i else "", it), (new_ref, bt)) if r and not t)
        if not i and any(by_bns[b]):
            continue  # labelled new, but another row maps an IPC section onto it: the mapping wins
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
    """Section text by reference from a statute file: a JSON list or JSON lines of {code, section, text} rows, or the statutes SQLite.

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
        raw = _read_text(path)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:  # JSON lines (the `statutes.jsonl` of the Open India Law ingest)
            data = [json.loads(line) for line in raw.splitlines() if line.strip()]
        data = [data] if isinstance(data, dict) else data  # a one-line JSONL file parses as a single object
        rows = [(r["code"], r["section"], r.get("text", "")) for r in data]
    return {make_ref(c, sec): t or "" for c, sec, t in rows}


def build_ipc_bns_edges(verify_dir: str, statutes_path: str, out_path: str, strict: bool = True) -> int:
    """Write typed edges as JSON lines (the input `concordance_edges.jsonl` of `ConcordanceStore.build`).

    When the Verify files carry no section text, the texts come from the statutes file so the edge type and diff can
    still be computed. A section named in the Verify files but absent from the statutes file cannot be typed and is
    never guessed.

    Args:
        verify_dir: see behaviour
        statutes_path: JSON list, JSON lines or SQLite statute table, or '' to skip
        out_path: JSONL file to write
        strict: raise on a section without any text (default); when False such edges are dropped and logged, so a few sections
            whose text is empty in the source (IPC 13, omitted before the repeal) do not block the build

    Returns:
        Edge count.

    Raises:
        ValueError: when `strict` and a section in the Verify files is missing from the statutes file.
    """
    texts: dict[str, str] = {}
    if statutes_path and Path(statutes_path).is_file():
        texts = read_statute_texts(statutes_path)
    untyped: set[str] = set()
    edges = load_ipc_bns_edges(verify_dir, texts, untyped)
    if texts:
        missing = sorted(untyped)
        if missing and strict:
            raise ValueError(f"sections not in the statutes file, cannot type their edges: {', '.join(missing)}")
        if missing:
            log.warning("dropping edges that cannot be typed (no text anywhere): %s", ", ".join(missing))
            edges = [e for e in edges if e.old_ref not in missing and e.new_ref not in missing]
    return write_edges_jsonl(edges, out_path)
