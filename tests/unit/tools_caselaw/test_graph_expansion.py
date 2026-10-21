"""S5 `search_reasoning(expand_graph=True)` over small synthetic real stores (no store build): index prefix filter, `search_docs`,
`CitationStore.expand`, the tool, leakage, graceful fallback and the unchanged default."""

from __future__ import annotations

import inspect

import pytest

from vakeel_sahayak.pipelines.citation_graph.expansion import ExpandedParagraph
from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph, NodeMeta
from vakeel_sahayak.schemas.enums import Factor, OrderPart, StoreName, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge, ParagraphRecord
from vakeel_sahayak.stores.caselaw_citations import CitationStore
from vakeel_sahayak.stores.caselaw_reasoning import ReasoningStore
from vakeel_sahayak.stores.hybrid import HybridIndex
from vakeel_sahayak.stores.leakage_guard import LeakageError
from vakeel_sahayak.stores.paragraph_store import paragraph_index_rows
from vakeel_sahayak.tools import store_call
from vakeel_sahayak.tools.base import ToolError
from vakeel_sahayak.tools.caselaw.reasoning import search_reasoning

BEFORE = "2025-02-03"


def para(doc: str, n: int, text: str, date: str, court: str = "Delhi High Court", factors=(Factor.PARITY_WITH_CO_ACCUSED,)) -> ParagraphRecord:
    return ParagraphRecord(doc_id=doc, para=n, court=court, date=date, part=OrderPart.REASONING, factors=list(factors), section_family=["IPC 420"], text=text)


PARAGRAPHS = [
    para("HC-A", 1, "parity co-accused similar role granted bail parity principle", "2022-06-03"),
    para("HC-A", 2, "the petitioner is in custody since arrest and the charge sheet is filed", "2022-06-03"),
    para("SC-S", 5, "the principle of parity requires equal treatment of co-accused with a similar role", "2014-05-05", "Supreme Court of India"),
    para("SC-S", 6, "unrelated discussion of limitation under the contract act", "2014-05-05", "Supreme Court of India"),
    para("HC-B", 1, "trial delay and speedy trial under article 21", "2021-01-01", "Bombay High Court", (Factor.TRIAL_DELAY,)),
    para("LATE", 1, "parity co-accused bail parity principle", "2025-03-01"),  # dated after the case
]
NODES = [
    NodeMeta("HC-A", "Delhi High Court", "HC", 1, "2022-06-03"), NodeMeta("SC-S", "Supreme Court of India", "SC", 3, "2014-05-05"),
    NodeMeta("HC-B", "Bombay High Court", "HC", 1, "2021-01-01"), NodeMeta("LATE", "Delhi High Court", "HC", 1, "2025-03-01"),
]
EDGES = [
    CitationEdge(citing_doc_id="HC-A", cited_doc_id="SC-S", treatment=Treatment.RELIED_ON),
    CitationEdge(citing_doc_id="LATE", cited_doc_id="HC-A", treatment=Treatment.RELIED_ON),
]


@pytest.fixture()
def reasoning():
    store = ReasoningStore()
    store.open(":memory:")
    store._index.add(paragraph_index_rows(PARAGRAPHS))
    yield store
    store.close()


@pytest.fixture()
def citations():
    store = CitationStore()
    store.open(":memory:")
    store._graph = CitationGraph(list(NODES), list(EDGES))
    return store


@pytest.fixture()
def tool_stores(monkeypatch, reasoning, citations):
    """Route the tool's store opens to the synthetic stores (closing them per call is a no-op here)."""
    opened = []

    def fake_open(name, path=None, case_id=None):
        opened.append(name)
        return {StoreName.CASELAW_REASONING: reasoning, StoreName.CASELAW_CITATIONS: citations}[name]

    monkeypatch.setattr(store_call, "open_store", fake_open)
    monkeypatch.setattr(reasoning, "close", lambda: None)
    monkeypatch.setattr(citations, "close", lambda: None)
    return opened


QUERY = "parity co-accused similar role bail"


def ids(hits):
    return [f"{h.doc_id}#{h.para}" for h in hits]


# ---- the index prefix filter -----------------------------------------------------------------------------------
def test_index_key_prefixes_restrict_rows():
    index = HybridIndex(None)
    index.add(paragraph_index_rows(PARAGRAPHS))
    hits = index.search("parity co-accused", key_prefixes=["SC-S#"], k=10)
    assert {h.key.split("#")[0] for h in hits} == {"SC-S"}
    assert {h.key.split("#")[0] for h in index.search("parity co-accused", key_prefixes=["SC-S#", "HC-A#"], k=10)} == {"SC-S", "HC-A"}
    assert index.search("parity", key_prefixes=["NOPE#"]) == []
    assert len(index.search("parity co-accused", k=10)) > len(hits)  # no prefixes: unrestricted


