"""In-memory citation graph with authority score, good-law check and SC root (plan §5.3).

Plain dictionaries and sets (no heavy dependency): a corpus of 100-300K edges fits in memory and every query is a
neighbour lookup. The SQLite file written by `write_sqlite` is what the `caselaw.citations` store reads.

Interpretation of "later SC judgment or larger bench" (plan §5.3): an OVERRULED edge from a citing judgment counts when
the citing judgment is later than the cited one and either (a) it is a Supreme Court judgment whose bench is not
smaller than the cited judgment's bench when both are known, or (b) it is from the same court with a known, larger
bench. Anything else (a smaller bench, an unrelated court, a citing judgment dated no later than the cited one) is ignored.
The date comparison is skipped when either judgment has no date (a judgment outside the corpus, known only from an edge).
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vakeel_sahayak.schemas.enums import GoodLawStatus, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge
from vakeel_sahayak.tools.types import GoodLawResult

DEFAULT_WEIGHTS = {"court_level": 0.35, "bench_size": 0.15, "citations": 0.35, "recency": 0.15}  # TODO: tune on dev
RECENCY_HALF_LIFE_YEARS = 10.0
MAX_BENCH_FOR_SCORE = 5
_ROOT_TREATMENTS = (Treatment.FOLLOWED, Treatment.RELIED_ON)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (doc_id TEXT PRIMARY KEY, court TEXT, court_level TEXT, bench_size INTEGER, date TEXT);
CREATE TABLE IF NOT EXISTS edges (citing TEXT NOT NULL, cited TEXT NOT NULL, treatment TEXT NOT NULL,
    court_level TEXT, sentence TEXT, PRIMARY KEY (citing, cited));
CREATE INDEX IF NOT EXISTS edges_cited ON edges (cited);
"""


def court_level_of(court: str | None) -> str:
    """'SC' for the Supreme Court, 'HC' for a High Court, else 'OTHER'."""
    c = (court or "").lower()
    if "supreme" in c or c.strip() in ("sc", "supreme court of india"):
        return "SC"
    if "high court" in c or c.strip().endswith(" hc") or c.strip() == "hc":
        return "HC"
    return "OTHER"


@dataclass
class NodeMeta:
    """What the graph knows about one judgment."""

    doc_id: str
    court: str | None = None
    court_level: str = "OTHER"
    bench_size: int | None = None
    date: str | None = None  # ISO


def _years_between(earlier: str, later: str) -> float:
    """Elapsed years between two ISO dates (never negative)."""
    return max(0.0, (date.fromisoformat(later) - date.fromisoformat(earlier)).days / 365.25)


