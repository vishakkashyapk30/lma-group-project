"""S5 personalised PageRank expansion over the citation graph (HippoRAG 2 style; evaluation plan 3.3): the walk, the merge, leakage."""

from __future__ import annotations

import pytest

from vakeel_sahayak.pipelines.citation_graph import expansion as ex
from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph, NodeMeta
from vakeel_sahayak.schemas.enums import OrderPart, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge, ParagraphRecord

BEFORE = "2025-01-01"
NODES = [
    NodeMeta("HC-A", "Delhi HC", "HC", 1, "2020-01-01"),
    NodeMeta("SC-S", "Supreme Court of India", "SC", 3, "2015-01-01"),
    NodeMeta("HC-B", "Bombay HC", "HC", 1, "2019-01-01"),
    NodeMeta("HC-C", "Kerala HC", "HC", 1, "2018-01-01"),  # an island: no edge to anything else
    NodeMeta("HC-D", "Delhi HC", "HC", 1, "2021-01-01"),
    NodeMeta("LATE", "Delhi HC", "HC", 1, "2026-01-01"),  # dated after the case
    NodeMeta("NODATE", "Delhi HC", "HC", 1, None),
    NodeMeta("SC-OVR", "Supreme Court of India", "SC", 5, "2022-01-01"),
]


def edge(a: str, b: str, t: Treatment) -> CitationEdge:
    return CitationEdge(citing_doc_id=a, cited_doc_id=b, treatment=t)


EDGES = [
    edge("HC-A", "SC-S", Treatment.RELIED_ON),
    edge("HC-B", "SC-S", Treatment.FOLLOWED),
    edge("HC-D", "HC-A", Treatment.DISTINGUISHED),
    edge("LATE", "HC-A", Treatment.RELIED_ON),
    edge("NODATE", "HC-A", Treatment.RELIED_ON),
    edge("SC-OVR", "HC-A", Treatment.OVERRULED),
]


@pytest.fixture()
def graph() -> CitationGraph:
    return CitationGraph(list(NODES), list(EDGES))


def rec(doc: str, para: int, text: str = "bail", date: str = "2019-01-01") -> ParagraphRecord:
    return ParagraphRecord(doc_id=doc, para=para, court="c", date=date, part=OrderPart.REASONING, text=text)


def test_mass_is_a_distribution_led_by_the_seed(graph):
    mass = ex.personalized_pagerank(graph, {"HC-A": 1.0}, BEFORE)
    assert abs(sum(mass.values()) - 1.0) < 1e-6 and max(mass, key=mass.get) == "HC-A"
    assert mass["SC-S"] > mass["HC-B"] > 0  # the SC judgment HC-A relied on, then the sibling that also follows it


def test_walk_never_visits_later_undated_or_overruling_judgments_or_islands(graph):
    mass = ex.personalized_pagerank(graph, {"HC-A": 1.0}, BEFORE)
    assert not {"LATE", "NODATE", "SC-OVR", "HC-C"} & set(mass)
    assert "LATE" in ex.personalized_pagerank(graph, {"HC-A": 1.0}, "2027-01-01")  # it is the date, not the shape of the graph


def test_a_distinguishing_edge_carries_less_than_a_relied_on_edge(graph):
    mass = ex.personalized_pagerank(graph, {"HC-A": 1.0}, BEFORE)
    assert mass["SC-S"] > mass["HC-D"] > 0


def test_unusable_seeds_give_nothing(graph):
    assert ex.personalized_pagerank(graph, {}, BEFORE) == {}
    assert ex.personalized_pagerank(graph, {"LATE": 1.0, "UNKNOWN": 1.0, "NODATE": 1.0}, BEFORE) == {}
    assert ex.expand_documents(graph, {"HC-C": 1.0}, BEFORE).docs == []  # an island reaches nobody


def test_expansion_excludes_seeds_is_ranked_and_deterministic(graph):
    first = ex.expand_documents(graph, {"HC-A": 1.0}, BEFORE, top_n=3)
    assert first == ex.expand_documents(graph, {"HC-A": 1.0}, BEFORE, top_n=3)
    assert [d.doc_id for d in first.docs] == ["SC-S", "HC-D", "HC-B"] or [d.doc_id for d in first.docs][0] == "SC-S"
    assert "HC-A" not in {d.doc_id for d in first.docs} and first.docs[0].court_level == "SC" and first.docs[0].from_docs == ("HC-A",)
    assert len(ex.expand_documents(graph, {"HC-A": 1.0}, BEFORE, top_n=1).docs) == 1


def test_two_seeds_share_mass_and_the_common_neighbour_wins(graph):
    docs = ex.expand_documents(graph, {"HC-A": 1.0, "HC-B": 1.0}, BEFORE).docs
    assert docs[0].doc_id == "SC-S" and docs[0].from_docs == ("HC-A", "HC-B")


def test_expansion_is_leakage_safe_for_every_cutoff(graph):
    for before in ("2016-01-01", "2019-06-01", "2021-06-01", BEFORE):
        dates = {n.doc_id: n.date for n in NODES}
        walked = ex.personalized_pagerank(graph, {"HC-B": 1.0, "HC-A": 1.0}, before)
        assert all(dates[d] and dates[d] < before for d in walked)


def test_seed_weights_follow_the_rank():
    w = ex.seed_weights([rec("X", 1), rec("Y", 1), rec("X", 2)])
    assert w == {"X": 1.0 + 1 / 3, "Y": 0.5}


def test_merge_keeps_seeds_adds_per_doc_and_marks_the_graph_hits():
    seeds = [rec("HC-A", 1, "parity bail")]
    scored = [(rec("HC-A", 1), 0.9), (rec("SC-S", 5), 0.8), (rec("SC-S", 6), 0.7), (rec("SC-S", 7), 0.6), (rec("HC-B", 1), 0.99)]
    docs = [ex.ExpandedDoc("SC-S", 0.2, ("HC-A",), "SC")]
    out = ex.merge_ranked(seeds, scored, docs, {"HC-A": 0.5, "SC-S": 0.2}, k=10, per_doc=2)
    assert [(p.doc_id, p.para, p.expanded) for p in out] == [("HC-A", 1, False), ("SC-S", 5, True), ("SC-S", 6, True)]
    assert out[1].graph_from == ["HC-A"] and out[1].text_score == 0.8 and 0 < out[1].ppr < 1
    assert "HC-B" not in {p.doc_id for p in out}  # not a seed, not expanded: never added
    assert len(ex.merge_ranked(seeds, scored, docs, {"HC-A": 0.5, "SC-S": 0.2}, k=2)) == 2


def test_walk_weight_can_lift_a_graph_paragraph_above_a_weak_text_match():
    seeds = [rec("HC-A", 1)]
    scored = [(rec("HC-A", 1), 0.5), (rec("SC-S", 5), 0.4)]
    docs = [ex.ExpandedDoc("SC-S", 0.4, ("HC-A",), "SC")]
    mass = {"HC-A": 0.1, "SC-S": 0.4}
    assert ex.merge_ranked(seeds, scored, docs, mass, 5, ppr_weight=0.0)[0].doc_id == "HC-A"
    assert ex.merge_ranked(seeds, scored, docs, mass, 5, ppr_weight=0.8)[0].doc_id == "SC-S"


def test_sc_share(graph):
    assert ex.sc_share([rec("SC-S", 1), rec("HC-A", 1)], graph) == 0.5 and ex.sc_share([], graph) == 0.0
