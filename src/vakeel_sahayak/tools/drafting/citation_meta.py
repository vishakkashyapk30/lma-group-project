"""Corpus metadata for rendering citations (plan §8.1: citation text is rendered from corpus metadata; the model writes only IDs).

Where the metadata comes from, in order (each source only fills what the earlier ones lack):

1. the corpus metadata file: `VS_CORPUS_METADATA`, else `<interim_dir>/metadata.jsonl`, else `<interim_dir>/orders.jsonl`
   (the store builders' input; see `pipelines/store_builders/corpus.py`): title / case name, neutral citation and other
   citations, court, date;
2. the citation graph (`caselaw.citations` nodes): court, date;
3. the cited paragraph in `caselaw.reasoning`: court, date.

A doc id that none of them knows is unknown: the caller must fail, never invent a name.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[tuple[str, float, int], dict[str, dict[str, Any]]] = {}
_TITLE = ("title", "case_name", "case_title")
_COURT = ("court", "court_name")
_DATE = ("date", "decision_date", "judgment_date")


@dataclass(frozen=True)
class DocMeta:
    """What the corpus says about one judgment."""

    doc_id: str
    title: str | None = None
    citation: str | None = None  # the judgment's own reported or neutral citation
    court: str | None = None
    date: str | None = None  # ISO


def _first(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    low = {str(k).lower(): v for k, v in raw.items()}
    for k in keys:
        if low.get(k) not in (None, ""):
            return low[k]
    return None


def metadata_paths() -> list[Path]:
    """Candidate metadata files, most specific first."""
    out: list[Path] = []
    if os.environ.get("VS_CORPUS_METADATA"):
        out.append(Path(os.environ["VS_CORPUS_METADATA"]))
    from vakeel_sahayak.config import load_config

    interim = Path(load_config().paths.interim_dir)
    out += [interim / "metadata.jsonl", interim / "orders.jsonl"]
    return out


def _load(path: Path) -> dict[str, dict[str, Any]]:
    """doc_id -> compact metadata for one JSONL file (streamed; cached by path, mtime and size)."""
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime, stat.st_size)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    from vakeel_sahayak.pipelines.text_utils import normalise_date

    index: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if not isinstance(raw, dict):
                continue
            doc_id = _first(raw, ("doc_id", "id", "case_id"))
            if doc_id is None:
                continue
            cites = _first(raw, ("citations",))
            neutral = _first(raw, ("neutral_citation",))
            first_cite = neutral or (cites[0] if isinstance(cites, list) and cites else cites if isinstance(cites, str) else None)
            index[str(doc_id)] = {
                "title": _first(raw, _TITLE),
                "citation": str(first_cite).split(" : ")[0].strip() if first_cite else None,
                "court": _first(raw, _COURT),
                "date": normalise_date(_first(raw, _DATE)),
            }
    with _LOCK:
        _CACHE.clear()  # keep one generation per process
        _CACHE[key] = index
    return index


def lookup(doc_id: str, para: int | None = None) -> DocMeta | None:
    """Metadata of a judgment from the corpus, the citation graph and the reasoning store; None when nobody knows it.

    Args:
        doc_id: the judgment's id
        para: a paragraph number (its row in caselaw.reasoning supplies court and date when the files lack them)

    Returns:
        DocMeta, or None for an unknown doc id.
    """
    found: dict[str, Any] = {}
    known = False
    for path in metadata_paths():
        if path.is_file():
            rec = _load(path).get(doc_id)
            if rec is not None:
                known = True
                found.update({k: v for k, v in rec.items() if v and not found.get(k)})
                break
    if not found.get("court") or not found.get("date") or not known:
        node = _graph_node(doc_id)
        if node is not None:
            known = True
            for key in ("court", "date"):
                if not found.get(key) and node.get(key):
                    found[key] = node[key]
    if para is not None and (not found.get("court") or not found.get("date") or not known):
        row = _paragraph(doc_id, para)
        if row is not None:
            known = True
            found["court"] = found.get("court") or row.court
            found["date"] = found.get("date") or row.date
    if not known:
        return None
    return DocMeta(doc_id=doc_id, title=found.get("title"), citation=found.get("citation"), court=found.get("court"), date=found.get("date"))


def _graph_node(doc_id: str) -> dict[str, Any] | None:
    """Court and date of a node of the citation graph (None when the graph does not hold the judgment)."""
    from vakeel_sahayak.schemas.enums import StoreName
    from vakeel_sahayak.stores.registry import open_store

    try:
        store = open_store(StoreName.CASELAW_CITATIONS)
    except Exception:  # noqa: BLE001 - an unavailable graph simply knows nothing
        return None
    try:
        if not store.known(doc_id):
            return None
        graph = getattr(store, "_graph", None)
        node = graph.nodes.get(doc_id) if graph is not None else None
        court = getattr(node, "court", None)
        return {"court": court if court and court != "unknown" else None, "date": getattr(node, "date", None)}
    finally:
        store.close()


def _paragraph(doc_id: str, para: int):  # noqa: ANN202
    """The reasoning paragraph, or None."""
    from vakeel_sahayak.tools.base import ToolError
    from vakeel_sahayak.tools.caselaw.reasoning import get_paragraph

    row = get_paragraph(doc_id, para)
    return None if isinstance(row, ToolError) else row


def clear_cache() -> None:
    """Forget the loaded metadata files (tests)."""
    with _LOCK:
        _CACHE.clear()
