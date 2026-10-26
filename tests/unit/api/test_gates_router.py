"""Router `gates` (plan §13.1, §13.5, §16): the checklist modal and the two approvals.

Gate 1 (after the dossier): every UNSUPPORTED field resolved or acknowledged. Gate 2 (before export): every NEEDS_REVIEW
ground and UNANSWERED objection resolved. Approval is counsel's alone (a GATE_APPROVED event by `counsel`). Refusal when the
checklist is not cleared is a 409 (ASSUMPTION, see `_helpers.py`).
"""

from __future__ import annotations

import pytest

from tests.system import _helpers as sh
from tests.unit.api._helpers import CASE, CHECKLIST_OPEN, G1, G2, INVALID, NOT_FOUND, scenario
from vakeel_sahayak.schemas.enums import ClaimCheck, EventKind


def gate_url(gate: str, case: str = CASE) -> str:
    return f"/api/cases/{case}/gates/{gate}"


def with_open_gate_2(tmp_path, monkeypatch):
    """After Gate 1; a brief with G2 NEEDS_REVIEW and a sparring record with O2 UNANSWERED; Gate 2 open."""
    sc = scenario(tmp_path, monkeypatch)
    g2 = sh.GROUNDS["G2"].model_copy(update={"check": ClaimCheck.NEEDS_REVIEW})
    brief = sh.clean_brief(CASE).model_copy(update={"grounds": [sh.GROUNDS["G1"].model_copy(update={"check": ClaimCheck.SUPPORTED}), g2]})
    spar = sh.clean_sparring(CASE).model_copy(update={"objections": [sh.O1_JUDGED, sh.O2_JUDGED]})
    sc.seed_record(brief=brief, sparring=spar)
    return sc, sc.client()


def test_gate_1_checklist_lists_the_unsupported_field(tmp_path, monkeypatch):
    """case-0007's only UNSUPPORTED field is antecedents (plan §7.1); the gate is open."""
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    body = sc.client().get(gate_url(G1)).json()
    assert body["gate"] == G1 and body["open"] is True
    assert body["unresolved_unsupported"] == ["antecedents"]
    assert body["unresolved_needs_review"] == [] and body["unresolved_unanswered"] == []


