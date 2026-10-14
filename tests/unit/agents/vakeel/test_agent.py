"""VakeelAgent class facts (pass today) and chat-independent behaviour (plan §3.2, §8)."""

from __future__ import annotations

import inspect

import pytest

from tests.unit.agents._helpers import build_agent, make_ground, make_state, models_yaml
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, ground_llm, model_ground
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, Factor
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround, SparringRecord


def test_class_facts():
    """Vakeel is a concrete BaseAgent named VAKEEL on the shared 14B agents model."""
    assert issubclass(VakeelAgent, BaseAgent) and not inspect.isabstract(VakeelAgent)
    assert VakeelAgent.NAME == AgentName.VAKEEL
    assert VakeelAgent.ROLE_MODEL == "agents_14b"
    assert "vakeel" in models_yaml()["llm"]["agents_14b"]["used_by"]


@pytest.mark.parametrize(
    "method", ["run", "draft_grounds", "reply_to_objections", "check_claims", "repair_or_flag", "assemble_brief", "build_hearing_card"]
)
def test_method_exists(method):
    """The plan §8.1 drafting-loop steps exist as methods."""
    assert callable(getattr(VakeelAgent, method))


def test_brief_label_is_the_fixed_constant():
    """The brief label is the fixed disclaimer of plan §8.1."""
    assert BailBrief(case_id="case-0007").label == "AI-generated draft. Not legal advice."


def test_reply_to_objections_renders_citations_and_checks_each_reply(dossier, expected_rights_report):
    """Replies follow the same rules as grounds: authorities rendered from metadata, check set, one reply per objection."""
    reply = {"text": "Parity applies: Co-accused with an identical role has been enlarged on bail", "authorities": [{"doc_id": "DLHC-2022-1187", "para": 14}]}
    # ASSUMPTION: a reply is requested with the schema title 'Reply' (ids only) and one call per objection.
    from tests.fakes.models import ScriptedLLM

    agent, ctx, toolbox = build_agent(VakeelAgent, llm=ScriptedLLM(by_schema={"Reply": reply}, strict=False, default=""))
    objection = Objection(
        id="O1", against="G1", factor="parity_with_co_accused",
        objection="The applicant, unlike Co-accused-1, received the money into his own account.",
        grounds=[ObjectionGround(store="advocacy.objections", doc_id="DLHC-2023-0911", para=6)],
    )
    replies = agent.reply_to_objections(make_state(dossier, expected_rights_report), [objection])
    assert len(replies) == 1
    rendered = toolbox.tools["render_citation"]("DLHC-2022-1187", 14)
    assert replies[0].authorities[0].citation == rendered
    assert replies[0].check in set(ClaimCheck)


def test_build_hearing_card_has_the_four_blocks_and_no_prediction(dossier, expected_rights_report):
    """Vakeel's card carries bench concerns, lead points, conditions and open issues, and no grant-rate text."""
    from tests.unit.agents._helpers import dumps

    g = make_ground("G1", Factor.PARITY_WITH_CO_ACCUSED, SUPPORTED_G1, [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED)
    state = make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=[g]))
    state = state.model_copy(update={"sparring": SparringRecord(case_id="case-0007", rounds=2)})
    agent, _, _ = build_agent(VakeelAgent, llm=ground_llm(model_ground("G1", "parity_with_co_accused", SUPPORTED_G1, [])))
    card = agent.build_hearing_card(state)
    # ASSUMPTION: card keys as in export.hearing_card (see tests/unit/export/test_hearing_card.py CARD_KEYS).
    assert {"bench_concerns", "lead_with", "conditions", "open_issues"} <= set(card)
    text = dumps(card).lower()
    assert "grant rate" not in text and "likely to be granted" not in text
