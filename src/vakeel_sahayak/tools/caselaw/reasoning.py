"""Tools in caselaw.reasoning (plan §5.1, §8.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.pipelines.citation_graph.expansion import EXPAND_DOCS, ScoredParagraph, merge_ranked, seed_weights
from vakeel_sahayak.schemas.enums import AgentName, Factor, OrderPart, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, invalid, parse_filters

SCORED_PARAGRAPHS = 300  # paragraphs ranked by text across the seed and expanded judgments (S5)


def search_reasoning(
    query: str,
    factor: Factor | None = None,
    section_family: list[str] | None = None,
    before: str | None = None,
    outcome: str | None = None,
    court: str | None = None,
    k: int = 10,
    expand_graph: bool = False,
    with_scores: bool = False,
) -> list[ParagraphRecord] | ToolError:
    """Hybrid BM25 + BGE-M3 with metadata pre-filter over reasoning paragraphs. (plan §5.1)

    Args:
        query: see behaviour
        factor: see behaviour
        section_family: see behaviour
        before: only documents dated before the case's order; required (leakage rule, plan §2)
        outcome: see behaviour
        court: see behaviour
        k: see behaviour
        expand_graph: S5 (HippoRAG 2 style, see `pipelines/citation_graph/expansion.py`): after the plain search, a personalised PageRank over
            the citation graph seeded from the found judgments adds paragraphs of judgments the graph links to (for example the Supreme
            Court authority behind a High Court paragraph) and the union is re-ranked by text score plus walk score. Default False: the
            plain hybrid search, unchanged. If the citation graph is unavailable the plain result is returned.
        with_scores: S4 (SkewRoute style, see `agents/sutradhar/skew.py`): return `ScoredParagraph` records that carry the final hybrid score
            of each paragraph, so a caller can measure the skew of the score list. Default False: plain records, unchanged.

    Returns:
        Paragraphs (`ExpandedParagraph` records, with `expanded`, `ppr`, `text_score` and `graph_from`, when `expand_graph` is True and the graph answered).
    """
    tool = "search_reasoning"
    if err := check_search_args(tool, query, k, before):
        return err
    parsed, family, err = parse_filters(tool, factor, section_family)
    if err:
        return err
    if with_scores:
        pairs = call_store(
            tool, StoreName.CASELAW_REASONING,
            lambda s: s.search_scored(query, factor=parsed, section_family=family, before=before, outcome=outcome, court=court, k=k),
        )  # fmt: skip
        plain: Any = pairs if isinstance(pairs, ToolError) else [ScoredParagraph(**r.model_dump(), score=sc) for r, sc in pairs]
    else:
        plain = call_store(
            tool, StoreName.CASELAW_REASONING,
            lambda s: s.search(query, factor=parsed, section_family=family, before=before, outcome=outcome, court=court, k=k),
        )  # fmt: skip
    if not expand_graph or isinstance(plain, ToolError) or not plain:
        return plain
    return expand_search(
        query, plain, before or "", k,
        expand=lambda seeds, top_n: call_store(tool, StoreName.CASELAW_CITATIONS, lambda s: s.expand(seeds, before or "", top_n)),
        search_docs=lambda docs, kk: call_store(tool, StoreName.CASELAW_REASONING, lambda s: s.search_docs(query, docs, before=before, k=kk)),
    )  # fmt: skip


def expand_search(
    query: str, seeds: list[ParagraphRecord], before: str, k: int, *, expand: Any, search_docs: Any, top_n: int = EXPAND_DOCS,
) -> list[ParagraphRecord]:  # fmt: skip
    """The S5 steps after the plain search, over two callables so the logic is the same for the real stores and for test doubles.

    `expand(seed_weights, top_n)` returns an `Expansion` (or a ToolError); `search_docs(doc_ids, k)` returns (paragraph, score) pairs (or a
    ToolError). Any failure or an empty expansion returns the plain `seeds` unchanged (a missing graph must not cost the search its result).
    """
    weights = seed_weights(seeds)
    result = expand(weights, top_n)
    if isinstance(result, ToolError) or not result.docs:
        return seeds
    scored = search_docs(list(dict.fromkeys([*weights, *(d.doc_id for d in result.docs)])), SCORED_PARAGRAPHS)
    if isinstance(scored, ToolError) or not scored:
        return seeds
    return merge_ranked(seeds, scored, result.docs, result.mass, k)  # type: ignore[return-value]


def get_paragraph(doc_id: str, para: int) -> ParagraphRecord | ToolError:
    """Fetch one reasoning paragraph by id; a submission paragraph is refused. (plan §8.1)

    Args:
        doc_id: see behaviour
        para: see behaviour

    Returns:
        ParagraphRecord.
    """
    if not isinstance(doc_id, str) or not doc_id.strip():
        return invalid("get_paragraph", "doc_id must not be empty")
    if not isinstance(para, int) or isinstance(para, bool) or para < 1:
        return invalid("get_paragraph", "para must be an integer of at least 1")
    return call_store("get_paragraph", StoreName.CASELAW_REASONING, lambda s: _reasoning_only(s.get_paragraph(doc_id, para)))


def _reasoning_only(record: ParagraphRecord) -> ParagraphRecord:
    """Submissions (defense, prosecution) are for coverage and phrasing, never authority: only reasoning can be cited (plan §5.1)."""
    if record.part != OrderPart.REASONING:
        raise LookupError(
            f"paragraph {record.para} of {record.doc_id} is part of the {record.part.value}, not the court's reasoning; it cannot be cited"
        )
    return record


SEARCH_REASONING_SPEC = ToolSpec(
    name="search_reasoning",
    description="Hybrid BM25 + BGE-M3 with metadata pre-filter over reasoning paragraphs.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK],
    stores=[StoreName.CASELAW_REASONING],
    plan_ref="§5.1",
)

GET_PARAGRAPH_SPEC = ToolSpec(
    name="get_paragraph",
    description="Fetch one paragraph by id.",
    agents=[AgentName.VAKEEL],
    stores=[StoreName.CASELAW_REASONING],
    plan_ref="§8.1",
)
