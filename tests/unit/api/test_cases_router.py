"""Router `cases` (plan §13.1, §13.5): the cause list, one case, the tabs of the workspace.

The tabs are views of the case record: ingestion report, dossier (with counsel's field edits), List of Dates, Rights Radar,
brief, spar record, hearing-prep card, budget. Conventions (404, 409, 422): see `_helpers.py`.
"""

from __future__ import annotations

import re

import pytest

from tests.system import _helpers as sh
from tests.unit.api._helpers import CASE, CHECKLIST_OPEN, NOT_FOUND, scenario, urgent_rights
from vakeel_sahayak.schemas.enums import EventKind, FieldStatus, Stage


def seeded(tmp_path, monkeypatch, **seed):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(**seed)
    return sc, sc.client()


# ---- cause list --------------------------------------------------------------------------------------------------
def test_create_case_returns_a_new_summary_at_the_intake_stage(tmp_path, monkeypatch):
    """POST /api/cases {title} -> CaseSummary: a fresh id, the title, stage INTAKE, nothing needing attention."""
    client = scenario(tmp_path, monkeypatch).client()
    res = client.post("/api/cases", json={"title": "State v. Test"})
    assert res.status_code == 200
    body = res.json()
    assert re.fullmatch(r"case-\d{4}", body["case_id"])
    assert body["title"] == "State v. Test"
    assert body["stage"] == Stage.INTAKE.value
    assert body["needs_attention"] == 0 and body["rights_chips"] == []


def test_two_new_cases_get_different_ids(tmp_path, monkeypatch):
    client = scenario(tmp_path, monkeypatch).client()
    a = client.post("/api/cases", json={}).json()["case_id"]
    b = client.post("/api/cases", json={}).json()["case_id"]
    assert a != b


def test_list_cases_includes_the_seeded_case_with_its_gate_1_item(tmp_path, monkeypatch):
    """case-0007 after the dossier stage: one item needs attention (antecedents is UNSUPPORTED), plan §13.5 cause list."""
    _, client = seeded(tmp_path, monkeypatch, approve_gate1=False)
    cases = {c["case_id"]: c for c in client.get("/api/cases").json()}
    assert CASE in cases
    assert cases[CASE]["needs_attention"] == 1


def test_rights_chips_put_the_urgent_one_first(tmp_path, monkeypatch):
    """Rights Radar chips, urgent first: the default-bail window of 6 days comes before the s.479 'CHECK' chip."""
    _, client = seeded(tmp_path, monkeypatch, rights=urgent_rights())
    chips = client.get(f"/api/cases/{CASE}").json()["rights_chips"]
    assert len(chips) >= 2
    assert "default" in chips[0].lower() and "6 days" in chips[0]


def test_cause_list_orders_urgent_cases_first(tmp_path, monkeypatch):
    """Plan §13.5: 'Rights Radar chips (urgent first)': a case with an urgent chip is listed before one without."""
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record("case-0008")
    sc.seed_record("case-0009", rights=urgent_rights("case-0009"))
    ids = [c["case_id"] for c in sc.client().get("/api/cases").json()]
    assert ids.index("case-0009") < ids.index("case-0008")


def test_unknown_case_is_404(tmp_path, monkeypatch):
    client = scenario(tmp_path, monkeypatch).client()
    for path in ("", "/ingestion", "/dossier", "/dates", "/rights", "/brief", "/spar", "/prep", "/budget"):
        assert client.get(f"/api/cases/case-9999{path}").status_code == NOT_FOUND, path


# ---- tabs --------------------------------------------------------------------------------------------------------
def test_dossier_tab_returns_the_folded_dossier(tmp_path, monkeypatch):
    """GET dossier: the case-0007 dossier of plan §7.1: arrest 2024-08-20 VERIFIED, custody 167 COMPUTED, antecedents UNSUPPORTED."""
    _, client = seeded(tmp_path, monkeypatch)
    body = client.get(f"/api/cases/{CASE}/dossier").json()
    fields = body["fields"]
    assert body["case_id"] == CASE
    assert (fields["arrest_date"]["value"], fields["arrest_date"]["status"]) == ("2024-08-20", "VERIFIED")
    assert (fields["custody_days"]["value"], fields["custody_days"]["status"]) == (167, "COMPUTED")
    assert fields["antecedents"]["status"] == "UNSUPPORTED"


def test_dates_tab_is_the_timeline_in_date_order(tmp_path, monkeypatch):
    """GET dates: the seven timeline events, oldest first, each with its source."""
    _, client = seeded(tmp_path, monkeypatch)
    rows = client.get(f"/api/cases/{CASE}/dates").json()
    assert [r["date"] for r in rows] == ["2024-08-10", "2024-08-14", "2024-08-20", "2024-08-21", "2024-09-30", "2024-11-02", "2024-12-05"]
    assert all(r["source"]["doc"] for r in rows)


