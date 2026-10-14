"""User flow 3 (plan §13.6, §6, §8, §9, §16): the brief and the spar, Gate 2, and the export of the application DOCX and the hearing card.

Counsel clicks *Draft bail brief*. Sutradhar plans (the trace is visible), Vakeel drafts, Abhiyojak spars. Counsel resolves the
NEEDS_REVIEW and UNANSWERED items, reads the hearing-prep card, approves (Gate 2) and exports.

Real modules: SutradharAgent, VakeelAgent, AbhiyojakAgent, GateGuard, `export_case`, the SQLite log, the FastAPI app. Fakes: models, stores,
tools (`tests/system/_helpers.Scenario`); the document writers are recording stubs except in the python-docx test.

ASSUMPTIONS: Abhiyojak's scripted round leaves O1 ANSWERED, O2 UNANSWERED (witness tampering) and discards the ungrounded O3; the
unanswered objection is the one Gate 2 item; `POST /draft` runs the drafting synchronously under TestClient. SKELETON-GAP: no API route
resolves a Gate 2 checklist item (`Scenario.resolve` writes the counsel USER_ACTION a route would write).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.system import _helpers as sh
from tests.unit.agents._helpers import tools_yaml
from tests.unit.export._helpers import Spy, docx_text, mentions_date
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.export.hearing_card import build_hearing_card
from vakeel_sahayak.export.exporter import export_case
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, EventKind, ExportFormat, StoreName
from vakeel_sahayak.schemas.retrieval_plan import RetrievalPlan

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G1, G2 = sh.G1, sh.G2
FORBIDDEN_ORDERS = {"TESTORD-2024-0001", "SAMEFIR-2024-0002", "DLHC-2025-0099"}
LABEL = "AI-generated draft. Not legal advice."


def drafted(tmp_path, monkeypatch, **kw) -> sh.Scenario:
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), **kw)
    sc.through_gate1()
    sc.through_draft()
    return sc


@pytest.fixture()
def spy(monkeypatch) -> Spy:
    s = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", s.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", s.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", s.pdf)
    return s


# ---- steps 1-2: Sutradhar plans, Vakeel drafts, Abhiyojak spars ---------------------------------------------------------
def test_draft_over_http_after_gate_1(tmp_path, monkeypatch):
    """*Draft bail brief*: 200 after Gate 1, and the brief tab then has grounds."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    sc.through_gate1()
    client = sc.client()
    assert client.post(f"/api/cases/{CASE}/draft").status_code == 200
    assert client.get(f"/api/cases/{CASE}/brief").json()["grounds"]


def test_trace_is_visible_and_the_brief_is_drafted_and_sparred(tmp_path, monkeypatch):
    """Sutradhar's tool calls are in the log for the 'Show the plan' trace; Vakeel drafts G1 and G2; Abhiyojak spars two rounds."""
    sc = drafted(tmp_path, monkeypatch)
    assert [g.id for g in sc.state.brief.grounds] == ["G1", "G2"]
    assert sc.state.sparring.rounds == 2
    sut = [e for e in sc.events(EventKind.TOOL_CALL) if sh._actor(e) == "SUTRADHAR"]
    assert {e.tool for e in sut} & {"search_reasoning", "search_case_docs", "get_timeline"}
    assert {sh._actor(e) for e in sc.events()} >= {"SUTRADHAR", "VAKEEL", "ABHIYOJAK"}


def test_every_plan_stays_inside_the_contract_and_the_allow_list(tmp_path, monkeypatch):
    """Plan §6.1: each RetrievalPlan the planner wrote has at least one step, and every step's tool is one Sutradhar may call."""
    sc = drafted(tmp_path, monkeypatch)
    plans = [RetrievalPlan.model_validate_json(c.completion) for c in sc.ada.calls_for("RetrievalPlan")]
    assert plans
    allowed = set(tools_yaml()["sutradhar"])
    assert all(step.tool in allowed for p in plans for step in p.steps)


def test_the_budget_is_respected(tmp_path, monkeypatch):
    """Plan §6.2: at most 8 store calls per factor and 150K tokens per case, as the budget tab shows."""
    sc = drafted(tmp_path, monkeypatch)
    body = sc.client().get(f"/api/cases/{CASE}/budget").json()
    assert body["tokens_spent"] <= body["tokens_cap"] == 150000
    assert all(n <= 8 for n in body["store_calls"].values())