def test_gate_1_cannot_be_approved_with_an_unresolved_field(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    res = sc.client().post(gate_url(G1) + "/approve", json={"acknowledged_fields": []})
    assert res.status_code == CHECKLIST_OPEN
    assert sc.events(EventKind.GATE_APPROVED) == []


def test_gate_1_is_approved_once_the_field_is_acknowledged(tmp_path, monkeypatch):
    """Acknowledging antecedents clears Gate 1: 200, the gate is no longer open, and counsel's approval is in the log."""
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    res = sc.client().post(gate_url(G1) + "/approve", json={"acknowledged_fields": ["antecedents"]})
    assert res.status_code == 200 and res.json()["open"] is False
    (ev,) = sc.events(EventKind.GATE_APPROVED)
    assert str(getattr(ev.actor, "value", ev.actor)) == "counsel" and ev.inputs["gate"] == G1


def test_wrong_acknowledgement_does_not_clear_the_gate(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    res = sc.client().post(gate_url(G1) + "/approve", json={"acknowledged_fields": ["personal"]})
    assert res.status_code == CHECKLIST_OPEN


def test_gate_2_checklist_lists_needs_review_and_unanswered_items(tmp_path, monkeypatch):
    """Plan §13.5: NEEDS_REVIEW grounds and UNANSWERED objections: here G2 and O2."""
    _, client = with_open_gate_2(tmp_path, monkeypatch)
    body = client.get(gate_url(G2)).json()
    assert body["unresolved_needs_review"] == ["G2"] and body["unresolved_unanswered"] == ["O2"]


def test_gate_2_cannot_be_approved_until_items_are_resolved(tmp_path, monkeypatch):
    sc, client = with_open_gate_2(tmp_path, monkeypatch)
    assert client.post(gate_url(G2) + "/approve", json={"acknowledged_fields": []}).status_code == CHECKLIST_OPEN
    assert [e.inputs["gate"] for e in sc.events(EventKind.GATE_APPROVED)] == [G1]


def test_gate_2_is_approved_after_counsel_resolves_every_item(tmp_path, monkeypatch):
    """Counsel resolves G2 and O2 (USER_ACTION events, as in the system helpers); then Gate 2 can be approved."""
    sc, client = with_open_gate_2(tmp_path, monkeypatch)
    sc.resolve("G2")
    sc.resolve("O2")
    res = client.post(gate_url(G2) + "/approve", json={"acknowledged_fields": []})
    assert res.status_code == 200 and res.json()["open"] is False


def test_resolutions_sent_with_the_approval_are_recorded_as_counsels(tmp_path, monkeypatch):
    """The workspace sends what counsel resolved as NEEDS_REVIEW:<ground> / UNANSWERED:<objection> in acknowledged_fields; the route
    records each as counsel's resolve event, and the gate opens in the same request."""
    sc, client = with_open_gate_2(tmp_path, monkeypatch)
    res = client.post(gate_url(G2) + "/approve", json={"acknowledged_fields": ["NEEDS_REVIEW:G2", "UNANSWERED:O2", "NEEDS_REVIEW:issue-0"]})
    assert res.status_code == 200 and res.json()["open"] is False
    resolves = [e for e in sc.events(EventKind.USER_ACTION) if e.inputs.get("action") == "resolve"]
    assert sorted(e.inputs["item"] for e in resolves) == ["G2", "O2"]
    assert all(str(getattr(e.actor, "value", e.actor)) == "counsel" for e in resolves)


def test_a_partial_set_of_resolutions_still_leaves_the_gate_closed(tmp_path, monkeypatch):
    sc, client = with_open_gate_2(tmp_path, monkeypatch)
    assert client.post(gate_url(G2) + "/approve", json={"acknowledged_fields": ["NEEDS_REVIEW:G2"]}).status_code == CHECKLIST_OPEN
    assert client.get(gate_url(G2)).json()["unresolved_unanswered"] == ["O2"]


def test_approving_gate_2_of_one_case_does_not_approve_another(tmp_path, monkeypatch):
    """No bulk approval (plan §16): the approval is recorded for the case in the URL only."""
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record("case-0008", brief=sh.clean_brief("case-0008"), sparring=sh.clean_sparring("case-0008"))
    sc.seed_record(brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    client = sc.client()
    assert client.post(gate_url(G2) + "/approve", json={"acknowledged_fields": []}).status_code == 200
    assert client.get(gate_url(G2, "case-0008")).json()["open"] is True


def test_the_api_has_no_route_that_lets_an_agent_approve(tmp_path, monkeypatch):
    """Approval routes are POST .../gates/{gate}/approve only; no other route path mentions approval."""
    app = scenario(tmp_path, monkeypatch).client().app
    paths = [(r.path, sorted(r.methods)) for r in app.routes if hasattr(r, "methods")]
    assert [p for p, m in paths if "approve" in p] == ["/api/cases/{case_id}/gates/{gate}/approve"]


def test_unknown_gate_is_422(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record()
    assert sc.client().get(gate_url("GATE_3_WHATEVER")).status_code == INVALID


def test_gate_of_an_unknown_case_is_404(tmp_path, monkeypatch):
    client = scenario(tmp_path, monkeypatch).client()
    assert client.get(gate_url(G1, "case-9999")).status_code == NOT_FOUND
    assert client.post(gate_url(G1, "case-9999") + "/approve", json={"acknowledged_fields": []}).status_code == NOT_FOUND


@pytest.mark.parametrize("body", [None, {"acknowledged_fields": "antecedents"}])
def test_approve_body_is_validated(tmp_path, monkeypatch, body):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    res = sc.client().post(gate_url(G1) + "/approve", **({"json": body} if body is not None else {}))
    assert res.status_code == INVALID