def test_rights_tab_has_the_seven_checks_of_plan_7_3(tmp_path, monkeypatch, case_meta):
    _, client = seeded(tmp_path, monkeypatch)
    body = client.get(f"/api/cases/{CASE}/rights").json()
    assert {c["check"]: c["status"] for c in body["checks"]} == case_meta["expected"]["rights_statuses"]
    assert body["as_of"] == "2025-02-03"


def test_ingestion_tab_returns_the_latest_report(tmp_path, monkeypatch):
    from vakeel_sahayak.schemas.ingestion_report import IngestionReport

    report = IngestionReport(case_id=CASE, file="bundle_1.pdf", questions=["Page 3 of the FIR is unreadable. Can you upload a clearer copy?"])
    _, client = seeded(tmp_path, monkeypatch, ingestion=report)
    body = client.get(f"/api/cases/{CASE}/ingestion").json()
    assert body["file"] == "bundle_1.pdf" and body["questions"] == report.questions


def test_brief_spar_and_prep_are_404_before_drafting(tmp_path, monkeypatch):
    """No brief exists before Sutradhar and Vakeel have run."""
    _, client = seeded(tmp_path, monkeypatch)
    for tab in ("brief", "spar", "prep"):
        assert client.get(f"/api/cases/{CASE}/{tab}").status_code == NOT_FOUND, tab


