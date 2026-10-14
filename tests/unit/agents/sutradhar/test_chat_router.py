"""Chat routing (plan §6.4): which tool answers which counsel question; predictions and lay advice are refused."""

from __future__ import annotations

import pytest

from tests.unit.agents._helpers import route_or_refuse, tools_yaml
from vakeel_sahayak.agents.sutradhar.chat_router import CHAT_ROUTES, route_question


def test_chat_routes_table_matches_plan_6_4():
    """The routing table is exactly the plan §6.4 table."""
    assert CHAT_ROUTES == {
        "custody_days": ["get_timeline", "date_calc"],
        "section_equivalent": ["map_section"],
        "eligibility": ["rights_check"],
        "precedent_search": ["search_reasoning", "citations"],
        "what_did_court_say": ["search_case_docs"],
        "how_state_opposes": ["search_objections", "get_statute"],
    }


def test_every_routed_tool_is_in_sutradhars_allow_list():
    """Chat routes only use tools Sutradhar may call (configs/tools.yaml)."""
    allowed = set(tools_yaml()["sutradhar"])
    for tools in CHAT_ROUTES.values():
        assert set(tools) <= allowed


ROUTED = [
    ("How many days in custody?", {"get_timeline", "date_calc"}),
    ("BNS equivalent of 420 IPC?", {"map_section"}),
    ("Is my client eligible under s.479?", {"rights_check"}),
    ("Any SC case on parity in a cheating case?", {"search_reasoning", "citations"}),
    ("What did the Sessions Court say about antecedents?", {"search_case_docs"}),
]


@pytest.mark.parametrize("question, tools", ROUTED)
def test_example_questions_route_to_their_tools(question, tools):
    """Each plan §6.4 example goes to exactly its tools, and nothing else (no 'query everything')."""
    # ASSUMPTION: exact tool set per class (order not fixed).
    assert set(route_question(question)) == tools


def test_ndps_opposition_question_routes_to_objections_and_statutes():
    """'How does the State usually oppose bail in NDPS cases?' -> objection bank + statute text."""
    routed = set(route_question("How does the State usually oppose bail in NDPS cases?"))
    assert "search_objections" in routed
    assert routed & {"get_statute", "search_statutes"}
    assert routed <= {"search_objections", "get_statute", "search_statutes"}


@pytest.mark.parametrize(
    "question, tool",
    [
        ("How many days has the accused been in custody so far?", "date_calc"),  # ASSUMPTION: keyword routing, paraphrases
        ("What is the equivalent of section 406 IPC in the BNS?", "map_section"),
        ("Does he qualify for bail under section 479 BNSS?", "rights_check"),
        ("Show me what the Sessions Court said about parity", "search_case_docs"),
    ],
)
def test_paraphrases_route_to_the_same_tool(question, tool):
    """Paraphrases of the plan's examples still reach the right tool."""
    assert tool in route_question(question)


REFUSED = [
    "Will my client get bail?",
    "What are the chances of bail?",
    "what is the grant rate in Delhi HC for 420",
    "predict the outcome",
    "I am the accused, what should I do?",
    "Can I run away from the police?",
]


@pytest.mark.parametrize("question", REFUSED)
def test_predictions_and_lay_advice_are_refused(question):
    """Outcome predictions, grant rates and lay advice route to no tool at all (plan §6.4, §1.3)."""
    # ASSUMPTION: a refusal is an empty list, or a Refusal/ValueError exception; route_or_refuse accepts both.
    assert route_or_refuse(route_question, question) == []


@pytest.mark.parametrize("question", REFUSED)
def test_a_refusal_never_reaches_a_store_tool(question):
    """A refused question must not trigger even a harmless-looking search."""
    routed = set(route_or_refuse(route_question, question))
    store_tools = {t for tools in CHAT_ROUTES.values() for t in tools}
    assert not routed & store_tools


def test_refusal_is_specific_not_blanket():
    """A legitimate question with 'granted' or 'bail' in it is still answered (parity authorities are about grants)."""
    assert route_or_refuse(route_question, "Any SC case on parity in a cheating case where bail was granted?") != []
