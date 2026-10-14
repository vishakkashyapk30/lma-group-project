"""User flow 7 (plan §13.6, §5.3, §5.4, §13.5 `/library`): the library. Counsel explores precedents, with good-law badges and the IPC <-> BNS
bridge with its text diff.

Real modules: the library routes over the stores (search, citation graph, concordance) and, for the consistency check, the brief that
Vakeel drafts from the same stores. Fakes: the in-memory stores of case-0007 (`tests/fakes/stores.py`), wired by `Scenario`.

World facts: DLHC-2022-1187 relies on SC-2014-0463 (its SC root); DLHC-2021-0420 follows it; DLHC-2023-0911 is overruled by SC-2020-0100;
IPC 420 -> BNS 318(4) is REWORDED (a precedent under IPC 420 is CHANGED), IPC 406 -> BNS 316(2) is SAME, IPC 999 splits into BNS 888(1) and
888(2), CrPC 439 -> BNSS 483. Response keys follow tests/unit/api/test_library_router.py.
"""

from __future__ import annotations

import json
import re

import pytest

from tests.system import _helpers as sh
from vakeel_sahayak.schemas.enums import EventKind, StoreName

pytestmark = pytest.mark.system

FORBIDDEN = {"TESTORD-2024-0001", "SAMEFIR-2024-0002"}


def library(tmp_path, monkeypatch):
    sc = sh.Scenario(tmp_path, monkeypatch)
    return sc, sc.client()


