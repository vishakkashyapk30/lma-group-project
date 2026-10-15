"""The case's page index: every page Munshi has seen, pseudonymised, for `search_pages` and gap checks (plan §4.3 step 4).

Stored next to the case's other files (`<cases_dir>/<case_id>/page_index.json`, laptop only). It holds pseudonymised text
only. A page the routes could not read is listed with an empty text and status UNREADABLE.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

_WORD = re.compile(r"[A-Za-z0-9ऀ-ॿ]+")
_STOP = frozenset("the of and to in is was on for that this with by as at an be are from it or a".split())


class IndexedPage(BaseModel):
    """One page in the index."""

    file: str
    page: int
    doc_id: str | None = None
    doc_type: str | None = None
    status: str = "OK"
    route: str | None = None
    ocr_conf: float | None = None
    text: str = ""


def _terms(text: str) -> list[str]:
    return [w for w in (m.group(0).lower() for m in _WORD.finditer(text)) if w not in _STOP and len(w) > 1]


class PageIndex:
    """Pages of a case, searchable by a small TF-IDF score (no model needed)."""

    def __init__(self, pages: list[IndexedPage] | None = None) -> None:
        """Start empty or from existing pages."""
        self.pages: list[IndexedPage] = list(pages or [])

    def add(self, page: IndexedPage) -> None:
        """Add a page, replacing an earlier entry for the same file and page number."""
        self.pages = [p for p in self.pages if (p.file, p.page) != (page.file, page.page)]
        self.pages.append(page)

    def get(self, file: str, page: int) -> IndexedPage | None:
        """The entry for a page."""
        return next((p for p in self.pages if (p.file, p.page) == (file, page)), None)

    def search(self, query: str, k: int = 5, exclude_types: set[str] | None = None) -> list[tuple[IndexedPage, float]]:
        """Pages ranked by TF-IDF overlap with the query (best first, zero-score pages left out)."""
        q = _terms(query)
        pool = [p for p in self.pages if p.text and (p.doc_type not in (exclude_types or set()))]
        if not q or not pool:
            return []
        docs = [Counter(_terms(p.text)) for p in pool]
        n = len(pool)
        scored = []
        for page, tf in zip(pool, docs, strict=True):
            score = sum((1 + math.log(tf[t])) * math.log(1 + n / (1 + sum(1 for d in docs if t in d))) for t in set(q) if tf[t])
            if score > 0:
                scored.append((page, round(score, 4)))
        return sorted(scored, key=lambda ps: (-ps[1], ps[0].file, ps[0].page))[:k]

    def save(self, path: str | Path) -> None:
        """Write the index as JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([pg.model_dump() for pg in self.pages], ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> PageIndex:
        """Read an index (empty when the file does not exist)."""
        p = Path(path)
        if not p.is_file():
            return cls()
        return cls([IndexedPage.model_validate(d) for d in json.loads(p.read_text(encoding="utf-8"))])


def index_path(case_id: str, cases_dir: str | None = None) -> Path:
    """Where a case's page index lives."""
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.schemas.ids import check_case_id

    return Path(cases_dir or load_config().paths.cases_dir) / check_case_id(case_id) / "page_index.json"