def test_prefix_is_a_judgment_boundary_not_a_string_prefix():
    index = HybridIndex(None)
    index.add(paragraph_index_rows([para("HC-A", 1, "parity bail", "2020-01-01"), para("HC-AB", 1, "parity bail", "2020-01-01")]))
    assert {h.key for h in index.search("parity bail", key_prefixes=["HC-A#"])} == {"HC-A#1"}


# ---- store methods ---------------------------------------------------------------------------------------------
def test_search_docs_ranks_only_the_named_judgments_before_the_date(reasoning):
    out = reasoning.search_docs(QUERY, ["SC-S", "LATE"], before=BEFORE)
    assert {r.doc_id for r, _ in out} == {"SC-S"}  # LATE is dated after the case
    assert out[0][0].para == 5 and all(0 <= s <= 1 for _, s in out) and out[0][1] >= out[-1][1]
    with pytest.raises(LeakageError):
        reasoning.search_docs(QUERY, ["SC-S"], before=None)
    assert reasoning.search_docs(QUERY, [], before=BEFORE) == []


def test_citation_store_expand_is_leakage_safe(citations):
    exp = citations.expand({"HC-A": 1.0}, BEFORE)
    assert [d.doc_id for d in exp.docs] == ["SC-S"] and "LATE" not in exp.mass
    assert "LATE" in citations.expand({"HC-A": 1.0}, "2026-01-01").mass
    with pytest.raises(LeakageError):
        citations.expand({"HC-A": 1.0}, "")


# ---- the tool --------------------------------------------------------------------------------------------------
def test_default_call_is_unchanged_and_signature_is_backward_compatible(tool_stores):
    sig = inspect.signature(search_reasoning)
    assert list(sig.parameters)[:7] == ["query", "factor", "section_family", "before", "outcome", "court", "k"] and sig.parameters["expand_graph"].default is False
    plain = search_reasoning(QUERY, factor=Factor.PARITY_WITH_CO_ACCUSED, before=BEFORE, k=5)
    assert not any(isinstance(h, ExpandedParagraph) for h in plain) and StoreName.CASELAW_CITATIONS not in tool_stores


def test_expansion_pulls_in_the_supreme_court_authority_behind_a_high_court_paragraph(tool_stores):
    plain = search_reasoning(QUERY, factor=Factor.PARITY_WITH_CO_ACCUSED, section_family=["IPC 420"], before=BEFORE, k=10, court="Delhi High Court")
    assert "SC-S#5" not in ids(plain)  # the factor, family and court filters keep the SC judgment out of the plain search
    out = search_reasoning(QUERY, factor=Factor.PARITY_WITH_CO_ACCUSED, section_family=["IPC 420"], before=BEFORE, k=10, court="Delhi High Court", expand_graph=True)
    hits = {f"{h.doc_id}#{h.para}": h for h in out}
    assert "SC-S#5" in hits and hits["SC-S#5"].expanded and hits["SC-S#5"].graph_from == ["HC-A"]
    assert set(ids(plain)) <= set(ids(out)) and all(not hits[i].expanded for i in ids(plain))
    assert "SC-S#6" not in hits or hits["SC-S#6"].text_score <= hits["SC-S#5"].text_score  # ranked by text inside the judgment


def test_expansion_never_adds_a_document_dated_after_the_case(tool_stores):
    out = search_reasoning(QUERY, before=BEFORE, k=20, expand_graph=True)
    assert out and all(h.date < BEFORE for h in out) and "LATE" not in {h.doc_id for h in out}
    early = search_reasoning(QUERY, before="2015-01-01", k=20, expand_graph=True)
    assert all(h.date < "2015-01-01" for h in early)


def test_expansion_is_deterministic_and_respects_k(tool_stores):
    a = search_reasoning(QUERY, before=BEFORE, k=3, expand_graph=True)
    assert ids(a) == ids(search_reasoning(QUERY, before=BEFORE, k=3, expand_graph=True)) and len(a) <= 3


def test_a_missing_graph_or_no_seeds_returns_the_plain_result(monkeypatch, tool_stores, citations):
    plain = search_reasoning(QUERY, before=BEFORE, k=5)
    monkeypatch.setattr(citations, "expand", lambda *a, **k: (_ for _ in ()).throw(OSError("graph file missing")))
    assert ids(search_reasoning(QUERY, before=BEFORE, k=5, expand_graph=True)) == ids(plain)
    assert search_reasoning("zzz nothing matches", before=BEFORE, expand_graph=True) == search_reasoning("zzz nothing matches", before=BEFORE)


def test_invalid_arguments_still_error_with_expansion_on(tool_stores):
    assert isinstance(search_reasoning("", before=BEFORE, expand_graph=True), ToolError)
    assert isinstance(search_reasoning(QUERY, expand_graph=True), ToolError)  # `before` is still mandatory
