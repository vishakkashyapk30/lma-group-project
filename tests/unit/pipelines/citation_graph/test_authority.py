"""Good-law check inputs (plan §5.3): a precedent is flagged when a later SC judgment (or larger bench) treats it as
overruled; 'distinguished' is shown but does not block."""

from __future__ import annotations

import json

from vakeel_sahayak.pipelines.citation_graph.authority import find_overruled


def graph_file(tmp_path, docs: dict, edges: list[dict]):
    """ASSUMPTION: the graph file is JSON {"docs": {doc_id: {"court_level", "date"}}, "edges": [CitationEdge dicts]}."""
    path = tmp_path / "graph.json"
    path.write_text(json.dumps({"docs": docs, "edges": edges}))
    return str(path)


def edge(citing: str, cited: str, treatment: str, level: str) -> dict:
    return {"citing_doc_id": citing, "cited_doc_id": cited, "treatment": treatment, "court_level": level}


DOCS = {
    "HC-2021-A": {"court_level": "HC", "date": "2021-03-10"},
    "HC-2022-B": {"court_level": "HC", "date": "2022-06-03"},
    "HC-2022-C": {"court_level": "HC", "date": "2022-08-01"},
    "SC-2023-X": {"court_level": "SC", "date": "2023-05-19"},
    "SC-2024-Y": {"court_level": "SC", "date": "2024-02-02"},
    "HC-2024-Z": {"court_level": "HC", "date": "2024-04-04"},
}


def test_precedent_overruled_by_a_later_sc_judgment_is_flagged(tmp_path):
    """An HC precedent that a later SC judgment overrules is flagged, mapped to the overruling judgment."""
    path = graph_file(tmp_path, DOCS, [edge("SC-2023-X", "HC-2021-A", "OVERRULED", "SC")])
    assert find_overruled(path) == {"HC-2021-A": "SC-2023-X"}


def test_distinguished_is_not_flagged(tmp_path):
    """'Distinguished' is shown but does not block, so it is not in the overruled map."""
    path = graph_file(tmp_path, DOCS, [edge("SC-2023-X", "HC-2022-B", "DISTINGUISHED", "SC")])
    assert find_overruled(path) == {}


def test_other_treatments_are_not_flagged(tmp_path):
    """Followed, relied on, referred and unknown treatments never flag a precedent."""
    edges = [edge("SC-2023-X", "HC-2021-A", t, "SC") for t in ("FOLLOWED", "RELIED_ON", "REFERRED", "UNKNOWN")]
    assert find_overruled(graph_file(tmp_path, DOCS, edges)) == {}


def test_overruled_only_by_a_high_court_is_not_flagged(tmp_path):
    """ASSUMPTION: only a later SC judgment (or larger bench) can overrule; one HC calling another overruled does not flag it."""
    path = graph_file(tmp_path, DOCS, [edge("HC-2024-Z", "HC-2022-C", "OVERRULED", "HC")])
    assert find_overruled(path) == {}


def test_several_precedents_each_get_their_overruling_judgment(tmp_path):
    """Two precedents overruled by two different SC judgments are both flagged; an untouched one is not."""
    edges = [
        edge("SC-2023-X", "HC-2021-A", "OVERRULED", "SC"),
        edge("SC-2024-Y", "HC-2022-B", "OVERRULED", "SC"),
        edge("SC-2024-Y", "HC-2022-C", "FOLLOWED", "SC"),
    ]
    assert find_overruled(graph_file(tmp_path, DOCS, edges)) == {"HC-2021-A": "SC-2023-X", "HC-2022-B": "SC-2024-Y"}


def test_overruling_judgment_must_be_later_than_the_precedent(tmp_path):
    """ASSUMPTION: an 'overruled' edge from a judgment dated BEFORE the precedent is data noise and is ignored."""
    docs = dict(DOCS)
    path = graph_file(tmp_path, docs, [edge("SC-2023-X", "SC-2024-Y", "OVERRULED", "SC")])
    assert find_overruled(path) == {}


def test_empty_graph_has_no_overruled_precedents(tmp_path):
    """No edges, nothing flagged."""
    assert find_overruled(graph_file(tmp_path, DOCS, [])) == {}