class CitationGraph:
    """Nodes, treated citation edges and the scores built on them (plan §5.3)."""

    def __init__(self, nodes: list[NodeMeta] | None = None, edges: list[CitationEdge] | None = None) -> None:
        """Create a graph; edges may mention nodes that were not listed (they get empty metadata)."""
        self.nodes: dict[str, NodeMeta] = {}
        self._out: dict[str, dict[str, CitationEdge]] = defaultdict(dict)
        self._in: dict[str, dict[str, CitationEdge]] = defaultdict(dict)
        self._top_cache: dict[str, int] = {}
        for n in nodes or []:
            self.nodes[n.doc_id] = n
        for e in edges or []:
            self.add_edge(e)

    def add_edge(self, edge: CitationEdge) -> None:
        """Add (or replace) a citing -> cited edge."""
        for doc in (edge.citing_doc_id, edge.cited_doc_id):
            self.nodes.setdefault(doc, NodeMeta(doc_id=doc))
        self._top_cache.clear()
        self._out[edge.citing_doc_id][edge.cited_doc_id] = edge
        self._in[edge.cited_doc_id][edge.citing_doc_id] = edge

    @property
    def n_edges(self) -> int:
        """Number of edges."""
        return sum(len(v) for v in self._out.values())

    def edges(self) -> list[CitationEdge]:
        """All edges, sorted for stable output."""
        return [self._out[c][d] for c in sorted(self._out) for d in sorted(self._out[c])]

    def cites(self, doc_id: str) -> list[CitationEdge]:
        """Outgoing edges of a judgment, sorted by cited id."""
        return [e for _, e in sorted(self._out.get(doc_id, {}).items())]

    def cited_by(self, doc_id: str, as_of: str | None = None) -> list[CitationEdge]:
        """Incoming edges (optionally only from judgments dated on or before `as_of`), sorted by citing id."""
        edges = [e for _, e in sorted(self._in.get(doc_id, {}).items())]
        return [e for e in edges if self._known_by(e.citing_doc_id, as_of)]

    def _known_by(self, doc_id: str, as_of: str | None) -> bool:
        """True when `as_of` is not set, or the judgment is dated on or before it (undated judgments are not)."""
        if not as_of:
            return True
        d = self.nodes.get(doc_id, NodeMeta(doc_id)).date
        return bool(d) and d <= as_of

    # authority score ---------------------------------------------------------------------------------------------

    def authority(
        self, doc_id: str, as_of: str | None = None, weights: dict[str, float] | None = None, own_court: str | None = None
    ) -> float:
        """Authority score in [0, 1]: court level, bench size, citations from other bail cases, recency (plan §5.3).

        With `as_of`, only citations from judgments dated on or before it count and recency is measured from it, so a
        query for a case never benefits from later judgments.

        Args:
            doc_id: judgment
            as_of: ISO date, default the latest date in the graph
            weights: component weights (default `DEFAULT_WEIGHTS`)
            own_court: the case's own High Court; its judgments rank above other High Courts

        Returns:
            Score, 0.0 for an unknown judgment.
        """
        node = self.nodes.get(doc_id)
        if node is None:
            return 0.0
        top = self._top_indegree(as_of)
        return self._score(node, self._indegree(doc_id, as_of), top, as_of or self._latest_date(), weights, own_court)

    def all_authority(self, weights: dict[str, float] | None = None) -> dict[str, float]:
        """Static authority of every judgment (no `as_of`)."""
        top, ref = self._top_indegree(None), self._latest_date()
        return {d: self._score(n, self._indegree(d, None), top, ref, weights, None) for d, n in self.nodes.items()}

    def _score(
        self, node: NodeMeta, indegree: int, top: int, ref: str | None, weights: dict[str, float] | None, own_court: str | None
    ) -> float:
        """Weighted mean of the four components, each in [0, 1]."""
        w = {**DEFAULT_WEIGHTS, **(weights or {})}
        parts = {
            "court_level": self._court_component(node, own_court),
            "bench_size": 0.0 if not node.bench_size else min(node.bench_size, MAX_BENCH_FOR_SCORE) / MAX_BENCH_FOR_SCORE,
            "citations": math.log1p(indegree) / math.log1p(top) if top else 0.0,
            "recency": 0.0 if not (node.date and ref) else 0.5 ** (_years_between(node.date, max(ref, node.date)) / RECENCY_HALF_LIFE_YEARS),
        }
        return round(sum(w[k] * parts[k] for k in parts) / (sum(w.values()) or 1.0), 4)

    @staticmethod
    def _court_component(node: NodeMeta, own_court: str | None) -> float:
        """SC first, then the case's own High Court, then other High Courts."""
        if node.court_level == "SC":
            return 1.0
        if node.court_level == "HC":
            return 0.7 if own_court and node.court and own_court.lower() in node.court.lower() else 0.5
        return 0.25

    def _indegree(self, doc_id: str, as_of: str | None) -> int:
        """Number of citing judgments known by `as_of`."""
        return sum(1 for c in self._in.get(doc_id, {}) if self._known_by(c, as_of))

    def _top_indegree(self, as_of: str | None) -> int:
        """The largest in-degree in the graph at `as_of` (cached)."""
        key = as_of or ""
        if key not in self._top_cache:
            self._top_cache[key] = max((self._indegree(d, as_of) for d in self._in), default=0)
        return self._top_cache[key]

    def _latest_date(self) -> str | None:
        """Latest judgment date in the graph."""
        return max((n.date for n in self.nodes.values() if n.date), default=None)

    # good law ----------------------------------------------------------------------------------------------------

    def _overrules(self, edge: CitationEdge) -> bool:
        """True when this OVERRULED edge is a valid overruling under the module's reading of plan §5.3."""
        if edge.treatment != Treatment.OVERRULED:
            return False
        citing, cited = self.nodes[edge.citing_doc_id], self.nodes[edge.cited_doc_id]
        if citing.date and cited.date and citing.date <= cited.date:  # dates are compared only when both are known
            return False
        if citing.court_level == "SC":
            return not (citing.bench_size and cited.bench_size and citing.bench_size < cited.bench_size)
        same_court = bool(citing.court) and citing.court == cited.court
        return same_court and bool(citing.bench_size and cited.bench_size and citing.bench_size > cited.bench_size)

    def find_overruled(self, as_of: str | None = None) -> dict[str, str]:
        """Precedents treated as overruled by a later SC judgment or larger bench.

        Args:
            as_of: only count overruling judgments dated on or before this ISO date

        Returns:
            Doc id to overruling doc id (the earliest valid overruling judgment).
        """
        out: dict[str, str] = {}
        for cited, incoming in self._in.items():
            valid = [e for e in incoming.values() if self._overrules(e) and self._known_by(e.citing_doc_id, as_of)]
            if valid:
                first = min(valid, key=lambda e: (self.nodes[e.citing_doc_id].date or "", e.citing_doc_id))
                out[cited] = first.citing_doc_id
        return out

    def good_law(self, doc_id: str, as_of: str | None = None) -> GoodLawResult:
        """Good-law check (plan §5.3): OVERRULED blocks, DISTINGUISHED is shown but does not block.

        Args:
            doc_id: precedent
            as_of: only judgments dated on or before this ISO date can overrule or distinguish it

        Returns:
            GoodLawResult with `overruled_by` and `sc_root` where known; UNKNOWN for a judgment not in the graph.
        """
        if doc_id not in self.nodes:
            return GoodLawResult(status=GoodLawStatus.UNKNOWN, note=f"{doc_id} is not in the citation graph")
        root = self.sc_root(doc_id)
        overruling = self.find_overruled(as_of).get(doc_id)
        if overruling:
            return GoodLawResult(
                status=GoodLawStatus.OVERRULED, overruled_by=overruling, sc_root=root,
                note=f"treated as overruled by {overruling}; do not cite without a warning",
            )  # fmt: skip
        distinguishing = [e.citing_doc_id for e in self.cited_by(doc_id, as_of) if e.treatment == Treatment.DISTINGUISHED]
        if distinguishing:
            return GoodLawResult(
                status=GoodLawStatus.DISTINGUISHED, sc_root=root,
                note=f"distinguished in {len(distinguishing)} later judgment(s); shown, not blocking",
            )  # fmt: skip
        return GoodLawResult(status=GoodLawStatus.OK, sc_root=root)

    # SC root -----------------------------------------------------------------------------------------------------

    def sc_root(self, doc_id: str, max_depth: int = 3) -> str | None:
        """Follow the graph from a judgment to the SC judgment it relies on (plan §5.3).

        A Supreme Court judgment is its own root. Otherwise the judgment's FOLLOWED / RELIED_ON edges are followed:
        an SC target is the root (the most cited one if there are several); an HC target is followed in turn, up to
        `max_depth` hops, never revisiting a judgment.

        Args:
            doc_id: judgment (or the doc id behind a High Court paragraph)
            max_depth: hops through intermediate High Court judgments

        Returns:
            SC doc id, or None when no SC judgment is relied on.
        """
        return self.sc_root_of_cites([doc_id], max_depth)

    def sc_root_of_cites(self, cites: list[str], max_depth: int = 3) -> str | None:
        """SC root for a High Court paragraph, from the doc ids in its `cites` (see `sc_root`)."""
        seen: set[str] = set()
        frontier = [c for c in cites if c in self.nodes]
        for _ in range(max_depth + 1):
            sc = [c for c in frontier if self.nodes[c].court_level == "SC"]
            if sc:
                return max(sc, key=lambda c: (len(self._in.get(c, {})), c))
            seen.update(frontier)
            frontier = sorted(
                {
                    e.cited_doc_id
                    for c in frontier
                    for e in self._out.get(c, {}).values()
                    if e.treatment in _ROOT_TREATMENTS and e.cited_doc_id not in seen
                }
            )
            if not frontier:
                return None
        return None

    # persistence -------------------------------------------------------------------------------------------------

    def write_sqlite(self, path: str | Path) -> int:
        """Write nodes and edges to a SQLite file, replacing it; returns the number of edges."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.unlink(missing_ok=True)
        conn = sqlite3.connect(str(p))
        try:
            with conn:
                conn.executescript(_SCHEMA)
                conn.executemany(
                    "INSERT INTO nodes VALUES (?, ?, ?, ?, ?)",
                    [(n.doc_id, n.court, n.court_level, n.bench_size, n.date) for n in self.nodes.values()],
                )
                conn.executemany(
                    "INSERT INTO edges VALUES (?, ?, ?, ?, ?)",
                    [(e.citing_doc_id, e.cited_doc_id, e.treatment.value, e.court_level, e.sentence) for e in self.edges()],
                )
        finally:
            conn.close()
        return self.n_edges

    @classmethod
    def from_connection(cls, conn: sqlite3.Connection) -> CitationGraph:
        """Load a graph from an open connection holding the `nodes` and `edges` tables."""
        nodes = [
            NodeMeta(doc_id=d, court=c, court_level=lvl or court_level_of(c), bench_size=b, date=dt)
            for d, c, lvl, b, dt in conn.execute("SELECT doc_id, court, court_level, bench_size, date FROM nodes")
        ]
        edges = [
            CitationEdge(citing_doc_id=a, cited_doc_id=b, treatment=Treatment(t), court_level=lvl, sentence=s)
            for a, b, t, lvl, s in conn.execute("SELECT citing, cited, treatment, court_level, sentence FROM edges")
        ]
        return cls(nodes, edges)

    @classmethod
    def from_sqlite(cls, path: str | Path) -> CitationGraph:
        """Load a graph from a file written by `write_sqlite`, or from JSON `{"docs": {doc_id: {court_level, date, ...}}, "edges": [...]}`."""
        with Path(path).open("rb") as fh:
            is_sqlite = fh.read(16).startswith(b"SQLite format 3")
        if not is_sqlite:
            return cls.from_json(path)
        conn = sqlite3.connect(str(path))
        try:
            return cls.from_connection(conn)
        finally:
            conn.close()

    @classmethod
    def from_json(cls, path: str | Path) -> CitationGraph:
        """Load a graph from JSON: `docs` (doc id to court, court_level, bench_size, date) and `edges` (CitationEdge objects)."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        nodes = [
            NodeMeta(
                doc_id=doc, court=meta.get("court"), court_level=meta.get("court_level") or court_level_of(meta.get("court")),
                bench_size=meta.get("bench_size"), date=meta.get("date"),
            )
            for doc, meta in (data.get("docs") or data.get("nodes") or {}).items()
        ]  # fmt: skip
        return cls(nodes, [CitationEdge.model_validate(e) for e in data.get("edges", [])])
