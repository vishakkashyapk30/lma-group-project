"""User flow 1 (plan §13.6): a new case from a messy bundle, up to Gate 1.

Counsel drops in one 14-page PDF (a scanned Hindi FIR, two remand orders, the Sessions Court bail rejection with the order sheet).
Munshi splits and labels it and asks about the unreadable page; Peshkar builds the dossier, the List of Dates and the Rights
Radar; counsel fixes the red fields and approves (Gate 1).

Real modules: MunshiAgent, PeshkarAgent, BaseAgent, the SQLite event log, GateGuard, the FastAPI app. Fakes: models, page back-ends and
the in-memory stores (`tests/system/_helpers.Scenario`). No GPU. The `models` variant at the end reads a real PDF with the real laptop
models.

ASSUMPTIONS: a PageRoute's `route` entries start with the route name ('text_layer', 'ocr', 'vision'); the upload route starts intake
and the dossier build, and the work is finished when the response returns (TestClient runs background tasks); a gate checklist names
dossier fields by their field name; `PATCH /dossier/{field}` is how counsel fixes a red field.
"""

from __future__ import annotations

import pytest

from tests.fakes.toolbox import leaked_names
from tests.system import _helpers as sh
from vakeel_sahayak.schemas.enums import AgentName, EventKind, FieldStatus, PageStatus, RightsCheckName, RightsStatus, Stage

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G1, G2 = sh.G1, sh.G2


def after_intake(tmp_path, monkeypatch) -> sh.Scenario:
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    sc.add_upload("bundle_1.pdf")
    sc.run(AgentName.MUNSHI)
    return sc


def after_dossier(tmp_path, monkeypatch) -> sh.Scenario:
    sc = after_intake(tmp_path, monkeypatch)
    sc.run(AgentName.PESHKAR)
    return sc


def routes(sc: sh.Scenario) -> dict[int, object]:
    return {r.page: r for d in sc.state.ingestion.documents for r in d.page_routes}


# ---- step 1-2: Munshi splits and labels the bundle ------------------------------------------------------------------
def test_munshi_splits_the_14_pages_into_four_labelled_documents(tmp_path, monkeypatch):
    """FIR (p.1-4, Hindi), remand order (p.5-7), remand order (p.8-10), bail rejection with order sheet (p.11-14)."""
    report = after_intake(tmp_path, monkeypatch).state.ingestion
    assert [(d.type, d.pages, d.lang) for d in report.documents] == sh.EXPECTED_BUNDLE_DOCS
    assert report.case_id == CASE


def test_each_page_shows_the_route_that_read_it(tmp_path, monkeypatch):
    """Route badges: the Hindi FIR was OCR'd, its handwritten page went to the vision model, born-digital orders used the text layer."""
    by_page = routes(after_intake(tmp_path, monkeypatch))
    assert by_page[1].route[0].startswith("ocr")
    assert any(step.startswith("vision") for step in by_page[2].route)
    assert all(by_page[p].route[0].startswith("text_layer") for p in range(5, 15))


def test_the_unreadable_page_is_marked_and_counsel_is_asked_about_it(tmp_path, monkeypatch):
    """Page 3 gives no text on any route: status UNREADABLE, and one question names it (plan §4.6)."""
    sc = after_intake(tmp_path, monkeypatch)
    assert routes(sc)[3].status == PageStatus.UNREADABLE
    assert all(r.status == PageStatus.OK for p, r in routes(sc).items() if p != 3)
    asked = [q for q in sc.state.ingestion.questions if "unreadable" in q.lower()]
    assert len(asked) == 1 and "3" in asked[0]


def test_the_report_lists_what_was_filed_and_what_is_missing(tmp_path, monkeypatch):
    """No custody certificate and no antecedents in the bundle: they are gaps, not guesses (plan §4.3 step 4)."""
    report = after_intake(tmp_path, monkeypatch).state.ingestion
    assert report.filed.timeline_events > 0 and report.filed.chunks > 0
    gaps = " ".join(g.item.lower() for g in report.gaps)
    assert "custody certificate" in gaps


