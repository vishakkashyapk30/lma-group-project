"""BaseAgent.call_tool and emit (plan §3.3): allow-list, budget charge, TOOL_CALL then TOOL_RESULT, one Event per action."""

from __future__ import annotations

import pytest

from tests.fakes.toolbox import leaked_names
from tests.unit.agents._helpers import SpyBudget, build_agent, is_denied, tool_specs
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.schemas.enums import AgentName, EventKind


def test_allowed_call_appends_call_then_result_and_returns_the_value():
    """An allowed call returns the tool's value and logs TOOL_CALL then TOOL_RESULT carrying the tool name and inputs."""
    agent, ctx, toolbox = build_agent(AbhiyojakAgent)
    value = agent.call_tool("get_fact", case_id="case-0007", field="arrest_date")
    assert value.value == "2024-08-20"
    assert [e.kind for e in ctx.log.events] == [EventKind.TOOL_CALL, EventKind.TOOL_RESULT]
    call, result = ctx.log.events
    assert call.tool == result.tool == "get_fact"
    assert call.actor == AgentName.ABHIYOJAK
    assert call.inputs == {"case_id": "case-0007", "field": "arrest_date"}
    assert result.parent_id == call.event_id  # causal link used by truth maintenance
    assert toolbox.count("get_fact") == 1


@pytest.mark.parametrize(
    "agent_cls, tool, kwargs",
    [
        (AbhiyojakAgent, "export", {"case_id": "case-0007", "format": "DOCX"}),  # Abhiyojak never exports
        (AbhiyojakAgent, "get_timeline", {"case_id": "case-0007"}),  # not in its isolated tool list (plan §9)
        (AbhiyojakAgent, "search_arguments", {"query": "parity", "before": "2025-02-03"}),  # defence bank hidden from it
        (MunshiAgent, "search_reasoning", {"query": "parity", "before": "2025-02-03"}),  # Munshi has no case-law access
        (PeshkarAgent, "export", {"case_id": "case-0007", "format": "DOCX"}),
        (VakeelAgent, "ocr_page", {"file_path": "x.pdf", "page": 1}),
        (AbhiyojakAgent, "no_such_tool", {}),
    ],
)
def test_tool_outside_the_allow_list_is_refused_without_running_or_logging_a_result(agent_cls, tool, kwargs):
    """A tool not in the agent's configs/tools.yaml list is refused, never executed, and leaves no TOOL_RESULT."""
    agent, ctx, toolbox = build_agent(agent_cls, toolbox=None)
    # ASSUMPTION: refusal = PermissionError, or a returned ToolError; is_denied accepts both.
    assert is_denied(agent.call_tool, tool, **kwargs)
    assert toolbox.count(tool) == 0
    assert toolbox.exports == []
    assert [e for e in ctx.log.events if e.kind == EventKind.TOOL_RESULT] == []


def test_gate_open_toolbox_still_cannot_be_used_to_export_by_a_non_vakeel_agent():
    """Even when Gate 2 is approved, the allow-list (not just the gate) stops Abhiyojak exporting."""
    from tests.fakes.data import build_world
    from tests.fakes.toolbox import FakeToolbox

    toolbox = FakeToolbox(build_world(), gate2_approved=True)
    agent, _, _ = build_agent(AbhiyojakAgent, toolbox=toolbox)
    assert is_denied(agent.call_tool, "export", case_id="case-0007", format="DOCX")
    assert toolbox.exports == []


@pytest.mark.parametrize(
    "tool, kwargs, is_store_call",
    [
        ("search_objections", {"query": "parity", "before": "2025-02-03"}, True),
        ("get_statute", {"code": "BNS", "section": "318(4)"}, True),
        ("get_fact", {"case_id": "case-0007", "field": "sections"}, True),
    ],
)
def test_allowed_store_call_charges_one_store_call(tool, kwargs, is_store_call):
    """A call that touches a store charges exactly one store call to the budget."""
    # ASSUMPTION: BaseAgent charges store_calls=1 for tools whose SPEC.stores is non-empty, 0 otherwise.
    assert bool(tool_specs()[tool].stores) is is_store_call
    budget = SpyBudget()
    agent, _, _ = build_agent(AbhiyojakAgent, budgets=budget)
    agent.call_tool(tool, **kwargs)
    assert budget.store_calls_charged == 1


def test_tool_without_a_store_charges_no_store_call():
    """A pure tool (date_calc has a timeline spec, so use Vakeel's check_claim) charges no store call."""
    budget = SpyBudget()
    agent, _, _ = build_agent(VakeelAgent, budgets=budget)
    assert tool_specs()["check_claim"].stores == []
    agent.call_tool("check_claim", claim="Co-accused was granted bail", refs=[])
    assert budget.store_calls_charged == 0


def test_denied_call_charges_nothing():
    """A refused call costs nothing."""
    budget = SpyBudget()
    agent, _, _ = build_agent(AbhiyojakAgent, budgets=budget)
    assert is_denied(agent.call_tool, "export", case_id="case-0007", format="DOCX")
    assert budget.charges == []


def test_event_inputs_hold_pseudonymised_text_only(planted_names):
    """Plan §16: a raw planted name passed as a tool input never reaches the event log."""
    # ASSUMPTION: the agent pseudonymises inputs before logging, or refuses the call (ValueError/PermissionError).
    agent, ctx, _ = build_agent(AbhiyojakAgent)
    try:
        agent.call_tool("search_case_docs", case_id="case-0007", query="bail of Ramesh Kumar Yadav")
    except (ValueError, PermissionError):
        pass
    assert leaked_names([ctx.log.as_text()], planted_names) == []


def test_emit_appends_an_event_with_the_agent_as_actor():
    """emit() appends one Event (actor = the agent, this case) and returns it."""
    agent, ctx, _ = build_agent(PeshkarAgent)
    event = agent.emit(EventKind.AGENT_MESSAGE, {"text": "dossier ready for Gate 1"})
    assert ctx.log.events == [event]
    assert event.kind == EventKind.AGENT_MESSAGE
    assert event.actor == AgentName.PESHKAR
    assert event.case_id == "case-0007"
    # ASSUMPTION: the payload is stored in the event's inputs or outputs.
    assert {**event.inputs, **event.outputs}.get("text") == "dossier ready for Gate 1"


def test_emit_events_are_ordered_and_have_distinct_ids():
    """Successive emits give distinct event ids in append order."""
    agent, ctx, _ = build_agent(VakeelAgent)
    a = agent.emit(EventKind.AGENT_MESSAGE, {"n": 1})
    b = agent.emit(EventKind.AGENT_MESSAGE, {"n": 2})
    assert a.event_id != b.event_id
    assert [e.event_id for e in ctx.log.events] == [a.event_id, b.event_id]
