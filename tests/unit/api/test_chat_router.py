"""Router `chat` (plan §6.4, §13.5): counsel's question goes to Sutradhar, which routes it to a store or tool and answers
shortly with citations; outcome predictions and lay advice are refused. The core of the workspace (centre pane).

The model and the tools are the scripted/fake ones of `tests/system/_helpers.Scenario`.
"""

from __future__ import annotations

import re

import pytest

from tests.system import _helpers as sh
from tests.unit.api._helpers import CASE, INVALID, NOT_FOUND, scenario
from vakeel_sahayak.schemas.enums import AgentName, EventKind

CUSTODY_Q = "How many days in custody?"
CUSTODY_A = "Custody: 167 days [date_calc from arrest 20.08.2024]; s.479 not yet reached"


def chat_scenario(tmp_path, monkeypatch, answer: str = CUSTODY_A):
    sc = scenario(tmp_path, monkeypatch, ada=sh.ada_client(chat=[("custody", answer)]))
    sc.with_case_state()
    return sc, sc.client()


def test_custody_question_is_answered_with_chips_for_the_timeline_and_date_calc(tmp_path, monkeypatch):
    """Plan §13.6 flow 2: a one-line cited answer, with store/tool chips on it."""
    _, client = chat_scenario(tmp_path, monkeypatch)
    res = client.post(f"/api/cases/{CASE}/chat", json={"text": CUSTODY_Q})
    assert res.status_code == 200
    msg = res.json()
    assert msg["role"] == "agent" and msg["agent"] == AgentName.SUTRADHAR.value and msg["case_id"] == CASE
    assert re.search(r"\b16[78]\b", msg["text"])
    assert {c["tool"] for c in msg["chips"]} >= {"get_timeline", "date_calc"}
    assert msg["refused"] is False


def test_answer_is_short(tmp_path, monkeypatch):
    """'Answers are short and cited' (plan §6.4): ASSUMPTION: at most 600 characters."""
    _, client = chat_scenario(tmp_path, monkeypatch)
    assert len(client.post(f"/api/cases/{CASE}/chat", json={"text": CUSTODY_Q}).json()["text"]) <= 600


def test_section_equivalent_question_goes_to_the_concordance(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch, ada=sh.ada_client(chat=[("equivalent", "BNS 318(4) [map_section]")]))
    sc.with_case_state()
    msg = sc.client().post(f"/api/cases/{CASE}/chat", json={"text": "BNS equivalent of 420 IPC?"}).json()
    assert [c["tool"] for c in msg["chips"]] == ["map_section"]
    assert "318(4)" in msg["text"]


@pytest.mark.parametrize("question", ["Will my client get bail?", "What are the chances of bail in this case?", "Predict the outcome."])
def test_outcome_predictions_are_refused(tmp_path, monkeypatch, question):
    """Refused, flagged, no tool called, no probability in the text (plan §1.3, §6.4)."""
    sc, client = chat_scenario(tmp_path, monkeypatch)
    msg = client.post(f"/api/cases/{CASE}/chat", json={"text": question}).json()
    assert msg["refused"] is True and msg["chips"] == []
    assert not sh.PROBABILITY_RE.search(msg["text"])
    assert sc.toolbox.calls == []


@pytest.mark.parametrize("question", ["I am the accused, what should I do now?", "My brother was arrested yesterday, how do I get him out?"])
def test_lay_advice_is_refused_and_points_to_legal_aid(tmp_path, monkeypatch, question):
    """No advice to accused persons or the public (plan §1.3); the pointer is NALSA 15100 (ASSUMPTION: the refusal names it)."""
    sc, client = chat_scenario(tmp_path, monkeypatch)
    msg = client.post(f"/api/cases/{CASE}/chat", json={"text": question}).json()
    assert msg["refused"] is True and "15100" in msg["text"]
    assert sc.toolbox.calls == []


def test_turns_are_kept_in_order_with_distinct_ids(tmp_path, monkeypatch):
    """GET chat returns the history: counsel's question, then the agent's answer."""
    _, client = chat_scenario(tmp_path, monkeypatch)
    client.post(f"/api/cases/{CASE}/chat", json={"text": CUSTODY_Q})
    history = client.get(f"/api/cases/{CASE}/chat").json()
    assert [m["role"] for m in history] == ["counsel", "agent"]
    assert history[0]["text"] == CUSTODY_Q
    assert len({m["message_id"] for m in history}) == 2


def test_chat_is_written_to_the_event_log(tmp_path, monkeypatch):
    """The question is a USER_ACTION by counsel and the answer an AGENT_MESSAGE by Sutradhar (audit trail)."""
    sc, client = chat_scenario(tmp_path, monkeypatch)
    client.post(f"/api/cases/{CASE}/chat", json={"text": CUSTODY_Q})
    assert any(CUSTODY_Q in e.model_dump_json() for e in sc.events(EventKind.USER_ACTION))
    assert [str(getattr(e.actor, "value", e.actor)) for e in sc.events(EventKind.AGENT_MESSAGE)][-1] == "SUTRADHAR"


def test_empty_message_is_422(tmp_path, monkeypatch):
    _, client = chat_scenario(tmp_path, monkeypatch)
    assert client.post(f"/api/cases/{CASE}/chat", json={}).status_code == INVALID


def test_chat_on_an_unknown_case_is_404(tmp_path, monkeypatch):
    client = scenario(tmp_path, monkeypatch).client()
    assert client.post("/api/cases/case-9999/chat", json={"text": CUSTODY_Q}).status_code == NOT_FOUND
    assert client.get("/api/cases/case-9999/chat").status_code == NOT_FOUND


def test_question_text_reaching_ada_is_pseudonymised(tmp_path, monkeypatch, planted_names):
    """A name typed into the chat is pseudonymised before the Ada-bound model sees it (plan §16)."""
    sc, client = chat_scenario(tmp_path, monkeypatch)
    client.post(f"/api/cases/{CASE}/chat", json={"text": f"How many days has {planted_names[0]} been in custody?"})
    assert not [n for n in planted_names if any(n in p for p in sc.ada_prompts)]
