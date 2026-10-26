"""User flow 2 (plan §13.6, §6.4): quick questions in the chat get short, cited answers; predictions and lay advice are refused.

Real modules: SutradharAgent.answer_chat (routing, tool calls, answer), BaseAgent.call_tool, the event log, the FastAPI chat routes.
Fakes: the Ada client (a scripted answer that is only returned when the tool results are in the prompt, so a scripted answer cannot
pass unless the evidence reached the model), the in-memory stores of case-0007, the toolbox. The `models`/`gpu` variant uses the real 14B.

ASSUMPTIONS: a chat answer is at most 600 characters; chips name the tools that were called; a refusal has `refused=True`, no chips and
no tool call; chat never writes to the case record other than the two chat events.
"""

from __future__ import annotations

import pytest

from tests.system import _helpers as sh
from tests.system import _scripts as ss
from tests.unit.agents._helpers import tools_yaml
from vakeel_sahayak.schemas.enums import AgentName, EventKind, StoreName

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
CUSTODY_ANSWER = "Custody: 167 days [date_calc from arrest 20.08.2024]; s.479 not yet reached"
FORBIDDEN_ORDERS = {"TESTORD-2024-0001", "SAMEFIR-2024-0002", "DLHC-2025-0099"}


def chat_case(tmp_path, monkeypatch, chat: list | None = None) -> sh.Scenario:
    sc = sh.Scenario(tmp_path, monkeypatch, ada=sh.ada_client(chat=chat or []))
    sc.with_case_state()
    return sc


# ---- cited one-line answers ----------------------------------------------------------------------------------------------
def test_custody_question_gets_a_one_line_cited_answer(tmp_path, monkeypatch):
    """The answer comes from `case.timeline` + `date_calc` and cites them; it is only given if the tool results are in the prompt."""
    sc = chat_case(tmp_path, monkeypatch, [("custody", sh.prompt_must_contain(CUSTODY_ANSWER, "date_calc", "2024-08-20"))])
    msg = sc.chat("How many days in custody?")
    # RECONCILED: Sutradhar composes the cited sentence from the tool results (answer_chat docstring), it does not ask the model to phrase it;
    # the content the test cares about (the days counted by date_calc from the filed arrest date, one line, cited) is asserted instead of the wording
    assert "167 days" in msg.text and "2024-08-20" in msg.text and "date_calc" in msg.text and "\n" not in msg.text
    assert {c.tool for c in msg.chips} >= {"get_timeline", "date_calc"}
    assert msg.refused is False and msg.agent == AgentName.SUTRADHAR and msg.role == "agent"


def test_answers_are_short(tmp_path, monkeypatch):
    """'Answers are short and cited' (plan §6.4)."""
    sc = chat_case(tmp_path, monkeypatch, [("custody", CUSTODY_ANSWER)])
    assert len(sc.chat("How many days in custody?").text) <= 600


def test_section_equivalent_goes_to_the_concordance_only(tmp_path, monkeypatch):
    """'BNS equivalent of 420 IPC?' -> `map_section` and nothing else (no 'query everything')."""
    sc = chat_case(tmp_path, monkeypatch, [("equivalent", sh.prompt_must_contain("BNS 318(4) [map_section]", "318(4)"))])
    msg = sc.chat("BNS equivalent of 420 IPC?")
    assert [c.tool for c in msg.chips] == ["map_section"] and "318(4)" in msg.text


def test_eligibility_goes_to_the_rights_radar(tmp_path, monkeypatch):
    """'Is my client eligible under s.479?' -> the Rights Radar; the radar's check name is in the prompt."""
    answer = "s.479: 167 of 852 days; antecedents unknown (CHECK) [rights_check]"
    sc = chat_case(tmp_path, monkeypatch, [("479", sh.prompt_must_contain(answer, "undertrial_limit"))])
    msg = sc.chat("Is my client eligible under s.479?")
    # RECONCILED: the answer is composed from the Rights Radar entry (answer_chat docstring), not phrased by the model; assert its content
    assert [c.tool for c in msg.chips] == ["rights_check"]
    assert "undertrial_limit" in msg.text and "CHECK" in msg.text and "167 days" in msg.text and "852" in msg.text


def test_precedent_question_cites_retrieved_orders_only(tmp_path, monkeypatch):
    """'Any SC case on parity in a cheating case?' -> `caselaw.reasoning` + `caselaw.citations`; the cited order was retrieved,
    and no test, same-FIR or post-dated order can appear."""
    answer = "Yes: DLHC-2022-1187 para 14 applies parity; it relies on SC-2014-0463 [search_reasoning, citations]"
    sc = chat_case(tmp_path, monkeypatch, [("parity", sh.prompt_must_contain(answer, "DLHC-2022-1187"))])
    msg = sc.chat("Any SC case on parity in a cheating case?")
    assert {c.tool for c in msg.chips} == {"search_reasoning", "citations"}
    assert "DLHC-2022-1187" in msg.text and not [d for d in FORBIDDEN_ORDERS if d in msg.text]


def test_what_did_the_court_say_goes_to_the_case_documents(tmp_path, monkeypatch):
    sc = chat_case(tmp_path, monkeypatch, [("Sessions Court", "The Sessions Court rejected bail on 30.09.2024 [search_case_docs]")])
    msg = sc.chat("What did the Sessions Court say about antecedents?")
    assert [c.tool for c in msg.chips] == ["search_case_docs"]


