"""Router `library` (plan §5.3, §5.4, §13.5 `/library`, flow 7): the precedent explorer. Search reasoning paragraphs, the
citation graph with good-law badges, the IPC <-> BNS bridge with a text diff.

The stores are the in-memory fakes of case-0007 (tests/fakes/stores.py), wired by `Scenario`.
ASSUMPTIONS (response keys are not fixed by the plan): citations: `{root, nodes: [{id, authority, good_law, overruled_by}],
edges: [{source, target, treatment}]}`; bridge: `{old_ref, new_ref, edge_type, text_diff, transfer, ambiguous, candidates}`;
an unknown section is a 404.
"""

from __future__ import annotations

from tests.unit.api._helpers import INVALID, NOT_FOUND, scenario
from vakeel_sahayak.schemas.enums import StoreName

FORBIDDEN = {"TESTORD-2024-0001", "SAMEFIR-2024-0002"}


def test_search_returns_reasoning_paragraphs_only(tmp_path, monkeypatch):
    """Search over `caselaw.reasoning`: every hit is a court's reasoning paragraph (plan §5.2: authorities from reasoning only)."""
    rows = scenario(tmp_path, monkeypatch).client().get("/api/library/search", params={"q": "parity co-accused bail"}).json()
    assert rows and all(r["part"] == "reasoning" for r in rows)
    assert {"doc_id", "para", "court", "date", "text"} <= set(rows[0])


def test_search_never_returns_test_or_same_fir_orders(tmp_path, monkeypatch):
    """Leakage (plan §2): the excluded orders are in no result."""
    rows = scenario(tmp_path, monkeypatch).client().get("/api/library/search", params={"q": "bail"}).json()
    assert not {r["doc_id"] for r in rows} & FORBIDDEN


def test_search_always_passes_a_before_date_to_the_store(tmp_path, monkeypatch):
    """Every shared-store query carries a before date, also from the library (plan §2)."""
    sc = scenario(tmp_path, monkeypatch)
    sc.client().get("/api/library/search", params={"q": "parity"})
    calls = sc.world.stores[StoreName.CASELAW_REASONING].calls
    assert calls and all(kw["before"] for _, kw in calls)


def test_search_ranks_the_matching_paragraph_first(tmp_path, monkeypatch):
    rows = scenario(tmp_path, monkeypatch).client().get("/api/library/search", params={"q": "co-accused granted bail parity"}).json()
    assert rows[0]["doc_id"] == "DLHC-2022-1187" and rows[0]["para"] == 14


def test_search_needs_a_query(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().get("/api/library/search").status_code == INVALID


def test_search_results_carry_no_grant_rates(tmp_path, monkeypatch):
    """The explorer shows reasoning, never rates (plan §1.3, §16)."""
    text = scenario(tmp_path, monkeypatch).client().get("/api/library/search", params={"q": "bail"}).text.lower()
    assert "grant_rate" not in text and "grant rate" not in text


# ---- citation graph ----------------------------------------------------------------------------------------------
def test_citation_graph_has_nodes_edges_and_a_good_law_badge(tmp_path, monkeypatch):
    """SC-2014-0463 is relied on and followed by two High Court orders; its badge is OK."""
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/citations/SC-2014-0463").json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert nodes["SC-2014-0463"]["good_law"] == "OK"
    assert {"DLHC-2022-1187", "DLHC-2021-0420"} <= set(nodes)
    assert {(e["source"], e["target"], e["treatment"]) for e in body["edges"]} >= {
        ("DLHC-2022-1187", "SC-2014-0463", "RELIED_ON"), ("DLHC-2021-0420", "SC-2014-0463", "FOLLOWED")}


def test_overruled_precedent_shows_an_overruled_badge_and_the_overruling_judgment(tmp_path, monkeypatch):
    """Plan §5.3: DLHC-2023-0911 is overruled by SC-2020-0100; the explorer says so and names the judgment."""
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/citations/DLHC-2023-0911").json()
    node = next(n for n in body["nodes"] if n["id"] == "DLHC-2023-0911")
    assert node["good_law"] == "OVERRULED" and node["overruled_by"] == "SC-2020-0100"


def test_high_court_order_shows_its_sc_root(tmp_path, monkeypatch):
    """The graph leads from a High Court paragraph to the SC judgment it relies on (plan §5.3 'SC root')."""
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/citations/DLHC-2022-1187").json()
    assert body["root"] == "SC-2014-0463"


def test_citation_graph_of_unknown_order_is_404(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().get("/api/library/citations/NOPE-0000-0000").status_code == NOT_FOUND


# ---- the IPC <-> BNS bridge --------------------------------------------------------------------------------------
def test_bridge_ipc_420_to_bns_318_4_with_a_text_diff(tmp_path, monkeypatch):
    """The worked example: IPC 420 -> BNS 318(4), REWORDED, so a precedent under IPC 420 is CHANGED (plan §5.4)."""
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/IPC/420").json()
    assert (body["old_ref"], body["new_ref"], body["edge_type"]) == ("IPC 420", "BNS 318(4)", "REWORDED")
    assert body["text_diff"] and body["transfer"] == "CHANGED"
    assert body["ambiguous"] is False


def test_bridge_works_from_the_new_code_too(tmp_path, monkeypatch):
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/BNS/318(4)").json()
    assert body["old_ref"] == "IPC 420" and body["new_ref"] == "BNS 318(4)"


def test_bridge_same_text_provision(tmp_path, monkeypatch):
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/IPC/406").json()
    assert body["edge_type"] == "SAME" and body["transfer"] == "SAME_TEXT"


def test_bridge_of_a_split_provision_lists_candidates_and_does_not_guess(tmp_path, monkeypatch):
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/IPC/999").json()
    assert body["ambiguous"] is True and body["new_ref"] in (None, "")
    assert set(body["candidates"]) == {"BNS 888(1)", "BNS 888(2)"}


def test_bridge_covers_the_bail_table(tmp_path, monkeypatch):
    """CrPC 439 -> BNSS 483 (plan §2 bail table)."""
    body = scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/CrPC/439").json()
    assert body["new_ref"] == "BNSS 483"


def test_bridge_of_unknown_section_is_404(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().get("/api/library/bridge/IPC/12345").status_code == NOT_FOUND
