"""caselaw.citations store: who cites whom with treatment and court level (100-300K edges). Index: graph + authority score. (plan §5.1)"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from vakeel_sahayak.pipelines.citation_graph.authority import configured_weights
from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph
from vakeel_sahayak.schemas.enums import Shelf, StoreName
from vakeel_sahayak.schemas.store_rows import CitationEdge
from vakeel_sahayak.stores.base import SharedStore
from vakeel_sahayak.stores.paths import MEMORY, resolve_shared_path
from vakeel_sahayak.tools.types import GoodLawResult

_GRAPH_CACHE: dict[tuple[str, float, int], CitationGraph] = {}


class CitationStore(SharedStore):
    """caselaw.citations store: who cites whom with treatment and court level (100-300K edges). Index: graph + authority score."""

    name = StoreName.CASELAW_CITATIONS
    shelf = Shelf.CASELAW
    index_kind = "graph + authority score"

    def __init__(self) -> None:
        """Create an unopened store."""
        self._graph: CitationGraph | None = None
        self.built = False

    def open(self, path: str | None = None) -> None:
        """Open the store: load the SQLite graph at `path` (default from configs/stores.yaml) into memory; an absent file gives an empty graph.

        Args:
            path: file, folder written by `build`, or ':memory:'
        """
        target = resolve_shared_path(self.name, path)
        self.built = target != MEMORY and Path(target).is_file()
        if self.built:
            stat = Path(target).stat()
            key = (str(Path(target).resolve()), stat.st_mtime, stat.st_size)
            if key not in _GRAPH_CACHE:  # tools reopen the store per call; load a given file once per process
                conn = sqlite3.connect(target)
                try:
                    _GRAPH_CACHE.clear()
                    _GRAPH_CACHE[key] = CitationGraph.from_connection(conn)
                finally:
                    conn.close()
            self._graph = _GRAPH_CACHE[key]
        else:
            self._graph = CitationGraph()

    def close(self) -> None:
        """Close."""
        self._graph = None

    def count(self) -> int:
        """Row count.

        Returns:
            Count (edges).
        """
        return self._need().n_edges

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build from interim data.

        Args:
            source_dir: folder holding `orders.jsonl` (see `pipelines/store_builders/corpus.py`)
            out_dir: folder that receives the SQLite file named in configs/stores.yaml
        """
        from vakeel_sahayak.pipelines.store_builders.build_citations import build_citations

        build_citations(source_dir, out_dir)

    def _need(self) -> CitationGraph:
        """The loaded graph (raises if the store was never opened)."""
        if self._graph is None:
            raise RuntimeError("caselaw.citations is not open")
        return self._graph

    def known(self, doc_id: str) -> bool:
        """True when the judgment is a node of the graph."""
        return doc_id in self._need().nodes

    def cited_by(self, doc_id: str) -> list[CitationEdge]:
        """Incoming edges.

        Args:
            doc_id: see behaviour

        Returns:
            Edges.
        """
        return self._need().cited_by(doc_id)

    def cites(self, doc_id: str) -> list[CitationEdge]:
        """Outgoing edges.

        Args:
            doc_id: see behaviour

        Returns:
            Edges.
        """
        return self._need().cites(doc_id)

    def authority_score(self, doc_id: str, as_of: str | None = None) -> float:
        """Authority score: court level, bench size, citations, recency.

        Args:
            doc_id: see behaviour
            as_of: count only citations from judgments up to this ISO date (leakage-safe ranking); default all

        Returns:
            Score in [0, 1].
        """
        return self._need().authority(doc_id, as_of, configured_weights())

    def good_law(self, doc_id: str, as_of: str | None = None) -> GoodLawResult:
        """Overruled by later SC or larger bench?

        Args:
            doc_id: see behaviour
            as_of: see behaviour

        Returns:
            GoodLawResult.
        """
        return self._need().good_law(doc_id, as_of)

    def sc_root(self, doc_id: str) -> str | None:
        """Follow the graph from an HC paragraph to the SC judgment it relies on.

        Args:
            doc_id: see behaviour

        Returns:
            SC doc id.
        """
        return self._need().sc_root(doc_id)

    def sc_root_of_cites(self, cites: list[str]) -> str | None:
        """SC root for a High Court paragraph, from the doc ids in its `cites` metadata."""
        return self._need().sc_root_of_cites(cites)