def test_how_the_state_opposes_goes_to_objections_and_statutes(tmp_path, monkeypatch):
    sc = chat_case(tmp_path, monkeypatch, [("oppose", "Usually on gravity and flight risk [search_objections]")])
    msg = sc.chat("How does the State usually oppose bail in NDPS cases?")
    tools = {c.tool for c in msg.chips}
    assert "search_objections" in tools and tools <= {"search_objections", "get_statute", "search_statutes"}


# ---- at any point ----------------------------------------------------------------------------------------------------------
def test_any_question_any_time_even_before_gate_1(tmp_path, monkeypatch):
    """Plan §13.6: 'at any point counsel asks the chat'. A custody question works right after intake, with Gate 1 still open."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), ada=sh.ada_client(chat=[("custody", CUSTODY_ANSWER)]))
    sc.add_upload("bundle_1.pdf")
    sc.run(AgentName.MUNSHI)
    sc.run(AgentName.PESHKAR)
    assert sc.status(sh.G1).open is True
    assert "167" in sc.chat("How many days in custody?").text
    assert sc.events(EventKind.GATE_APPROVED) == []


# ---- the chat leaves a clean trace --------------------------------------------------------------------------------------
def test_chat_calls_only_tools_sutradhar_may_call_and_logs_each_call(tmp_path, monkeypatch):
    """Plan §3.3: each tool call is a TOOL_CALL then a TOOL_RESULT by SUTRADHAR, from its allow-list; the chips match the calls."""
    sc = chat_case(tmp_path, monkeypatch, [("custody", CUSTODY_ANSWER)])
    msg = sc.chat("How many days in custody?")
    calls = sc.events(EventKind.TOOL_CALL)
    assert calls and len(calls) == len(sc.events(EventKind.TOOL_RESULT))
    assert {sh._actor(e) for e in calls} == {AgentName.SUTRADHAR.value}
    assert {e.tool for e in calls} <= set(tools_yaml()["sutradhar"])
    assert {c.tool for c in msg.chips} <= {e.tool for e in calls}


def test_chat_does_not_change_the_case_record(tmp_path, monkeypatch):
    """A question writes no dossier field, approves no gate and exports nothing."""
    sc = chat_case(tmp_path, monkeypatch, [("custody", CUSTODY_ANSWER)])
    before = len(sc.events(EventKind.STORE_WRITE))
    sc.chat("How many days in custody?")
    assert len(sc.events(EventKind.STORE_WRITE)) == before
    assert sc.toolbox.exports == [] and sh.agent_approvals(sc.events()) == []


def test_chat_store_queries_are_bounded_by_the_case_date(tmp_path, monkeypatch):
    """Plan §2: every shared-store query carries the case date as `before`, also for a chat question."""
    sc = chat_case(tmp_path, monkeypatch, [("parity", "DLHC-2022-1187 para 14 [search_reasoning]")])
    sc.chat("Any SC case on parity in a cheating case?")
    calls = sc.world.stores[StoreName.CASELAW_REASONING].calls
    assert calls and all(kw["before"] == sh.AS_OF for _, kw in calls)


# ---- predictions are refused ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("question", ss.PREDICTION_QUESTIONS[:3])
def test_a_prediction_is_refused_without_calling_any_tool(tmp_path, monkeypatch, question):
    """Plan §1.3, §6.4: refused, flagged, no chips, no tool call, no number in the text."""
    sc = chat_case(tmp_path, monkeypatch)
    msg = sc.chat(question)
    assert msg.refused is True and msg.chips == [] and msg.text.strip()
    assert sc.toolbox.calls == [] and not sh.PROBABILITY_RE.search(msg.text)


def test_a_legitimate_question_with_bail_and_granted_in_it_is_still_answered(tmp_path, monkeypatch):
    """The refusal is specific, not blanket (a refuse-everything bot would fail the first flow)."""
    sc = chat_case(tmp_path, monkeypatch, [("parity", "DLHC-2022-1187 para 14 [search_reasoning]")])
    assert sc.chat(ss.LEGITIMATE_QUESTIONS[2]).refused is False


# ---- over HTTP ----------------------------------------------------------------------------------------------------------
def test_chat_round_trip_over_http(tmp_path, monkeypatch):
    """POST the question, get the agent's message with chips; GET the history: counsel then agent, in order, distinct ids."""
    sc = chat_case(tmp_path, monkeypatch, [("custody", CUSTODY_ANSWER)])
    client = sc.client()
    msg = client.post(f"/api/cases/{CASE}/chat", json={"text": "How many days in custody?"}).json()
    assert msg["agent"] == AgentName.SUTRADHAR.value and {c["tool"] for c in msg["chips"]} >= {"get_timeline", "date_calc"}
    history = client.get(f"/api/cases/{CASE}/chat").json()
    assert [m["role"] for m in history] == ["counsel", "agent"] and len({m["message_id"] for m in history}) == 2


# ---- real 14B (laptop or Ada only) ------------------------------------------------------------------------------------
@pytest.mark.models
@pytest.mark.gpu
def test_real_model_answers_the_custody_question_from_the_tool_results(tmp_path, monkeypatch):
    """With the real Ada model the custody answer states 167 days and names its sources; the same refusal for a prediction."""
    sc = sh.Scenario(tmp_path, monkeypatch, real_models=True)
    sc.with_case_state()
    msg = sc.chat("How many days in custody?")
    assert "167" in msg.text and {c.tool for c in msg.chips} >= {"get_timeline", "date_calc"}
    assert sc.chat("Will my client get bail?").refused is True
