"""S4 `search_reasoning(with_scores=True)` and `ReasoningStore.search_scored` over a small synthetic store: scores in [0, 1], same order as the plain search, default unchanged."""

from __future__ import annotations

import inspect

import pytest

from tests.unit.tools_caselaw.test_graph_expansion import BEFORE, QUERY, citations, reasoning, tool_stores  # noqa: F401  (fixtures)
from vakeel_sahayak.pipelines.citation_graph.expansion import ExpandedParagraph, ScoredParagraph
from vakeel_sahayak.schemas.enums import Factor
from vakeel_sahayak.stores.leakage_guard import LeakageError
from vakeel_sahayak.tools.base import ToolError
from vakeel_sahayak.tools.caselaw.reasoning import search_reasoning


def ids(hits):
    return [f"{h.doc_id}#{h.para}" for h in hits]


def test_search_scored_matches_search_order_and_bounds(reasoning):  # noqa: F811
    plain = reasoning.search(QUERY, before=BEFORE, k=10)
    pairs = reasoning.search_scored(QUERY, before=BEFORE, k=10)
    assert ids([r for r, _ in pairs]) == ids(plain) and all(0 <= s <= 1 for _, s in pairs)
    assert [s for _, s in pairs] == sorted((s for _, s in pairs), reverse=True)
    with pytest.raises(LeakageError):
        reasoning.search_scored(QUERY, before=None)


def test_with_scores_adds_the_score_and_keeps_the_hits(tool_stores):  # noqa: F811
    plain = search_reasoning(QUERY, before=BEFORE, k=10)
    scored = search_reasoning(QUERY, before=BEFORE, k=10, with_scores=True)
    assert ids(scored) == ids(plain) and all(isinstance(h, ScoredParagraph) and 0 <= h.score <= 1 for h in scored)
    assert not any(isinstance(h, ScoredParagraph) for h in plain)


def test_signature_is_backward_compatible():
    sig = inspect.signature(search_reasoning)
    assert list(sig.parameters)[:7] == ["query", "factor", "section_family", "before", "outcome", "court", "k"]
    assert sig.parameters["with_scores"].default is False and sig.parameters["expand_graph"].default is False


def test_scores_and_expansion_combine(tool_stores):  # noqa: F811
    out = search_reasoning(QUERY, factor=Factor.PARITY_WITH_CO_ACCUSED, before=BEFORE, k=10, with_scores=True, expand_graph=True)
    assert out and all(isinstance(h, (ExpandedParagraph, ScoredParagraph)) for h in out)


def test_errors_are_unchanged_with_scores_on(tool_stores):  # noqa: F811
    assert isinstance(search_reasoning("", before=BEFORE, with_scores=True), ToolError)
    assert isinstance(search_reasoning(QUERY, with_scores=True), ToolError)