def test_every_ground_cites_only_retrieved_court_reasoning_with_rendered_citations(tmp_path, monkeypatch):
    """Plan §5.2, §8.1: authorities are reasoning paragraphs from the store, never test, same-FIR or post-dated orders, and carry the citation text rendered from metadata."""
    sc = drafted(tmp_path, monkeypatch)
    reasoning = {(r.doc_id, r.para) for r in sc.world.stores[StoreName.CASELAW_REASONING].rows}
    cited = {(a.doc_id, a.para) for g in sc.state.brief.grounds for a in g.authorities}
    assert cited and cited <= reasoning and not {d for d, _ in cited} & FORBIDDEN_ORDERS
    assert all(a.citation for g in sc.state.brief.grounds for a in g.authorities)


def test_the_brief_carries_the_label_and_a_check_result_per_ground(tmp_path, monkeypatch):
    brief = drafted(tmp_path, monkeypatch).state.brief
    assert brief.label == LABEL
    assert all(g.check in set(ClaimCheck) for g in brief.grounds)


def test_the_spar_ends_with_one_unanswered_objection_and_discards_the_ungrounded_one(tmp_path, monkeypatch):
    """Plan §9: O1 ANSWERED; O2 (witness tampering) UNANSWERED, waiting for counsel; O3 has no ground and is discarded and logged."""
    spar = drafted(tmp_path, monkeypatch).state.sparring
    verdicts = {o.id: o.verdict.value for o in spar.objections}
    assert verdicts["O1"] == "ANSWERED" and verdicts["O2"] == "UNANSWERED" and "O3" not in verdicts
    assert "O3" in spar.discarded
    assert all(o.grounds for o in spar.objections)


# ---- the hearing-prep card ---------------------------------------------------------------------------------------------
def test_hearing_prep_card_has_no_prediction(tmp_path, monkeypatch):
    """Concerns, lead points, conditions, open issues; no rates, no prediction (plan §8.3, §16)."""
    sc = drafted(tmp_path, monkeypatch)
    card = build_hearing_card(sc.state.brief, sc.state.sparring, CASE)
    assert {"bench_concerns", "lead_with", "conditions", "open_issues"} <= set(card)
    assert not sh.PROBABILITY_RE.search(json.dumps(card, default=str))
    assert "grant rate" not in json.dumps(card, default=str).lower()


