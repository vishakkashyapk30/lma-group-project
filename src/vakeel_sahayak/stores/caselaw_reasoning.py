"""caselaw.reasoning store: reasoning paragraphs of HC bail orders and SC bail judgments (100-300K paragraphs). Index: hybrid BM25 + BGE-M3, metadata pre-filter. (plan §5.1)"""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import Factor, OrderPart, Shelf, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.stores.leakage_guard import apply_before_filter
from vakeel_sahayak.stores.paragraph_store import ParagraphStore

AUTHORITY_RANK_WEIGHT = 0.15  # TODO: tune on dev; share of the ranking taken from the authority score (plan §5.3)


class ReasoningStore(ParagraphStore):
    """caselaw.reasoning store: reasoning paragraphs of HC bail orders and SC bail judgments (100-300K paragraphs). Index: hybrid BM25 + BGE-M3, metadata pre-filter."""

    name = StoreName.CASELAW_REASONING
    shelf = Shelf.CASELAW
    index_kind = "hybrid BM25 + BGE-M3, metadata pre-filter"
    parts = (OrderPart.REASONING,)
    _weight_of_prior = AUTHORITY_RANK_WEIGHT

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build from interim data.

        Args:
            source_dir: see behaviour
            out_dir: see behaviour
        """
        from vakeel_sahayak.pipelines.store_builders.build_reasoning import build_reasoning

        build_reasoning(source_dir, out_dir)

    def search(
        self,
        query: str,
        factor: Factor | None = None,
        section_family: list[str] | None = None,
        before: str | None = None,
        outcome: str | None = None,
        court: str | None = None,
        part: OrderPart = OrderPart.REASONING,
        k: int = 10,
    ) -> list[ParagraphRecord]:
        """Hybrid search with metadata pre-filter.

        Args:
            query: free text
            factor: only paragraphs tagged with this factor
            section_family: only paragraphs whose section family contains one of these references
            before: ISO date of the case's order; mandatory (leakage rule, plan §2)
            outcome: e.g. 'granted', 'rejected'
            court: court name (case-insensitive)
            part: authorities are cited from reasoning only; another part returns an empty list
            k: number of paragraphs

        Returns:
            Paragraphs, best first.

        Raises:
            LeakageError: when `before` is missing.
            ValueError: for a malformed date or section reference.
        """
        if OrderPart(part) != OrderPart.REASONING:  # the store holds no other part, so asking for one finds nothing
            apply_before_filter({}, before or "")
            return []
        return self._search(query, factor, section_family, before or "", outcome, court, OrderPart.REASONING, k)

    def search_scored(
        self,
        query: str,
        factor: Factor | None = None,
        section_family: list[str] | None = None,
        before: str | None = None,
        outcome: str | None = None,
        court: str | None = None,
        k: int = 10,
    ) -> list[tuple[ParagraphRecord, float]]:
        """`search` (reasoning part) returning each paragraph with its final hybrid score in [0, 1], best first (S4 score-skew signal).

        Raises:
            LeakageError: when `before` is missing.
            ValueError: for a malformed date or section reference.
        """
        return self._search_scored(query, factor, section_family, before or "", outcome, court, OrderPart.REASONING, k)

    def search_docs(self, query: str, doc_ids: list[str], before: str | None = None, k: int = 200) -> list[tuple[ParagraphRecord, float]]:
        """Rank the reasoning paragraphs of the given judgments against the query (S5 graph expansion; no factor or section filter).

        Args:
            query: free text
            doc_ids: judgments whose paragraphs are ranked
            before: ISO date of the case's order; mandatory (leakage rule, plan §2)
            k: paragraphs to return

        Returns:
            (paragraph, hybrid score in [0, 1]) pairs, best first.

        Raises:
            LeakageError: when `before` is missing.
        """
        return self._search_docs(query, list(doc_ids), before or "", OrderPart.REASONING, k)

    def get_paragraph(self, doc_id: str, para: int) -> ParagraphRecord:
        """Fetch by id.

        Args:
            doc_id: see behaviour
            para: see behaviour

        Returns:
            ParagraphRecord.

        Raises:
            LookupError: if the paragraph is not in the store, or is not a reasoning paragraph.
        """
        record = self._fetch(doc_id, para)
        if record.part != OrderPart.REASONING:
            raise LookupError(f"paragraph {para} of {doc_id} is not a reasoning paragraph")
        return record
