"""case.docs store: client documents in structure-aware chunks with page and box (hundreds of chunks). Index: hybrid. (plan §5.1)

Private to the laptop: the file lives under data/cases/<case_id>/ and is never copied to Ada (plan §16).
"""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import DocumentType, Shelf, StoreName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.store_rows import CaseChunk
from vakeel_sahayak.stores.base import CaseStore
from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow
from vakeel_sahayak.stores.paths import resolve_case_path


class CaseDocsStore(CaseStore):
    """case.docs store: client documents in structure-aware chunks with page and box (hundreds of chunks). Index: hybrid."""

    name = StoreName.CASE_DOCS
    shelf = Shelf.CASE
    index_kind = "hybrid"

    def __init__(self) -> None:
        """Create an unbound, unopened store."""
        self._case_id: str | None = None
        self._index: HybridIndex | None = None

    def open(self, path: str | None = None) -> None:
        """Open the store (creating it if new): `docs.sqlite` of the bound case, or `path`.

        Args:
            path: file, folder, or ':memory:'; default data/cases/<case_id>/docs.sqlite
        """
        if not self._case_id:
            raise ValueError("bind_case(case_id) before open()")
        self._index = HybridIndex(resolve_case_path(self.name, self._case_id, path))

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

    def bind_case(self, case_id: str) -> None:
        """Select the case.

        Args:
            case_id: letters, digits, '-' and '_' (it becomes a folder name)

        Raises:
            ValueError: for an invalid case id.
        """
        self._case_id = check_case_id(case_id)

    def _need(self) -> HybridIndex:
        """The open index (raises if the store was never opened)."""
        if self._index is None:
            raise RuntimeError("case.docs is not open")
        return self._index

    def add_chunks(self, chunks: list[CaseChunk]) -> None:
        """Insert chunks (names already pseudonymised).

        Args:
            chunks: chunks with page and box; a chunk id that is already stored is skipped
        """
        index = self._need()
        rows = [
            IndexRow(
                key=c.chunk_id,
                text=f"{c.text}\n{c.text_en}" if c.text_en else c.text,
                payload=c.model_dump(mode="json"),
                doc_type=c.doc_type.value,
                facets={"doc_type": [c.doc_type.value]},
            )
            for c in chunks
            if index.get(c.chunk_id) is None
        ]
        index.add(rows)

    def search(self, query: str, doc_types: list[DocumentType] | None = None, k: int = 5) -> list[CaseChunk]:
        """Hybrid search.

        Args:
            query: free text
            doc_types: only chunks of these document types
            k: number of chunks

        Returns:
            Chunks, best first, with page and box.
        """
        facets = {"doc_type": [DocumentType(t).value for t in doc_types]} if doc_types else {}
        hits = self._need().search(query, facets=facets, k=k)
        return [CaseChunk.model_validate(h.payload) for h in hits]

    def facts_text(self, max_chars: int = 12_000) -> str:
        """Pseudonymised source text for the product's local facts-text switches.

        The case shelf is local-only and Munshi files pseudonymised chunks into it.
        Chunks are ordered deterministically by document, page and chunk id; a
        bounded result prevents a large bundle from becoming an unbounded prompt.
        This method never searches a shared store or calls a model.
        """
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        chunks = [CaseChunk.model_validate(row) for row in self._need().payloads()]
        chunks.sort(key=lambda c: (c.doc_id, c.page, c.chunk_id))
        parts: list[str] = []
        used = 0
        for chunk in chunks:
            text = chunk.text.strip()
            if not text or text in parts:
                continue
            room = max_chars - used
            if room <= 0:
                break
            piece = text[:room].strip()
            if piece:
                parts.append(piece)
                used += len(piece) + 1
        return "\n".join(parts)