# ---- the precedent search ------------------------------------------------------------------------------------------------
def test_search_returns_reasoning_paragraphs_best_match_first(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    hits = client.get("/api/library/search", params={"q": "parity co-accused bail"}).json()
    assert hits and hits[0]["doc_id"] == "DLHC-2022-1187" and hits[0]["para"] == 14
    assert all(h["part"] == "reasoning" for h in hits)


def test_search_never_returns_test_or_same_fir_orders_and_always_has_a_before_date(tmp_path, monkeypatch):
    """Leakage (plan §2): the excluded orders are in no result, and every store query carries a before date."""
    sc, client = library(tmp_path, monkeypatch)
    hits = client.get("/api/library/search", params={"q": "bail"}).json()
    assert not {h["doc_id"] for h in hits} & FORBIDDEN
    calls = sc.world.stores[StoreName.CASELAW_REASONING].calls
    assert calls and all(kw["before"] for _, kw in calls)


# ---- good-law badges ----------------------------------------------------------------------------------------------------
def test_a_good_precedent_has_an_ok_badge_and_followers(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    body = client.get("/api/library/citations/SC-2014-0463").json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert nodes["SC-2014-0463"]["good_law"] == "OK" and {"DLHC-2022-1187", "DLHC-2021-0420"} <= set(nodes)
    assert {(e["source"], e["target"], e["treatment"]) for e in body["edges"]} >= {
        ("DLHC-2022-1187", "SC-2014-0463", "RELIED_ON"), ("DLHC-2021-0420", "SC-2014-0463", "FOLLOWED")}


def test_an_overruled_precedent_says_so_and_names_the_overruling_judgment(tmp_path, monkeypatch):
    """Plan §5.3: DLHC-2023-0911 is overruled by SC-2020-0100."""
    _, client = library(tmp_path, monkeypatch)
    node = next(n for n in client.get("/api/library/citations/DLHC-2023-0911").json()["nodes"] if n["id"] == "DLHC-2023-0911")
    assert node["good_law"] == "OVERRULED" and node["overruled_by"] == "SC-2020-0100"


def test_the_graph_leads_from_a_high_court_order_to_its_sc_root(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    assert client.get("/api/library/citations/DLHC-2022-1187").json()["root"] == "SC-2014-0463"


def test_the_badges_agree_with_the_authorities_in_a_drafted_brief(tmp_path, monkeypatch):
    """What the explorer shows is what Vakeel cites: every authority of the drafted brief has the good-law badge of the library."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    sc.through_gate1()
    sc.through_draft()
    client = sc.client()
    authorities = [a for g in sc.state.brief.grounds for a in g.authorities]
    assert authorities
    for a in authorities:
        node = next(n for n in client.get(f"/api/library/citations/{a.doc_id}").json()["nodes"] if n["id"] == a.doc_id)
        assert a.good_law.value == node["good_law"] != "OVERRULED", a.doc_id


# ---- the bridge ------------------------------------------------------------------------------------------------------------
def test_ipc_420_maps_to_bns_318_4_with_a_text_diff_and_is_changed(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    body = client.get("/api/library/bridge/IPC/420").json()
    assert (body["old_ref"], body["new_ref"], body["edge_type"], body["transfer"]) == ("IPC 420", "BNS 318(4)", "REWORDED", "CHANGED")
    assert body["text_diff"] and "dishonestly" in body["text_diff"] and body["ambiguous"] is False


def test_the_bridge_works_from_the_new_code_too(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    body = client.get("/api/library/bridge/BNS/318(4)").json()
    assert (body["old_ref"], body["new_ref"]) == ("IPC 420", "BNS 318(4)")


def test_a_same_text_provision_carries_over_unchanged(tmp_path, monkeypatch):
    body = library(tmp_path, monkeypatch)[1].get("/api/library/bridge/IPC/406").json()
    assert body["edge_type"] == "SAME" and body["transfer"] == "SAME_TEXT"


def test_a_split_provision_lists_its_candidates_and_does_not_guess(tmp_path, monkeypatch):
    body = library(tmp_path, monkeypatch)[1].get("/api/library/bridge/IPC/999").json()
    assert body["ambiguous"] is True and body["new_ref"] in (None, "") and set(body["candidates"]) == {"BNS 888(1)", "BNS 888(2)"}


def test_the_bail_table_is_bridged_too(tmp_path, monkeypatch):
    assert library(tmp_path, monkeypatch)[1].get("/api/library/bridge/CrPC/439").json()["new_ref"] == "BNSS 483"


def test_an_unknown_section_or_order_is_a_404(tmp_path, monkeypatch):
    _, client = library(tmp_path, monkeypatch)
    assert client.get("/api/library/bridge/IPC/12345").status_code == 404
    assert client.get("/api/library/citations/NOPE-0000-0000").status_code == 404


def test_the_bridge_agrees_with_the_chat_answer_for_the_same_section(tmp_path, monkeypatch):
    """Counsel gets the same mapping from the library and from the chat ('BNS equivalent of 420 IPC?')."""
    sc = sh.Scenario(tmp_path, monkeypatch, ada=sh.ada_client(chat=[("equivalent", sh.prompt_must_contain("BNS 318(4) [map_section]", "318(4)"))]))
    sc.with_case_state()
    bridge = sc.client().get("/api/library/bridge/IPC/420").json()["new_ref"]
    assert bridge in sc.chat("BNS equivalent of 420 IPC?").text


# ---- the library is read-only and shows no rates ---------------------------------------------------------------------------
def test_no_response_shows_a_grant_rate_or_a_probability(tmp_path, monkeypatch):
    """The similar-facts store shows reasoning, never rates (plan §1.3, §16)."""
    _, client = library(tmp_path, monkeypatch)
    blob = json.dumps([client.get("/api/library/search", params={"q": "bail"}).json(),
                       client.get("/api/library/citations/SC-2014-0463").json(),
                       client.get("/api/library/bridge/IPC/420").json()]).lower()
    assert not re.search(r"grant[ _]rate", blob) and not sh.PROBABILITY_RE.search(blob)


def test_browsing_the_library_writes_nothing_and_exports_nothing(tmp_path, monkeypatch):
    sc, client = library(tmp_path, monkeypatch)
    client.get("/api/library/search", params={"q": "parity"})
    client.get("/api/library/citations/SC-2014-0463")
    client.get("/api/library/bridge/IPC/420")
    assert sc.events(EventKind.STORE_WRITE) == [] and sc.events(EventKind.GATE_APPROVED) == []
    assert sc.toolbox.exports == [] and sc.ada_prompts == []
