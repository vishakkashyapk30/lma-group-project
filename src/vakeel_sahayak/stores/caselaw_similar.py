"""caselaw.similar store: one vector per order's facts section plus a fact signature (50-100K orders). Index: whole-order vectors + structured match. (plan §5.1)"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.schemas.enums import Shelf, StoreName
from vakeel_sahayak.schemas.store_rows import FactSignature, SimilarOrderRow
from vakeel_sahayak.stores.base import SharedStore
from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow, store_vectors_mode
from vakeel_sahayak.stores.leakage_guard import apply_before_filter, assert_all_before
from vakeel_sahayak.stores.paragraph_store import normalise_family
from vakeel_sahayak.stores.paths import MEMORY, resolve_shared_path

TEXT_WEIGHT = 0.7  # share of the score from the facts text; the rest from the signature match
_OVERFETCH = 5


def similar_index_row(row: SimilarOrderRow, facts_text: str, family: list[str]) -> IndexRow:
    """The index row of an order: its facts text (vector and BM25), its metadata row, and its section family for matching."""
    return IndexRow(
        key=row.doc_id,
        text=facts_text,
        payload={**row.model_dump(mode="json"), "section_family": family},
        date=row.date,
        court=row.court,
        facets={"family": family},
    )


def signature_match(want: FactSignature, row_signature: FactSignature, row_family: list[str], want_family: list[str]) -> float | None:
    """Share of the wanted signature fields the order matches (sections by family overlap); None when nothing was asked."""
    checks: list[bool] = []
    if want.sections:
        checks.append(bool(set(want_family) & set(row_family)))
    for name in ("custody_band", "charge_sheet_status", "co_accused_outcome"):
        asked = getattr(want, name)
        if asked:
            checks.append(asked == getattr(row_signature, name))
    return sum(checks) / len(checks) if checks else None


class SimilarStore(SharedStore):
    """caselaw.similar store: one vector per order's facts section plus a fact signature (50-100K orders). Index: whole-order vectors + structured match."""

    name = StoreName.CASELAW_SIMILAR
    shelf = Shelf.CASELAW
    index_kind = "whole-order vectors + structured match"

    def __init__(self) -> None:
        """Create an unopened store."""
        self._index: HybridIndex | None = None
        self.built = False

    def open(self, path: str | None = None) -> None:
        """Open the store: the SQLite file at `path` (default from configs/stores.yaml), or an empty in-memory index if absent.

        Args:
            path: file, folder written by `build`, or ':memory:'
        """
        target = resolve_shared_path(self.name, path)
        self.built = target != MEMORY and Path(target).is_file()
        # VS_STORES=bge (opt-in) searches the BGE-M3 side vectors of the built file; unset keeps the vectors inside it
        self._index = HybridIndex(target, side_vectors=store_vectors_mode()) if self.built else HybridIndex(None)

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
        return self._need().count()

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build from interim data.

        Args:
            source_dir: folder holding `orders.jsonl` (see `pipelines/store_builders/corpus.py`)
            out_dir: folder that receives the SQLite file named in configs/stores.yaml
        """
        from vakeel_sahayak.pipelines.store_builders.build_similar import build_similar

        build_similar(source_dir, out_dir)

    def _need(self) -> HybridIndex:
        """The open index (raises if the store was never opened)."""
        if self._index is None:
            raise RuntimeError("caselaw.similar is not open")
        return self._index

    def similar(
        self, facts_text: str, signature: FactSignature | None = None, before: str | None = None, k: int = 10
    ) -> list[SimilarOrderRow]:
        """Vector search then structured signature match. Never returns grant rates.

        The facts text is searched (BM25 + vectors, dated before `before`); the best candidates are re-ranked by how many
        of the wanted signature fields they match (`TEXT_WEIGHT` text, the rest signature). Rows carry no outcome.

        Args:
            facts_text: facts of the case at hand
            signature: wanted structured signature (sections, custody band, charge-sheet status, co-accused outcome)
            before: ISO date of the case's order; mandatory (leakage rule, plan §2)
            k: number of orders

        Returns:
            Orders, best first.

        Raises:
            LeakageError: when `before` is missing.
            ValueError: for a malformed date or section reference.
        """
        guard = apply_before_filter({}, before or "")
        want = signature or FactSignature()
        want_family = normalise_family(want.sections) if want.sections else []
        hits = self._need().search(facts_text, before=guard["before"], k=max(k * _OVERFETCH, 50))
        ranked: list[tuple[float, str, SimilarOrderRow]] = []
        for hit in hits:
            row = SimilarOrderRow.model_validate(hit.payload)
            match = signature_match(want, row.signature, list(hit.payload.get("section_family", [])), want_family)
            score = hit.score if match is None else TEXT_WEIGHT * hit.score + (1 - TEXT_WEIGHT) * match
            ranked.append((score, row.doc_id, row))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        rows = [r for _, _, r in ranked[:k]]
        assert_all_before([r.date for r in rows], guard["before"])
        return rows
