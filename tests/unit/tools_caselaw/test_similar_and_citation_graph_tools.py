"""`similar_orders`, `citations`, `good_law_check` (plan §5.1 caselaw.similar / caselaw.citations, §5.3, §2).

Fixture graph (tests/fakes/data.py `build_world`): DLHC-2022-1187 relies on SC-2014-0463; DLHC-2021-0420 follows SC-2014-0463; SC-2020-0100
overrules DLHC-2023-0911. SC root of DLHC-2022-1187 is SC-2014-0463 (authority 0.95 for the SC case, 0.71 for the High Court one).

Good-law rule (plan §5.3): a precedent that a later SC judgment or larger bench treats as overruled is FLAGGED and cannot be cited without a
warning; DISTINGUISHED is shown but does not block. `similar_orders` shows reasoning, never grant rates (plan §1.3, §5.1).
"""

from __future__ import annotations

import pytest

from tests.unit.tools_case._helpers import assert_tool_error, install_recording_stores, stores_touched
from vakeel_sahayak.schemas.enums import AgentName, GoodLawStatus, StoreName, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge, FactSignature, SimilarOrderRow
from vakeel_sahayak.tools.caselaw.citations import CITATIONS_SPEC, GOOD_LAW_CHECK_SPEC, citations, good_law_check
from vakeel_sahayak.tools.caselaw.similar import SIMILAR_ORDERS_SPEC, similar_orders
from vakeel_sahayak.tools.types import GoodLawResult

BEFORE = "2025-02-03"
FACTS = "Cheating under Section 318(4) BNS; charge sheet filed; co-accused granted bail."


# ---------------------------------------------------------------- similar_orders
def test_similar_orders_returns_signature_rows_before_the_date(world, monkeypatch):
    opened = install_recording_stores(monkeypatch, world)
    rows = similar_orders(FACTS, before=BEFORE)
    assert rows and all(isinstance(r, SimilarOrderRow) and r.date < BEFORE for r in rows)
    assert {n for n, _ in opened} == {StoreName.CASELAW_SIMILAR}


def test_similar_orders_ranks_by_the_fact_signature(world, install_stores):
    """A signature with IPC 420 ranks the order whose signature lists IPC 420 first."""
    install_stores()
    sig = FactSignature(sections=["IPC 420"], charge_sheet_status="filed")
    assert similar_orders(FACTS, signature=sig, before=BEFORE)[0].doc_id == "DLHC-2022-1187"


def test_similar_orders_requires_before(world, install_stores):
    """Plan §2 leakage rule applies to this shared store too."""
    install_stores()
    assert_tool_error(lambda: similar_orders(FACTS))


@pytest.mark.parametrize("kwargs", [{"k": 0}, {"k": -1}, {"facts_text": ""}, {"before": "05-02-2025"}])
def test_similar_orders_rejects_bad_arguments(world, install_stores, kwargs):
    install_stores()
    args = {"facts_text": FACTS, "before": BEFORE, **kwargs}
    assert_tool_error(lambda: similar_orders(**args))


def test_similar_orders_never_returns_grant_rates(world, install_stores):
    """'Shows reasoning, never grant rates': neither the row model nor the returned rows carry a rate, probability or outcome count."""
    install_stores()
    banned = ("rate", "probab", "prediction", "likel", "success")
    for name in SimilarOrderRow.model_fields:
        assert not any(b in name.lower() for b in banned), name
    rows = similar_orders(FACTS, before=BEFORE)
    assert not any(b in str(r.model_dump()).lower() for r in rows for b in banned)


def test_similar_orders_respects_k(world, install_stores):
    install_stores()
    assert len(similar_orders(FACTS, before=BEFORE, k=1)) <= 1


def test_similar_orders_reads_only_its_store(world, install_stores):
    install_stores()
    similar_orders(FACTS, before=BEFORE)
    assert stores_touched(world) == {StoreName.CASELAW_SIMILAR}
    assert SIMILAR_ORDERS_SPEC.stores == [StoreName.CASELAW_SIMILAR]


# ---------------------------------------------------------------- citations
def test_citations_cited_by_and_authority(world, monkeypatch):
    """SC-2014-0463 is cited by the two Delhi HC orders; its authority score is 0.95."""
    opened = install_recording_stores(monkeypatch, world)
    res = citations(["SC-2014-0463"], want=["cited_by", "authority"])
    entry = res["SC-2014-0463"]
    assert {e.citing_doc_id for e in entry["cited_by"]} == {"DLHC-2022-1187", "DLHC-2021-0420"}
    assert entry["authority"] == pytest.approx(0.95)
    assert {n for n, _ in opened} == {StoreName.CASELAW_CITATIONS}


