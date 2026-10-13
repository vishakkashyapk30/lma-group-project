"""advocacy.arguments store: defense-submission paragraphs tagged by factor and outcome (about 100K); never cited as authority. Index: hybrid + filters. (plan §5.1)"""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import Factor, OrderPart, Shelf, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.stores.paragraph_store import ParagraphStore


class ArgumentStore(ParagraphStore):
    """advocacy.arguments store: defense-submission paragraphs tagged by factor and outcome (about 100K); never cited as authority. Index: hybrid + filters."""

    name = StoreName.ADVOCACY_ARGUMENTS
    shelf = Shelf.ADVOCACY
    index_kind = "hybrid + filters"
    parts = (OrderPart.DEFENSE,)

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build from interim data.

        Args:
            source_dir: see behaviour
            out_dir: see behaviour
        """
        from vakeel_sahayak.pipelines.store_builders.build_arguments import build_arguments

        build_arguments(source_dir, out_dir)

    def search(
        self,
        query: str,
        factor: Factor | None = None,
        section_family: list[str] | None = None,
        outcome: str | None = None,
        before: str | None = None,
        k: int = 10,
    ) -> list[ParagraphRecord]:
        """Hybrid search.

        Args:
            query: free text
            factor: only paragraphs tagged with this factor
            section_family: only paragraphs whose section family contains one of these references
            outcome: outcome of the order the paragraph comes from
            before: ISO date of the case's order; mandatory (leakage rule, plan §2)
            k: number of paragraphs

        Returns:
            Paragraphs, best first. These are counsel's submissions: for coverage and phrasing, never cited as authority.

        Raises:
            LeakageError: when `before` is missing.
            ValueError: for a malformed date or section reference.
        """
        return self._search(query, factor, section_family, before or "", outcome, None, OrderPart.DEFENSE, k)