def test_intake_stays_on_the_laptop_and_files_only_pseudonymised_text(tmp_path, monkeypatch, planted_names):
    """Plan §16: nothing reaches an Ada-bound client during intake, and the case shelf holds no planted name."""
    sc = after_intake(tmp_path, monkeypatch)
    assert sc.ada_prompts == []
    assert leaked_names([sh.stores_text(sc.world, shared=False)], planted_names) == []
    # RECONCILED: Munshi reads raw client files from the case's inbox folder (MunshiAgent._inbox); the raw file stays there, on the laptop
    assert (sc.data_dir / "cases" / CASE / "inbox" / "bundle_1.pdf").exists()


def test_every_munshi_tool_call_is_an_event_pair(tmp_path, monkeypatch):
    """Plan §3.3: TOOL_CALL then TOOL_RESULT for every call, by MUNSHI; the first gate is not open yet."""
    sc = after_intake(tmp_path, monkeypatch)
    calls, results = sc.events(EventKind.TOOL_CALL), sc.events(EventKind.TOOL_RESULT)
    assert calls and len(calls) == len(results)
    assert {sh._actor(e) for e in calls} == {AgentName.MUNSHI.value}
    assert sc.events(EventKind.GATE_OPENED) == []


# ---- step 3: Peshkar builds the dossier, the List of Dates and the radar -------------------------------------------------
def test_peshkar_builds_the_dossier_from_the_shelf(tmp_path, monkeypatch):
    """The fields of case-0007, each with its status: dates VERIFIED, custody days COMPUTED, antecedents UNSUPPORTED (red)."""
    f = after_dossier(tmp_path, monkeypatch).state.dossier.fields
    assert (f.arrest_date.value, f.arrest_date.status) == ("2024-08-20", FieldStatus.VERIFIED)
    assert f.first_remand.value == "2024-08-21"
    assert (f.custody_days.value, f.custody_days.status) == (167, FieldStatus.COMPUTED)
    assert f.charge_sheet.value.filed is True and f.charge_sheet.value.date == "2024-11-02"
    assert f.antecedents.status == FieldStatus.UNSUPPORTED and f.antecedents.value is None


def test_every_verified_field_points_at_a_source_box(tmp_path, monkeypatch):
    """Plan §7.1: {value, source, status}; a VERIFIED value has a document and page, a COMPUTED one names its tool."""
    f = after_dossier(tmp_path, monkeypatch).state.dossier.fields
    for name in type(f).model_fields:
        tracked = getattr(f, name)
        if tracked.status == FieldStatus.VERIFIED:
            assert tracked.source is not None and tracked.source.doc and tracked.source.page, name
        if tracked.status == FieldStatus.COMPUTED:
            assert tracked.source is not None and tracked.source.tool, name


def test_hindi_quotes_keep_the_original_and_the_translation(tmp_path, monkeypatch):
    """Plan §4.5: the FIR value carries the Hindi quote and its English translation; counsel sees the original."""
    src = after_dossier(tmp_path, monkeypatch).state.dossier.fields.fir.source
    assert src.lang == "hi" and "112/2024" in src.quote and src.quote_en and "112/2024" in src.quote_en
    assert any("ऀ" <= c <= "ॿ" for c in src.quote)  # Devanagari original, not an image