def test_citations_sc_root_of_a_high_court_paragraph(world, install_stores):
    """Plan §5.3 'SC root': from DLHC-2022-1187 the graph leads to SC-2014-0463, so Vakeel can cite both."""
    install_stores()
    assert citations(["DLHC-2022-1187"], want=["sc_root"])["DLHC-2022-1187"]["sc_root"] == "SC-2014-0463"


def test_citations_overruled_by(world, install_stores):
    install_stores()
    entry = citations(["DLHC-2023-0911"], want=["overruled_by"])["DLHC-2023-0911"]
    assert "SC-2020-0100" in str(entry["overruled_by"])


def test_citations_with_no_want_returns_the_full_record_per_document(world, install_stores):
    install_stores()
    res = citations(["SC-2014-0463", "DLHC-2022-1187"])
    assert set(res) == {"SC-2014-0463", "DLHC-2022-1187"}
    assert all({"cited_by", "sc_root", "authority"} <= set(v) for v in res.values())


def test_citations_only_returns_the_requested_keys(world, install_stores):
    install_stores()
    assert set(citations(["SC-2014-0463"], want=["sc_root"])["SC-2014-0463"]) == {"sc_root"}


@pytest.mark.parametrize("args", [{"doc_ids": []}, {"doc_ids": ["SC-2014-0463"], "want": ["grant_rate"]}, {"doc_ids": [""]}])
def test_citations_rejects_bad_arguments(world, install_stores, args):
    install_stores()
    assert_tool_error(lambda: citations(**args))


def test_citations_has_no_before_date_it_reads_a_graph_of_decided_cases(world, install_stores):
    """Graph lookups are keyed by document id (the ids came from before-filtered searches), so the tool takes no `before`."""
    import inspect

    assert "before" not in inspect.signature(citations).parameters
    assert CITATIONS_SPEC.agents == [AgentName.SUTRADHAR, AgentName.VAKEEL]


# ---------------------------------------------------------------- good_law_check
def test_an_overruled_precedent_is_flagged_with_the_overruling_judgment(world, monkeypatch):
    """DLHC-2023-0911 is treated as overruled by SC-2020-0100: status OVERRULED and the overruling case is named."""
    opened = install_recording_stores(monkeypatch, world)
    res = good_law_check("DLHC-2023-0911")
    assert isinstance(res, GoodLawResult) and res.status == GoodLawStatus.OVERRULED and res.overruled_by == "SC-2020-0100"
    assert {n for n, _ in opened} == {StoreName.CASELAW_CITATIONS}


def test_a_followed_precedent_is_ok_and_carries_its_sc_root(world, install_stores):
    install_stores()
    res = good_law_check("DLHC-2022-1187")
    assert res.status == GoodLawStatus.OK and res.sc_root == "SC-2014-0463" and res.overruled_by is None


def test_distinguished_is_shown_but_does_not_block(world, install_stores):
    """Plan §5.3: 'Distinguished is shown but does not block': the status is DISTINGUISHED (not OVERRULED) and nothing overrules it."""
    world.stores[StoreName.CASELAW_CITATIONS].edges.append(
        CitationEdge(citing_doc_id="DLHC-2024-0777", cited_doc_id="BOMHC-2024-0355", treatment=Treatment.DISTINGUISHED))
    install_stores()
    res = good_law_check("BOMHC-2024-0355")
    assert res.status == GoodLawStatus.DISTINGUISHED and res.overruled_by is None


def test_overruled_wins_over_distinguished(world, install_stores):
    """A precedent both distinguished and overruled is OVERRULED (the blocking status dominates)."""
    cites = world.stores[StoreName.CASELAW_CITATIONS]
    cites.edges.append(CitationEdge(citing_doc_id="DLHC-2024-0777", cited_doc_id="DLHC-2023-0911", treatment=Treatment.DISTINGUISHED))
    install_stores()
    assert good_law_check("DLHC-2023-0911").status == GoodLawStatus.OVERRULED


@pytest.mark.parametrize("kwargs", [{"doc_id": ""}, {"doc_id": "DLHC-2022-1187", "as_of": "03/02/2025"}, {"doc_id": "DLHC-2022-1187", "as_of": "soon"}])
def test_good_law_check_rejects_bad_arguments(world, install_stores, kwargs):
    install_stores()
    assert_tool_error(lambda: good_law_check(**kwargs))


def test_good_law_check_reads_only_the_citation_store(world, install_stores):
    install_stores()
    good_law_check("DLHC-2023-0911", as_of=BEFORE)
    assert stores_touched(world) == {StoreName.CASELAW_CITATIONS}
    assert GOOD_LAW_CHECK_SPEC.stores == [StoreName.CASELAW_CITATIONS]