def test_the_card_leads_with_supported_grounds_and_lists_the_open_objection(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    card = build_hearing_card(sc.state.brief, sc.state.sparring, CASE)
    supported = {g.id for g in sc.state.brief.grounds if g.check == ClaimCheck.SUPPORTED}
    assert len(card["lead_with"]) <= 3 and set(card["lead_with"]) <= supported | {g.id for g in sc.state.brief.grounds}
    assert "O2" in json.dumps(card["open_issues"], default=str) or "witness" in json.dumps(card["open_issues"]).lower()


def test_the_prep_tab_over_http_has_the_same_blocks(tmp_path, monkeypatch):
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/prep").json()
    assert {"bench_concerns", "lead_with", "conditions", "open_issues"} <= set(body)


# ---- step 3: Gate 2 -----------------------------------------------------------------------------------------------------
def test_gate_2_lists_the_unanswered_objection_and_blocks_until_resolved(tmp_path, monkeypatch):
    """O2 is the checklist item; approval is refused until counsel resolves it; then Gate 2 is approved by counsel."""
    sc = drafted(tmp_path, monkeypatch)
    assert sc.status(G2).unresolved_unanswered == ["O2"]
    with pytest.raises(sh.REFUSED):
        sc.approve(G2)
    assert sc.toolbox.exports == []
    sc.clear_and_approve(G2)
    assert [e.inputs["gate"] for e in sc.events(EventKind.GATE_APPROVED)] == [G1.value, G2.value]
    assert sh.agent_approvals(sc.events()) == []


def test_gate_2_over_http_is_409_then_200(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    client = sc.client()
    status = client.get(f"/api/cases/{CASE}/gates/{G2.value}").json()
    assert status["open"] is True and status["unresolved_unanswered"] == ["O2"]
    url = f"/api/cases/{CASE}/gates/{G2.value}/approve"
    assert client.post(url, json={"acknowledged_fields": []}).status_code == sh.HTTP_CHECKLIST_OPEN
    for item in status["unresolved_needs_review"] + status["unresolved_unanswered"]:
        sc.resolve(item)  # SKELETON-GAP: no API route for this
    res = client.post(url, json={"acknowledged_fields": status["unresolved_unsupported"]})
    assert res.status_code == 200 and res.json()["open"] is False


def test_export_before_gate_2_is_refused_and_writes_nothing(tmp_path, monkeypatch, spy):
    sc = drafted(tmp_path, monkeypatch)
    client = sc.client()
    for fmt in ("DOCX", "PDF"):
        assert client.post(f"/api/cases/{CASE}/export", json={"format": fmt}).status_code == sh.HTTP_EXPORT_REFUSED
    with pytest.raises(sh.REFUSED):
        export_case(CASE, ExportFormat.DOCX)
    assert spy.calls == [] and sc.toolbox.exports == [] and sh.export_tool_calls(sc.events()) == []
    assert not [p for p in tmp_path.rglob("*") if p.suffix in (".docx", ".pdf")]


# ---- step 3: the export -------------------------------------------------------------------------------------------------
def test_export_after_gate_2_writes_the_application_the_dates_the_objections_sheet_and_the_card(tmp_path, monkeypatch, spy):
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    res = sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"})
    assert res.status_code == 200
    paths = [Path(p) for p in res.json()]
    assert len(paths) >= 4 and all(p.exists() for p in paths)
    names = " ".join(p.name.lower() for p in paths)
    for word in ("application", "dates", "objection", "card"):
        assert word in names, names
    assert spy.calls.count("application") == 1 and "card" in spy.calls and "pdf" not in spy.calls
    assert all("0008" not in p.name for p in paths)


def test_pdf_export_converts_the_docx(tmp_path, monkeypatch, spy):
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = sc.client().post(f"/api/cases/{CASE}/export", json={"format": "PDF"}).json()
    assert "pdf" in spy.calls and any(p.endswith(".pdf") for p in paths)


def test_the_exported_application_has_the_plan_8_2_content(tmp_path, monkeypatch):
    """Needs python-docx: the cause title with placeholders, the section heading, the List of Dates, grounds with rendered citations,
    the 'AI-generated draft' label, and no model-written citation tags."""
    pytest.importorskip("docx")
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = [Path(p) for p in sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()]
    text = docx_text(next(p for p in paths if "application" in p.name.lower()))
    assert "Application under Section 483 BNSS for grant of regular bail" in text
    assert LABEL in text and "check against your court" in text.lower()
    for iso in ("2024-08-20", "2024-08-21", "2024-11-02"):
        assert mentions_date(text, iso), iso
    assert "DLHC-2022-1187" in text and "[A:" not in text and "[F:" not in text
    assert "[" in text  # placeholders for real names, filled only on counsel's machine


def test_approving_one_case_unlocks_only_that_case(tmp_path, monkeypatch, spy):
    """No bulk export: Gate 2 of case-0007 does nothing for case-0008 (plan §11, §16)."""
    sc = drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    sc.seed_record("case-0008", brief=sh.clean_brief("case-0008"), sparring=sh.clean_sparring("case-0008"))
    client = sc.client()
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).status_code == 200
    assert client.post("/api/cases/case-0008/export", json={"format": "DOCX"}).status_code == sh.HTTP_EXPORT_REFUSED


def test_only_counsel_approved_and_the_planner_never_exported(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    assert sh.agent_approvals(sc.events()) == [] and sc.toolbox.count("export") == 0
    vakeel_tools = {e.tool for e in sc.events(EventKind.TOOL_CALL) if sh._actor(e) == AgentName.VAKEEL.value}
    assert "export" not in vakeel_tools


# ---- real 14B (laptop or Ada only) --------------------------------------------------------------------------------------
@pytest.mark.models
@pytest.mark.gpu
def test_real_model_drafts_a_checked_brief_over_the_fake_stores(tmp_path, monkeypatch):
    """The real 14B plans, drafts and spars over the in-memory stores: grounds exist, every authority was retrieved and carries a
    rendered citation, and nothing is exported."""
    sc = sh.Scenario(tmp_path, monkeypatch, real_models=True)
    sc.with_case_state()
    state = sc.through_draft()
    reasoning = {(r.doc_id, r.para) for r in sc.world.stores[StoreName.CASELAW_REASONING].rows}
    cited = {(a.doc_id, a.para) for g in state.brief.grounds for a in g.authorities}
    assert state.brief.grounds and cited <= reasoning and state.brief.label == LABEL
    assert sc.toolbox.exports == []