def test_list_of_dates_is_sorted_and_every_entry_has_a_source(tmp_path, monkeypatch):
    events = after_dossier(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/dates").json()
    assert [e["date"] for e in events] == sorted(e["date"] for e in events)
    assert {"2024-08-20", "2024-08-21", "2024-11-02"} <= {e["date"] for e in events}
    assert all(e["source"] and e["source"].get("doc") for e in events)


def test_the_rights_radar_raises_its_flags(tmp_path, monkeypatch):
    """Plan §7.3 worked example: default bail WINDOW_CLOSED (charge sheet on day 74), s.479 CHECK because antecedents are unknown."""
    rights = after_dossier(tmp_path, monkeypatch).state.rights
    status = {c.check: c.status for c in rights.checks}
    assert status[RightsCheckName.DEFAULT_BAIL] == RightsStatus.WINDOW_CLOSED
    assert status[RightsCheckName.UNDERTRIAL_LIMIT] == RightsStatus.CHECK
    assert status[RightsCheckName.STATUTORY_BAR] == RightsStatus.NOT_APPLICABLE
    assert all(c.rule for c in rights.checks)  # every entitlement carries its rule text


def test_the_radar_matches_the_plan_7_3_worked_example_exactly(tmp_path, monkeypatch, case_meta):
    """All seven checks of plan §7.3, status by status (the expected map is built by construction in tests/fixtures/case_0007)."""
    rights = after_dossier(tmp_path, monkeypatch).state.rights
    assert {c.check.value: c.status.value for c in rights.checks} == case_meta["expected"]["rights_statuses"]


def test_munshi_asks_few_questions_at_a_time(tmp_path, monkeypatch):
    """Plan §4.3: questions are put to counsel in small batches (at most three), and the unreadable page is asked about once."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), answers=["", "", ""])
    sc.add_upload("bundle_1.pdf")
    sc.run(AgentName.MUNSHI)
    assert all(len(batch) <= 3 for batch in sc.toolbox.questions)
    assert len([q for batch in sc.toolbox.questions for q in batch if "page 3" in q.lower()]) == 1


def test_peshkar_stops_at_gate_1_and_leaves_the_decision_to_counsel(tmp_path, monkeypatch):
    """The gate is opened and nobody approved it: no GATE_APPROVED event, no brief."""
    sc = after_dossier(tmp_path, monkeypatch)
    assert [e.inputs["gate"] for e in sc.events(EventKind.GATE_OPENED)] == [G1.value]
    assert sc.events(EventKind.GATE_APPROVED) == []
    assert sc.state.brief is None and sc.state.stage in (Stage.DOSSIER, Stage.RIGHTS)


# ---- step 4: counsel fixes the red fields and approves Gate 1 ---------------------------------------------------------
def test_gate_1_checklist_lists_the_red_field(tmp_path, monkeypatch):
    status = after_dossier(tmp_path, monkeypatch).status(G1)
    assert status.open is True and status.unresolved_unsupported == ["antecedents"]


def test_gate_1_cannot_be_approved_with_a_red_field_left(tmp_path, monkeypatch):
    sc = after_dossier(tmp_path, monkeypatch)
    with pytest.raises(sh.REFUSED):
        sc.approve(G1)
    assert sc.events(EventKind.GATE_APPROVED) == []


def test_counsel_acknowledges_the_red_field_and_approves(tmp_path, monkeypatch):
    """The approval is a counsel event with the acknowledged fields and the hash of the approved dossier; no agent approved anything."""
    sc = after_dossier(tmp_path, monkeypatch)
    sc.approve(G1, acknowledged=["antecedents"])
    (ev,) = sc.events(EventKind.GATE_APPROVED)
    assert sh._actor(ev).lower() == "counsel" and ev.inputs["acknowledged"] == ["antecedents"]
    assert str(ev.outputs["dossier_hash"]).startswith("h:")
    assert sh.agent_approvals(sc.events()) == [] and sc.status(G1).open is False


def test_counsel_can_fix_the_field_instead_of_acknowledging_it(tmp_path, monkeypatch):
    """'Counsel fixes the red fields': editing antecedents over the API makes it USER_EDITED and clears the checklist."""
    sc = after_dossier(tmp_path, monkeypatch)
    client = sc.client()
    res = client.patch(f"/api/cases/{CASE}/dossier/antecedents", json={"value": []})
    assert res.status_code == 200 and res.json()["fields"]["antecedents"]["status"] == FieldStatus.USER_EDITED.value
    assert client.get(f"/api/cases/{CASE}/gates/{G1.value}").json()["unresolved_unsupported"] == []
    assert client.post(f"/api/cases/{CASE}/gates/{G1.value}/approve", json={"acknowledged_fields": []}).status_code == 200


def test_nothing_after_gate_1_runs_before_counsel_approves(tmp_path, monkeypatch):
    """Drafting is refused until Gate 1 is approved (plan §3.1), and export is refused too."""
    sc = after_dossier(tmp_path, monkeypatch)
    client = sc.client()
    assert client.post(f"/api/cases/{CASE}/draft").status_code == sh.HTTP_CHECKLIST_OPEN
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).status_code == sh.HTTP_EXPORT_REFUSED
    assert sc.toolbox.exports == [] and sc.ada_prompts == []


# ---- the same flow through the HTTP API ---------------------------------------------------------------------------------
def test_the_whole_flow_over_http(tmp_path, monkeypatch):
    """Upload -> ingestion report -> dossier -> checklist -> approval, as the workspace does it (plan §13.5)."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    client = sc.client()
    up = client.post(f"/api/cases/{CASE}/upload", files=[("files", ("bundle_1.pdf", b"%PDF-1.4\n% stub\n", "application/pdf"))])
    assert up.status_code == 200 and up.json()["accepted"] == ["bundle_1.pdf"]
    report = client.get(f"/api/cases/{CASE}/ingestion").json()
    assert [(d["type"], d["pages"]) for d in report["documents"]] == [(t.value, p) for t, p, _ in sh.EXPECTED_BUNDLE_DOCS]
    fields = client.get(f"/api/cases/{CASE}/dossier").json()["fields"]  # ASSUMPTION: upload also runs Peshkar up to Gate 1
    assert fields["arrest_date"]["value"] == "2024-08-20"
    gate = client.get(f"/api/cases/{CASE}/gates/{G1.value}").json()
    assert gate["open"] is True and gate["unresolved_unsupported"] == ["antecedents"]
    refused = client.post(f"/api/cases/{CASE}/gates/{G1.value}/approve", json={"acknowledged_fields": []})
    assert refused.status_code == sh.HTTP_CHECKLIST_OPEN
    ok = client.post(f"/api/cases/{CASE}/gates/{G1.value}/approve", json={"acknowledged_fields": ["antecedents"]})
    assert ok.status_code == 200 and ok.json()["open"] is False
    assert sh.agent_approvals(sc.events()) == []


# ---- real laptop models (laptop or Ada only) --------------------------------------------------------------------------------
@pytest.mark.models
def test_real_models_split_a_real_three_document_pdf(tmp_path, monkeypatch, require_pymupdf, pdfs):
    """The real laptop models and tools (text layer, layout, the 4B Munshi) on a constructed born-digital bundle: three documents."""
    pages = [sh.pdfgen.REMAND_PAGE, sh.pdfgen.BAIL_ORDER_PAGE, sh.pdfgen.ORDER_SHEET_PAGE]
    sc = sh.Scenario(tmp_path, monkeypatch, real_models=True)
    sc.add_upload("bundle_1.pdf", pdfs.text("bundle_1.pdf", pages).read_bytes())
    state = sc.run(AgentName.MUNSHI)
    assert len(state.ingestion.documents) >= 2
    assert {d.type.value for d in state.ingestion.documents} & {"REMAND_ORDER", "BAIL_ORDER", "ORDER_SHEET"}
    assert sc.ada_prompts == []


def test_gate_2_is_not_reachable_from_intake(tmp_path, monkeypatch):
    """Gate 2 stays closed in flow 1: no brief means no Gate 2 checklist to clear, and Gate 1 alone unlocks no export."""
    sc = after_dossier(tmp_path, monkeypatch)
    sc.approve(G1, acknowledged=["antecedents"])
    with pytest.raises(sh.REFUSED):
        sc.approve(G2)
    assert sc.events(EventKind.GATE_APPROVED, actor="counsel")[-1].inputs["gate"] == G1.value
