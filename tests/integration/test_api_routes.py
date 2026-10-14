"""FastAPI end to end through TestClient (plan §13.1, §13.5, §13.6 flows 1-3, §16): the API serves the views of a case that the
real agents have just worked on, and its gates and SSE stream behave as the plan says.

The case is prepared by `tests.system._helpers.Scenario` (real Munshi, Peshkar, Sutradhar, Vakeel and Abhiyojak on the fakes: the
14-page bundle, the scripted Ada client) up to a drafted brief; the HTTP layer then reads it. Routers are unit-tested in
tests/unit/api/; here the point is the wiring: log, stores, agents, gates and the stream agree with each other.

ASSUMPTIONS: HTTP codes and the SSE frame layout as in tests/unit/api/_helpers.py. SKELETON-GAP: the API has no route to resolve a
Gate 2 checklist item (a NEEDS_REVIEW ground, an UNANSWERED objection); `Scenario.resolve` writes the counsel USER_ACTION event a
future route would write.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fakes.toolbox import leaked_names
from tests.system import _helpers as sh
from tests.unit.api._helpers import CHECKLIST_OPEN, EXPORT_REFUSED, sse_frames
from tests.unit.export._helpers import Spy
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.schemas.enums import AgentName, EventKind

CASE = sh.CASE_ID
G1, G2 = sh.G1.value, sh.G2.value
GET_TABS = ("ingestion", "dossier", "dates", "rights", "brief", "spar", "prep", "budget")


class FiniteView:
    """The real log, except that `subscribe` ends at once (TestClient cannot follow a stream that never ends)."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def subscribe(self, case_id: str):
        return iter(())


def drafted(tmp_path, monkeypatch, **kw):
    """Intake, dossier, Gate 1 (acknowledged by counsel), then Sutradhar plans, Vakeel drafts, Abhiyojak spars."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), **kw)
    sc.through_gate1()
    sc.through_draft()
    return sc


def stream_client(sc):
    from vakeel_sahayak.api import deps

    client = sc.client()
    client.app.dependency_overrides[deps.get_event_log] = lambda case_id=None: FiniteView(sc.log)
    return client


@pytest.fixture()
def spy(monkeypatch):
    s = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", s.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", s.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", s.pdf)
    return s


# ---- the tabs agree with what the agents did ---------------------------------------------------------------------
def test_every_tab_of_a_drafted_case_returns_json(tmp_path, monkeypatch):
    """Ingestion, dossier, dates, rights, brief, spar, prep and budget all answer 200 for the case the agents just worked on."""
    client = drafted(tmp_path, monkeypatch).client()
    for tab in GET_TABS:
        res = client.get(f"/api/cases/{CASE}/{tab}")
        assert res.status_code == 200, (tab, res.text[:200])
        res.json()


def test_dossier_and_dates_tabs_show_what_munshi_and_peshkar_filed(tmp_path, monkeypatch):
    """Plan §13.6 flow 1: arrest 2024-08-20 and the charge sheet of 2024-11-02 are on the dossier and the List of Dates."""
    client = drafted(tmp_path, monkeypatch).client()
    fields = client.get(f"/api/cases/{CASE}/dossier").json()["fields"]
    assert fields["arrest_date"]["value"] == "2024-08-20"
    assert fields["charge_sheet"]["value"] == {"filed": True, "date": "2024-11-02"}
    dates = [r["date"] for r in client.get(f"/api/cases/{CASE}/dates").json()]
    assert {"2024-08-20", "2024-08-21", "2024-11-02"} <= set(dates) and dates == sorted(dates)


def test_ingestion_tab_lists_the_four_documents_and_the_unreadable_page(tmp_path, monkeypatch):
    """Plan §4.6: four documents (FIR 1-4, remand 5-7 and 8-10, bail order 11-14); the unreadable FIR page is among the questions."""
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/ingestion").json()
    assert [(d["type"], d["pages"]) for d in body["documents"]] == [(t.value, p) for t, p, _ in sh.EXPECTED_BUNDLE_DOCS]
    assert any("unreadable" in q.lower() for q in body["questions"])


def test_brief_tab_has_grounds_with_rendered_citations_and_the_label(tmp_path, monkeypatch):
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/brief").json()
    assert body["grounds"] and body["label"] == "AI-generated draft. Not legal advice."
    assert all(a["citation"] for g in body["grounds"] for a in g["authorities"])


def test_spar_tab_shows_two_rounds_and_the_unanswered_objection(tmp_path, monkeypatch):
    """Plan §9: rounds 2; O2 (witness tampering) is UNANSWERED and waits for counsel."""
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/spar").json()
    assert body["rounds"] == 2
    verdicts = {o["id"]: o["verdict"] for o in body["objections"]}
    assert verdicts["O1"] == "ANSWERED" and verdicts["O2"] == "UNANSWERED"
    assert "O3" not in verdicts  # ungrounded, discarded


def test_prep_card_has_no_prediction(tmp_path, monkeypatch):
    text = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/prep").text
    assert not sh.PROBABILITY_RE.search(text) and "grant rate" not in text.lower()


def test_budget_tab_stays_within_the_caps(tmp_path, monkeypatch):
    body = drafted(tmp_path, monkeypatch).client().get(f"/api/cases/{CASE}/budget").json()
    assert body["tokens_spent"] <= body["tokens_cap"] == 150000
    assert all(n <= 8 for n in body["store_calls"].values())


# ---- gates and export over HTTP ----------------------------------------------------------------------------------
def test_gate_1_was_approved_by_counsel_and_the_api_says_so(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    body = sc.client().get(f"/api/cases/{CASE}/gates/{G1}").json()
    assert body["open"] is False and body["unresolved_unsupported"] == []
    assert sh.agent_approvals(sc.events()) == []


def test_gate_2_flow_over_http(tmp_path, monkeypatch, spy):
    """Plan §13.6 flow 3: the checklist lists the UNANSWERED objection; approval is refused (409) until counsel resolves it; then 200,
    and only then does export work (200 with files); before it, export is 403 and writes nothing."""
    sc = drafted(tmp_path, monkeypatch)
    client = sc.client()
    status = client.get(f"/api/cases/{CASE}/gates/{G2}").json()
    assert status["unresolved_unanswered"] == ["O2"]
    assert client.post(f"/api/cases/{CASE}/gates/{G2}/approve", json={"acknowledged_fields": []}).status_code == CHECKLIST_OPEN
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).status_code == EXPORT_REFUSED
    assert spy.calls == []
    for item in status["unresolved_needs_review"] + status["unresolved_unanswered"]:
        sc.resolve(item)  # SKELETON-GAP: no API route for this
    res = client.post(f"/api/cases/{CASE}/gates/{G2}/approve", json={"acknowledged_fields": status["unresolved_unsupported"]})
    assert res.status_code == 200 and res.json()["open"] is False
    exported = client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"})
    assert exported.status_code == 200 and len(exported.json()) >= 4
    assert all(Path(p).exists() for p in exported.json())


def test_nothing_is_exported_by_the_run_itself(tmp_path, monkeypatch, spy):
    """Drafting never exports: no export TOOL_CALL and no writer ran before counsel's Gate 2 (plan §16)."""
    sc = drafted(tmp_path, monkeypatch)
    assert sh.export_tool_calls(sc.events()) == [] and spy.calls == []
    assert sc.toolbox.exports == []


