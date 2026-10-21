"""Shared implementation of the hybrid paragraph stores: caselaw.reasoning, advocacy.arguments, advocacy.objections (plan §5.1, §5.2).

One row per paragraph (`ParagraphRecord`), indexed by BM25 and dense vectors (`HybridIndex`), with metadata pre-filters
on court, outcome, part, factor and section family, and the leakage guard on every query.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.concordance.refs import make_ref, split_ref
from vakeel_sahayak.schemas.enums import Factor, OrderPart
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.stores.base import SharedStore
from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow
from vakeel_sahayak.stores.leakage_guard import apply_before_filter, assert_all_before
from vakeel_sahayak.stores.paths import MEMORY, resolve_shared_path


def paragraph_key(doc_id: str, para: int) -> str:
    """Unique key of a paragraph row: 'DLHC-2022-1187#14'."""
    return f"{doc_id}#{para}"


def paragraph_index_rows(records: list[ParagraphRecord]) -> list[IndexRow]:
    """Index rows for the chunks of an order. Chunks sharing (doc_id, para), the pieces of one long paragraph, get
    keys 'DLHC-2022-1187#14', 'DLHC-2022-1187#14.2', ...; `get_paragraph(doc_id, para)` returns the first."""
    seen: dict[str, int] = {}
    rows = []
    for rec in records:
        base = paragraph_key(rec.doc_id, rec.para)
        seen[base] = seen.get(base, 0) + 1
        rows.append(paragraph_index_row(rec, base if seen[base] == 1 else f"{base}.{seen[base]}"))
    return rows


def paragraph_index_row(rec: ParagraphRecord, key: str | None = None) -> IndexRow:
    """The index row of a paragraph: text for BM25 and vectors, metadata for filters, the full record as payload."""
    return IndexRow(
        key=key or paragraph_key(rec.doc_id, rec.para),
        text=rec.text,
        payload=rec.model_dump(mode="json"),
        date=rec.date,
        court=rec.court,
        outcome=rec.outcome,
        part=rec.part.value,
        authority=rec.authority,
        facets={"family": list(rec.section_family), "factor": [f.value for f in rec.factors]},
    )


def normalise_family(section_family: list[str] | None) -> list[str]:
    """Canonical references for a section-family filter ('ipc 420' -> 'IPC 420').

    Raises:
        ValueError: when an entry is not a full statute reference.
    """
    return [make_ref(*split_ref(ref)) for ref in (section_family or [])]


class ParagraphStore(SharedStore):
    """Base of the hybrid paragraph stores. Subclasses set `name`, `shelf`, `index_kind`, `parts` and `_weight_of_prior`."""

    parts: tuple[OrderPart, ...] = (OrderPart.REASONING,)
    _weight_of_prior: float = 0.0

    def __init__(self) -> None:
        """Create an unopened store."""
        self._index: HybridIndex | None = None
        self.path: str | None = None
        self.built = False

    def open(self, path: str | None = None) -> None:
        """Open the store: the SQLite file at `path` (default from configs/stores.yaml), or an empty in-memory index if absent.

        Args:
            path: file, folder written by `build`, or ':memory:'
        """
        target = resolve_shared_path(self.name, path)
        self.built = target != MEMORY and Path(target).is_file()
        self.path = target
        self._index = HybridIndex(target if self.built else None)

    def close(self) -> None:
        """Close."""
        if self._index:
            self._index.close()
            self._index = None

    def count(self) -> int:
        """Row count.

        Returns:
            Count.
        """
        return self._need_index().count()

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build from interim data (see the builder of the store for the input format).

        Args:
            source_dir: folder holding `orders.jsonl` (see `pipelines/store_builders/corpus.py`)
            out_dir: folder that receives the SQLite file named in configs/stores.yaml
        """
        raise NotImplementedError  # each concrete store forwards to its builder

    def _need_index(self) -> HybridIndex:
        """The open index (raises if the store was never opened)."""
        if self._index is None:
            raise RuntimeError(f"{self.name.value} is not open")
        return self._index

    def _search(
        self,
        query: str,
        factor: Factor | str | None,
        section_family: list[str] | None,
        before: str,
        outcome: str | None,
        court: str | None,
        part: OrderPart | None,
        k: int,
    ) -> list[ParagraphRecord]:
        """Filtered hybrid search with the leakage guard (before is mandatory)."""
        return [r for r, _ in self._search_scored(query, factor, section_family, before, outcome, court, part, k)]

    def _search_scored(
        self,
        query: str,
        factor: Factor | str | None,
        section_family: list[str] | None,
        before: str,
        outcome: str | None,
        court: str | None,
        part: OrderPart | None,
        k: int,
    ) -> list[tuple[ParagraphRecord, float]]:
        """`_search` with each paragraph's final hybrid score in [0, 1] (S4 reads the shape of these scores)."""
        guard = apply_before_filter({}, before)
        facets: dict[str, list[str]] = {}
        if factor:
            facets["factor"] = [Factor(factor).value]
        if section_family:
            facets["family"] = normalise_family(section_family)
        hits = self._need_index().search(
            query,
            filters={"court": court, "outcome": outcome, "part": part.value if part else None},
            facets=facets,
            before=guard["before"],
            k=k,
            authority_weight=self._weight_of_prior,
        )
        records = [(ParagraphRecord.model_validate(h.payload), h.score) for h in hits]
        assert_all_before([r.date for r, _ in records], guard["before"])
        return records

    def _search_docs(self, query: str, doc_ids: list[str], before: str, part: OrderPart | None, k: int) -> list[tuple[ParagraphRecord, float]]:
        """Hybrid text search restricted to the paragraphs of the given judgments (no factor or section filter), with the leakage guard.

        Used by the S5 graph expansion to rank the paragraphs of judgments the citation graph reached. Returns (record, score in [0, 1]).
        """
        guard = apply_before_filter({}, before)
        if not doc_ids:
            return []
        hits = self._need_index().search(
            query, filters={"part": part.value if part else None}, before=guard["before"], k=k,
            authority_weight=self._weight_of_prior, key_prefixes=[f"{d}#" for d in dict.fromkeys(doc_ids)], candidates=max(100, k),
        )  # fmt: skip
        records = [(ParagraphRecord.model_validate(h.payload), h.score) for h in hits]
        assert_all_before([r.date for r, _ in records], guard["before"])
        return records

    def _fetch(self, doc_id: str, para: int) -> ParagraphRecord:
        """One paragraph by id; LookupError if absent."""
        payload: dict[str, Any] | None = self._need_index().get(paragraph_key(doc_id, para))
        if payload is None:
            raise LookupError(f"paragraph {para} of {doc_id} not found in {self.name.value}")
        return ParagraphRecord.model_validate(payload)
