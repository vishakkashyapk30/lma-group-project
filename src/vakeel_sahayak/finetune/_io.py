"""Small JSON-lines helpers shared by the fine-tuning steps (pair rows: {"doc_id", "facts", "dossier"})."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


def read_rows(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield the JSON objects of a JSONL file; a missing file gives nothing, blank lines are skipped, a torn last line is ignored."""
    p = Path(path)
    if not p.is_file():
        return
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # a session killed mid-write leaves a partial last line
            if isinstance(obj, dict):
                yield obj


def write_rows(path: str | Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write rows as UTF-8 JSONL (parent folders created); returns the number written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n