# ---- the SSE stream ----------------------------------------------------------------------------------------------
def test_sse_replays_the_whole_agent_trace_in_order(tmp_path, monkeypatch):
    """Plan §3.3 use 4: the stream is the log: ids in log order, kinds valid, every agent of the run visible."""
    sc = drafted(tmp_path, monkeypatch)
    res = stream_client(sc).get(f"/api/cases/{CASE}/events")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    frames = sse_frames(res.text)
    logged = sc.events()
    assert [f["id"] for f in frames] == [e.event_id for e in logged]
    assert {f["event"] for f in frames} <= {k.value for k in EventKind}
    actors = {json.loads(f["data"])["actor"] for f in frames}
    assert {AgentName.MUNSHI.value, AgentName.PESHKAR.value, AgentName.SUTRADHAR.value} <= actors


def test_sse_resumes_after_the_last_seen_event(tmp_path, monkeypatch):
    sc = drafted(tmp_path, monkeypatch)
    logged = sc.events()
    cut = logged[len(logged) // 2].event_id
    res = stream_client(sc).get(f"/api/cases/{CASE}/events", headers={"Last-Event-ID": cut})
    ids = [f["id"] for f in sse_frames(res.text)]
    assert ids == [e.event_id for e in logged[len(logged) // 2 + 1:]]


def test_sse_carries_the_tool_trace_of_the_plan(tmp_path, monkeypatch):
    """The 'Show the plan' trace needs the tool calls of Sutradhar: store tools appear as TOOL_CALL frames by SUTRADHAR."""
    frames = sse_frames(stream_client(drafted(tmp_path, monkeypatch)).get(f"/api/cases/{CASE}/events").text)
    sut = [json.loads(f["data"]) for f in frames if f["event"] == EventKind.TOOL_CALL.value and json.loads(f["data"])["actor"] == "SUTRADHAR"]
    assert {e["tool"] for e in sut} & {"search_reasoning", "search_case_docs", "get_timeline"}


# ---- privacy across the API --------------------------------------------------------------------------------------
def test_no_planted_name_in_any_response_or_in_the_stream(tmp_path, monkeypatch, planted_names):
    """Plan §16: pseudonymised text only; the API never serves a raw name. (The constructed bundle's pages carry role pseudonyms; the
    toolbox's pseudonymiser would replace any planted name before filing.)"""
    sc = drafted(tmp_path, monkeypatch)
    client = stream_client(sc)
    bodies = [client.get(f"/api/cases/{CASE}/{tab}").text for tab in GET_TABS]
    bodies.append(client.get(f"/api/cases/{CASE}/events").text)
    assert leaked_names(bodies, planted_names) == []


# ---- upload through the API ----------------------------------------------------------------------------------------
def test_uploading_the_bundle_through_the_api_runs_intake(tmp_path, monkeypatch):
    """Plan §13.6 flow 1 step 1-2: dropping the 14-page PDF makes Munshi split and label it.

    ASSUMPTION: the upload route starts intake and the work is complete when the response returns (TestClient runs background tasks)."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    client = sc.client()
    res = client.post(f"/api/cases/{CASE}/upload", files=[("files", ("bundle_1.pdf", sh.pdfgen.make_text_pdf(tmp_path / "b.pdf", ["x"]).read_bytes(), "application/pdf"))])
    assert res.status_code == 200
    report = client.get(f"/api/cases/{CASE}/ingestion").json()
    assert len(report["documents"]) == 4