def test_brief_and_spar_tabs_return_the_views(tmp_path, monkeypatch):
    sc, client = seeded(tmp_path, monkeypatch, brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    brief = client.get(f"/api/cases/{CASE}/brief").json()
    assert [g["id"] for g in brief["grounds"]] == ["G1"]
    assert brief["label"] == "AI-generated draft. Not legal advice."
    spar = client.get(f"/api/cases/{CASE}/spar").json()
    assert spar["rounds"] == 2 and [o["id"] for o in spar["objections"]] == ["O1"]


def test_prep_card_has_no_prediction_and_no_grant_rate(tmp_path, monkeypatch):
    """The hearing-prep card carries no outcome prediction and no grant rate (plan §8.3)."""
    _, client = seeded(tmp_path, monkeypatch, brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    text = client.get(f"/api/cases/{CASE}/prep").text
    assert not sh.PROBABILITY_RE.search(text)
    assert "grant rate" not in text.lower()


def test_budget_tab_shows_the_default_case_cap(tmp_path, monkeypatch):
    """GET budget: tokens_cap is the plan's 150K per case (plan §6.2); store calls are counted per factor."""
    _, client = seeded(tmp_path, monkeypatch)
    body = client.get(f"/api/cases/{CASE}/budget").json()
    assert body["tokens_cap"] == 150000 and body["tokens_spent"] >= 0
    assert isinstance(body["store_calls"], dict)


# ---- counsel edits a field ---------------------------------------------------------------------------------------
def test_editing_a_field_makes_it_user_edited_and_is_logged_as_counsel(tmp_path, monkeypatch):
    """PATCH dossier/arrest_date: the new value, status USER_EDITED, and a USER_ACTION event by counsel (audit trail)."""
    sc, client = seeded(tmp_path, monkeypatch)
    res = client.patch(f"/api/cases/{CASE}/dossier/arrest_date", json={"value": "2024-08-19"})
    assert res.status_code == 200
    field = res.json()["fields"]["arrest_date"]
    assert (field["value"], field["status"]) == ("2024-08-19", FieldStatus.USER_EDITED.value)
    assert client.get(f"/api/cases/{CASE}/dossier").json()["fields"]["arrest_date"]["value"] == "2024-08-19"
    (action,) = [e for e in sc.events(EventKind.USER_ACTION) if "arrest_date" in str(e.inputs)]
    assert str(getattr(action.actor, "value", action.actor)).lower() == "counsel"


def test_editing_an_unknown_field_is_404(tmp_path, monkeypatch):
    """ASSUMPTION: a field that is not in the dossier is a 404 (not found), not a silent create."""
    _, client = seeded(tmp_path, monkeypatch)
    assert client.patch(f"/api/cases/{CASE}/dossier/no_such_field", json={"value": 1}).status_code == NOT_FOUND


def test_an_edit_leaves_other_fields_untouched(tmp_path, monkeypatch):
    _, client = seeded(tmp_path, monkeypatch)
    before = client.get(f"/api/cases/{CASE}/dossier").json()["fields"]
    client.patch(f"/api/cases/{CASE}/dossier/arrest_date", json={"value": "2024-08-19"})
    after = client.get(f"/api/cases/{CASE}/dossier").json()["fields"]
    assert {k: v for k, v in after.items() if k != "arrest_date"} == {k: v for k, v in before.items() if k != "arrest_date"}


# ---- drafting ----------------------------------------------------------------------------------------------------
def test_draft_is_refused_before_gate_1(tmp_path, monkeypatch):
    """Later stages unlock after Gate 1 (plan §13.5): POST draft with Gate 1 open is a 409 and nothing is planned."""
    sc, client = seeded(tmp_path, monkeypatch, approve_gate1=False)
    assert client.post(f"/api/cases/{CASE}/draft").status_code == CHECKLIST_OPEN
    assert sc.ada.calls == []


def test_draft_after_gate_1_is_accepted_and_returns_a_status(tmp_path, monkeypatch):
    """With Gate 1 approved the draft starts (plan §13.6 flow 3); the response is a small {status: ...} object."""
    _, client = seeded(tmp_path, monkeypatch)
    res = client.post(f"/api/cases/{CASE}/draft")
    assert res.status_code in (200, 202)
    assert isinstance(res.json(), dict) and res.json()


# ---- page images (laptop only) -----------------------------------------------------------------------------------
def test_page_image_of_an_unknown_document_is_404(tmp_path, monkeypatch):
    _, client = seeded(tmp_path, monkeypatch)
    assert client.get(f"/api/cases/{CASE}/files/d9/pages/1").status_code == NOT_FOUND


def test_page_number_must_be_an_integer(tmp_path, monkeypatch):
    _, client = seeded(tmp_path, monkeypatch)
    assert client.get(f"/api/cases/{CASE}/files/d1/pages/first").status_code == 422


def test_page_image_is_served_from_the_laptop_data_directory(tmp_path, monkeypatch):
    """Raw page images are served from `$VS_DATA_DIR/cases/<case>/files/<doc>/pages/<n>.png` and nowhere else.

    ASSUMPTION: that is where Munshi leaves rendered pages for the viewer (plan §13.5: PDF viewer with highlights)."""
    sc, client = seeded(tmp_path, monkeypatch)
    png = b"\x89PNG\r\n\x1a\nstub"
    page = sc.data_dir / "cases" / CASE / "files" / "d1" / "pages" / "1.png"
    page.parent.mkdir(parents=True)
    page.write_bytes(png)
    res = client.get(f"/api/cases/{CASE}/files/d1/pages/1")
    assert res.status_code == 200 and res.content == png


@pytest.mark.parametrize("bad", ["../../etc/passwd", "..%2F..%2Fsecret"])
def test_page_image_route_cannot_escape_the_case_directory(tmp_path, monkeypatch, bad):
    """A traversal in the document id never reads outside the case directory."""
    _, client = seeded(tmp_path, monkeypatch)
    assert client.get(f"/api/cases/{CASE}/files/{bad}/pages/1").status_code in (400, 404, 422)


def test_rights_tab_marks_every_check_unverified_until_a_person_verifies_it(tmp_path, monkeypatch):
    _, client = seeded(tmp_path, monkeypatch)
    body = client.get(f"/api/cases/{CASE}/rights").json()
    assert body["checks"] and all(c["verification"] == "unverified" for c in body["checks"])
    assert sorted(body["unverified_checks"]) == sorted(c["check"] for c in body["checks"])
    assert all(c["last_verified"] is None for c in body["checks"])  # the stored fields are unchanged; `verification` is additive


def test_rights_tab_shows_the_verification_date_once_a_check_is_verified(tmp_path, monkeypatch):
    rights = urgent_rights()
    rights.checks[0] = rights.checks[0].model_copy(update={"last_verified": "2026-11-02"})
    _, client = seeded(tmp_path, monkeypatch, rights=rights)
    body = client.get(f"/api/cases/{CASE}/rights").json()
    by = {c["check"]: c for c in body["checks"]}
    first = rights.checks[0].check.value
    assert by[first]["verification"] == "2026-11-02" and first not in body["unverified_checks"]
    assert all(c["verification"] == "unverified" for k, c in by.items() if k != first)


def test_rights_openapi_documents_the_verification_field_with_an_example(tmp_path, monkeypatch):
    _, client = seeded(tmp_path, monkeypatch)
    schema = client.get("/openapi.json").json()["components"]["schemas"]
    assert "verification" in schema["RightsCheckOut"]["properties"] and "unverified_checks" in schema["RightsReportOut"]["properties"]
    assert schema["RightsReportOut"]["example"]["checks"][0]["verification"] == "unverified"


def test_rights_chips_and_the_stored_report_are_unchanged(tmp_path, monkeypatch):
    from vakeel_sahayak.schemas.rights_report import RightsReport

    rights = urgent_rights()
    assert "verification" not in RightsReport.model_validate(rights.model_dump()).model_dump()["checks"][0]  # the golden shape of the stored report
    _, client = seeded(tmp_path, monkeypatch, rights=rights)
    chips = client.get(f"/api/cases/{CASE}").json()["rights_chips"]
    assert chips and all(isinstance(c, str) for c in chips)
