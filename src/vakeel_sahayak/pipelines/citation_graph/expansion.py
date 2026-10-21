"""S5: expansion of retrieved paragraphs through the citation graph with personalised PageRank (evaluation plan 3.3, variant S5).

Switch: `Switches.graph_expansion` (False by default); the tool argument is `search_reasoning(expand_graph=True)`.

Papers and what we took
-----------------------
* Bernal Jimenez Gutierrez, Yiheng Shu, Weijian Qi, Sizhe Zhou, Yu Su. "From RAG to Memory: Non-Parametric Continual Learning for
  Large Language Models" (HippoRAG 2). ICML 2025, PMLR 267, pp. 21497-21515. https://proceedings.mlr.press/v267/gutierrez25a.html
  Taken: seed a personalised PageRank on the graph from the nodes the first retrieval found, spread probability along the graph's
  edges, and rank what is reached by the resulting scores together with the text score of the passages (a graph-based "memory" that
  reaches documents the query text alone does not match).
* Bernal Jimenez Gutierrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, Yu Su. "HippoRAG: Neurobiologically Inspired Long-Term Memory
  for Large Language Models". NeurIPS 2024. https://arxiv.org/abs/2405.14831 (the original PPR-over-a-knowledge-graph retrieval).
* Context for the expected result: "When to use Graphs in RAG" (GraphRAG-Bench), ICLR 2026, https://iclr.cc/virtual/2026/poster/10007992
  reports that graph retrieval often loses to plain RAG, so a null result on some factors is an expected outcome, not a defect.

What we changed, and why
------------------------
HippoRAG builds a knowledge graph of LLM-extracted triples and links passages to phrase nodes. We build no triple graph (that needs
an LLM pass over the corpus): our graph is the court-citation graph the corpus already has (`CitationGraph`: judgments as nodes,
treated citation edges). Seeds are the judgments of the top plain-retrieval paragraphs, weighted by their rank; the walk runs over
citing and cited edges (a followed or relied-on edge carries the most weight, a distinguished one little, an overruled one none;
the reverse direction counts half) with damping 0.5 as in HippoRAG; the expanded judgments are then scored by text (their own
paragraphs are ranked against the query by the same hybrid index) and the final rank adds the walk score. Constants
(`DAMPING`, `PPR_WEIGHT`, `EXPAND_DOCS`, `PER_DOC`, edge weights) are our assumptions, to be tuned on the dev split.

Leakage: the walk only visits judgments with a known date strictly before the case's order date, and the paragraphs it adds are
fetched with the same `before` filter, so an expansion can never add a document the plain search could not have returned.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph
from vakeel_sahayak.schemas.enums import Treatment
from vakeel_sahayak.schemas.store_rows import ParagraphRecord

DAMPING = 0.5  # probability of following an edge (HippoRAG uses 0.5); 1 - DAMPING returns to the seeds
ITERATIONS = 30
TOLERANCE = 1e-9
REVERSE_FACTOR = 0.5  # a citation is walked backwards (cited -> citing) at half weight
EXPAND_DOCS = 5  # judgments added to the seeds
PER_DOC = 2  # paragraphs taken from each expanded judgment
PPR_WEIGHT = 0.3  # share of the walk score in the final rank (text score gets the rest)
EDGE_WEIGHT: dict[Treatment, float] = {Treatment.FOLLOWED: 1.0, Treatment.RELIED_ON: 1.0, Treatment.DISTINGUISHED: 0.3, Treatment.OVERRULED: 0.0}
OTHER_EDGE_WEIGHT = 0.2


@dataclass(frozen=True)
class ExpandedDoc:
    """A judgment reached by the walk: its score (probability mass, summing to at most 1 over the graph) and the seeds it is linked to."""

    doc_id: str
    score: float
    from_docs: tuple[str, ...]
    court_level: str = "OTHER"


@dataclass(frozen=True)
class Expansion:
    """Result of one walk: the judgments added to the seeds, and the walk score of every judgment it visited (seeds included)."""

    docs: list[ExpandedDoc]
    mass: dict[str, float]


class ScoredParagraph(ParagraphRecord):
    """A paragraph returned by `search_reasoning(with_scores=True)`: the record plus its final hybrid score in [0, 1] (S4)."""

    score: float = 0.0


class ExpandedParagraph(ParagraphRecord):
    """A paragraph returned by `search_reasoning(expand_graph=True)`: the record plus how the graph ranked it."""

    expanded: bool = False  # True when its judgment was reached through the citation graph rather than the plain search
    ppr: float = 0.0  # walk score of its judgment, scaled to [0, 1] over the candidates
    text_score: float = 0.0
    graph_from: list[str] = []  # the seed judgments it is linked to


def _known_before(graph: CitationGraph, doc_id: str, before: str) -> bool:
    node = graph.nodes.get(doc_id)
    return bool(node and node.date and node.date < before)


def _edge_weight(treatment: Treatment) -> float:
    return EDGE_WEIGHT.get(treatment, OTHER_EDGE_WEIGHT)


def personalized_pagerank(graph: CitationGraph, seeds: dict[str, float], before: str, *, damping: float = DAMPING, iterations: int = ITERATIONS) -> dict[str, float]:
    """Personalised PageRank over the judgments dated before `before`, restarting at the weighted seeds.

    Args:
        graph: the citation graph
        seeds: judgment -> weight (normalised here; seeds that are unknown or not dated before `before` are dropped)
        before: ISO date; judgments not strictly earlier (or undated) take no part in the walk
        damping: probability of following an edge at each step
        iterations: power-iteration steps (stops earlier at `TOLERANCE`)

    Returns:
        Judgment -> probability mass; empty when no seed is usable. Deterministic (nodes visited in sorted order).
    """
    usable = {d: float(w) for d, w in seeds.items() if w > 0 and _known_before(graph, d, before)}
    total = sum(usable.values())
    if not usable:
        return {}
    restart = {d: w / total for d, w in usable.items()}
    nbrs: dict[str, dict[str, float]] = defaultdict(dict)
    for e in graph.edges():
        w = _edge_weight(e.treatment)
        a, b = e.citing_doc_id, e.cited_doc_id
        if w <= 0 or not (_known_before(graph, a, before) and _known_before(graph, b, before)):
            continue
        nbrs[a][b] = nbrs[a].get(b, 0.0) + w
        nbrs[b][a] = nbrs[b].get(a, 0.0) + w * REVERSE_FACTOR
    mass = dict(restart)
    for _ in range(iterations):
        nxt: dict[str, float] = {d: (1 - damping) * p for d, p in restart.items()}
        for doc in sorted(mass):
            out = nbrs.get(doc)
            if not out:  # a dangling node returns its mass to the seeds
                for d, p in restart.items():
                    nxt[d] = nxt.get(d, 0.0) + damping * mass[doc] * p
                continue
            norm = sum(out.values())
            for nb in sorted(out):
                nxt[nb] = nxt.get(nb, 0.0) + damping * mass[doc] * out[nb] / norm
        delta = sum(abs(nxt.get(d, 0.0) - mass.get(d, 0.0)) for d in set(nxt) | set(mass))
        mass = nxt
        if delta < TOLERANCE:
            break
    return mass


def expand_documents(graph: CitationGraph, seeds: dict[str, float], before: str, top_n: int = EXPAND_DOCS) -> Expansion:
    """The `top_n` judgments other than the seeds with the largest walk score, best first (ties by doc id); never one dated on or after `before`."""
    mass = personalized_pagerank(graph, seeds, before)
    ranked = sorted(((d, s) for d, s in mass.items() if d not in seeds and s > 0), key=lambda t: (-t[1], t[0]))[: max(0, top_n)]
    out = []
    for doc, score in ranked:
        linked = {e.cited_doc_id for e in graph.cites(doc)} | {e.citing_doc_id for e in graph.cited_by(doc)}
        out.append(ExpandedDoc(doc, round(score, 8), tuple(sorted(linked & set(seeds))), graph.nodes[doc].court_level))
    return Expansion(out, mass)


def seed_weights(seed_paragraphs: list[ParagraphRecord]) -> dict[str, float]:
    """Judgment weights from the plain search's ranking: each paragraph adds 1/rank to its judgment (rank from 1)."""
    weights: dict[str, float] = {}
    for rank, rec in enumerate(seed_paragraphs, start=1):
        weights[rec.doc_id] = weights.get(rec.doc_id, 0.0) + 1.0 / rank
    return weights


