"""Builder of `caselaw.citations` (plan §5.1, §5.3): who cites whom, with treatment and court level; authority score;
good-law check; SC root. Test and same-FIR orders are excluded (plan §2).

Input (ASSUMPTION, see `_helpers.py`): resolved `CitationEdge` rows in `citation_edges.jsonl`.
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines.store_builders._helpers import SAME_FIR_ORDER, TEST_ORDER
from vakeel_sahayak.pipelines.store_builders.build_citations import build_citations
from vakeel_sahayak.schemas.enums import GoodLawStatus, StoreName, Treatment
from vakeel_sahayak.stores.caselaw_citations import CitationStore


@pytest.fixture()
def built(interim, excluded, tmp_path):
    out = tmp_path / "citations"
    n = build_citations(str(interim), str(out), exclude_doc_ids=excluded)
    store = CitationStore()
    store.open(str(out))
    yield n, store
    store.close()


def test_store_identity():
    assert CitationStore.name == StoreName.CASELAW_CITATIONS


def test_edge_from_an_excluded_order_is_dropped(built):
    """Four edges are given, one of them out of the test order: three are stored."""
    n, store = built
    assert n == store.count() == 3


def test_cited_by_lists_the_citing_orders_with_treatment(built):
    """SC-2014-0463 is relied on by DLHC-2022-1187 and followed by DLHC-2020-0500; the excluded order is not among them."""
    _, store = built
    edges = store.cited_by("SC-2014-0463")
    assert {e.citing_doc_id for e in edges} == {"DLHC-2022-1187", "DLHC-2020-0500"}
    assert {e.treatment for e in edges} == {Treatment.RELIED_ON, Treatment.FOLLOWED}
    assert all(e.court_level == "HC" for e in edges)
    assert TEST_ORDER not in {e.citing_doc_id for e in edges} and SAME_FIR_ORDER not in {e.citing_doc_id for e in edges}


def test_cites_is_the_reverse_direction(built):
    _, store = built
    assert [e.cited_doc_id for e in store.cites("DLHC-2022-1187")] == ["SC-2014-0463"]


def test_authority_score_ranks_the_cited_supreme_court_judgment_first(built):
    """Plan §5.3: court level, citations from other bail cases and recency feed the score; scores lie in [0, 1]."""
    _, store = built
    sc, hc = store.authority_score("SC-2014-0463"), store.authority_score("DLHC-2022-1187")
    assert 0.0 <= hc < sc <= 1.0


def test_overruled_precedent_is_flagged(built):
    """SC-2020-0100 overrules DLHC-2023-0911: good_law is OVERRULED and names the overruling judgment (plan §5.3)."""
    _, store = built
    res = store.good_law("DLHC-2023-0911")
    assert res.status == GoodLawStatus.OVERRULED
    assert res.overruled_by == "SC-2020-0100"


def test_precedent_with_no_adverse_treatment_is_ok(built):
    _, store = built
    assert store.good_law("SC-2014-0463").status == GoodLawStatus.OK


def test_sc_root_of_a_high_court_order_follows_the_graph(built):
    """For a High Court paragraph the graph leads to the SC judgment it relies on, so both can be cited (plan §5.3)."""
    _, store = built
    assert store.sc_root("DLHC-2022-1187") == "SC-2014-0463"
    assert store.sc_root("SC-2014-0463") in (None, "SC-2014-0463")


def test_edges_to_an_excluded_order_are_dropped_too(interim, tmp_path):
    """An edge *into* an excluded order is dropped as well (it would leak the order's existence)."""
    from tests.unit.pipelines.store_builders._helpers import citation_edges, write_jsonl

    rows = citation_edges() + [{"citing_doc_id": "DLHC-2022-1187", "cited_doc_id": TEST_ORDER, "treatment": "REFERRED",
                                "court_level": "HC", "sentence": "x"}]
    write_jsonl(interim / "citation_edges.jsonl", rows)
    out = tmp_path / "c2"
    n = build_citations(str(interim), str(out), exclude_doc_ids={TEST_ORDER, SAME_FIR_ORDER})
    assert n == 3