def merge_ranked(
    seeds: list[ParagraphRecord], scored: list[tuple[ParagraphRecord, float]], expanded: list[ExpandedDoc], mass: dict[str, float], k: int,
    *, ppr_weight: float = PPR_WEIGHT, per_doc: int = PER_DOC,
) -> list[ExpandedParagraph]:  # fmt: skip
    """Final ranking of seeds and graph-reached paragraphs: text score plus `ppr_weight` times the walk score of the paragraph's judgment.

    Args:
        seeds: the plain search's paragraphs (kept as candidates whatever their judgment's score)
        scored: (paragraph, hybrid text score in [0, 1]) for the paragraphs of the seed and expanded judgments, one text ranking over all
        expanded: the judgments the walk reached
        mass: walk score per judgment (from `personalized_pagerank`); scaled by its maximum here
        k: results wanted
        ppr_weight: share of the walk score
        per_doc: paragraphs taken from each expanded judgment

    Returns:
        Up to `k` `ExpandedParagraph`, best first (ties by judgment and paragraph number).
    """
    text = {(r.doc_id, r.para): s for r, s in scored}
    top = max(mass.values(), default=0.0) or 1.0
    linked = {e.doc_id: list(e.from_docs) for e in expanded}
    pool: dict[tuple[str, int], ExpandedParagraph] = {}

    def add(rec: ParagraphRecord, is_expanded: bool) -> None:
        key = (rec.doc_id, rec.para)
        if key in pool:
            return
        pool[key] = ExpandedParagraph(
            **rec.model_dump(), expanded=is_expanded, ppr=round(mass.get(rec.doc_id, 0.0) / top, 6),
            text_score=round(text.get(key, 0.0), 6), graph_from=linked.get(rec.doc_id, []),
        )  # fmt: skip

    for rec in seeds:
        add(rec, False)
    wanted = {e.doc_id for e in expanded}
    taken: dict[str, int] = defaultdict(int)
    for rec, _ in sorted(scored, key=lambda t: (-t[1], t[0].doc_id, t[0].para)):
        if rec.doc_id in wanted and taken[rec.doc_id] < per_doc:
            taken[rec.doc_id] += 1
            add(rec, True)
    final = sorted(pool.values(), key=lambda p: (-((1 - ppr_weight) * p.text_score + ppr_weight * p.ppr), p.doc_id, p.para))
    return final[: max(0, k)]


def sc_share(paragraphs: list[Any], graph: CitationGraph) -> float:
    """Share of the paragraphs whose judgment is a Supreme Court judgment in the graph (the S5 evaluation reads it)."""
    docs = [getattr(p, "doc_id", None) or p.get("doc_id") for p in paragraphs]
    if not docs:
        return 0.0
    return sum(1 for d in docs if d in graph.nodes and graph.nodes[d].court_level == "SC") / len(docs)
