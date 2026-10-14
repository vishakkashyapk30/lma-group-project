"""Vakeel step 1, drafting (plan §8.1): [F:field] and [A:doc#para] citations, ids-only model output, citation text
rendered from corpus metadata, invented authorities flagged."""

from __future__ import annotations

import re

import pytest

from tests.unit.agents._helpers import build_agent, make_state
from tests.unit.agents.vakeel._scripts import (
    SUPPORTED_G1,
    SUPPORTED_G2,
    ground_llm,
    model_ground,
    pack,
)
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.schemas.dossier import DossierFields
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor

FACT_TAG = re.compile(r"\[F:([a-z_]+)\]")
AUTH_TAG = re.compile(r"\[A:([A-Za-z0-9\-]+)#(\d+)\]")
PARITY, CHARGE = Factor.PARITY_WITH_CO_ACCUSED, Factor.CHARGE_SHEET_FILED


@pytest.fixture()
def state(dossier, expected_rights_report):
    return make_state(dossier, expected_rights_report)


@pytest.fixture()
def packs(paragraphs):
    return [pack(PARITY, paragraphs, [("DLHC-2022-1187", 14)]), pack(CHARGE, paragraphs, [("SC-2014-0463", 21)])]


def draft(state, packs, *model_grounds):
    agent, ctx, toolbox = build_agent(VakeelAgent, llm=ground_llm(*model_grounds))
    return agent, ctx, toolbox, agent.draft_grounds(state, packs)


def two_grounds():
    return (
        model_ground("G1", "parity_with_co_accused", SUPPORTED_G1, [("DLHC-2022-1187", 14)]),
        model_ground("G2", "charge_sheet_filed", SUPPORTED_G2, [("SC-2014-0463", 21)]),
    )


def test_one_ground_per_chosen_factor_in_pack_order(state, packs):
    """Two packs give two grounds, G1 and G2, for those factors in that order."""
    *_, grounds = draft(state, packs, *two_grounds())
    assert [(g.id, g.factor) for g in grounds] == [("G1", PARITY), ("G2", CHARGE)]


def test_every_ground_cites_dossier_fields_and_retrieved_authorities(state, packs):
    """Each argument carries at least one [F:field] over a real dossier field and one [A:doc#para] tag."""
    *_, grounds = draft(state, packs, *two_grounds())
    fields = set(DossierFields.model_fields)
    for g in grounds:
        facts = FACT_TAG.findall(g.argument)
        auths = AUTH_TAG.findall(g.argument)
        assert facts and set(facts) <= fields, g.argument
        assert auths, g.argument
        assert {(a.doc_id, str(a.para)) for a in g.authorities} == set(auths)


def test_authority_citation_is_rendered_from_corpus_metadata(state, packs):
    """Authority.citation equals the render_citation tool output for that doc and paragraph."""
    agent, ctx, toolbox = build_agent(VakeelAgent, llm=ground_llm(*two_grounds()))
    expected = toolbox.tools["render_citation"]("DLHC-2022-1187", 14)
    toolbox.calls.clear()
    grounds = agent.draft_grounds(state, packs)
    assert grounds[0].authorities[0].citation == expected
    assert toolbox.count("render_citation") >= 1


def test_model_written_citation_text_is_never_used(state, packs):
    """Even if the model emits its own citation string, the stored one is rendered from metadata."""
    scripted = model_ground("G1", "parity_with_co_accused", SUPPORTED_G1, [("DLHC-2022-1187", 14)], citation="Bogus v. State (2099) 1 SCC 1")
    agent, ctx, toolbox = build_agent(VakeelAgent, llm=ground_llm(scripted, two_grounds()[1]))
    grounds = agent.draft_grounds(state, packs)
    assert "Bogus" not in grounds[0].authorities[0].citation
    assert grounds[0].authorities[0].citation == toolbox.tools["render_citation"]("DLHC-2022-1187", 14)


def test_invented_case_name_in_the_argument_is_flagged_needs_review(state, packs):
    """An argument naming a case the corpus never produced is flagged NEEDS_REVIEW, and the ground stays in the list."""
    # ASSUMPTION: a 'X v. Y (year)' mention that is not backed by an [A:...] tag is treated as an invented authority.
    invented = SUPPORTED_G1 + " as held in Rajesh Kumar v. State of Delhi (2019) 5 SCC 100"
    agent, _, _, grounds = draft(
        state, packs, model_ground("G1", "parity_with_co_accused", invented, [("DLHC-2022-1187", 14)]), two_grounds()[1]
    )
    checked = agent.check_claims(grounds)
    assert len(checked) == 2
    assert checked[0].check == ClaimCheck.NEEDS_REVIEW
    assert checked[1].check == ClaimCheck.SUPPORTED  # the honest ground is not collateral damage


def test_unretrieved_citation_is_flagged_never_silently_kept(state, packs):
    """A [A:doc#para] that appears in no evidence pack (and not in the corpus) makes the ground NEEDS_REVIEW."""
    fake = "Co-accused with an identical role has been enlarged on bail [F:co_accused_bail] [A:DLHC-9999-0001#3]"
    agent, _, _, grounds = draft(
        state, packs, model_ground("G1", "parity_with_co_accused", fake, [("DLHC-9999-0001", 3)]), two_grounds()[1]
    )
    checked = agent.check_claims(grounds)
    assert [g.id for g in checked] == ["G1", "G2"]
    assert checked[0].check == ClaimCheck.NEEDS_REVIEW
    assert checked[1].check == ClaimCheck.SUPPORTED


def test_real_but_unretrieved_paragraph_is_flagged(state, paragraphs):
    """SC-2014-0463#21 exists in the corpus but was not retrieved for this factor's pack: citing it is flagged."""
    # ASSUMPTION: Vakeel remembers which paragraphs the packs it was handed contained (same agent instance).
    only_parity = [pack(PARITY, paragraphs, [("DLHC-2022-1187", 14)])]
    arg = "Once the charge sheet is filed custodial interrogation is no longer required [F:charge_sheet] [A:SC-2014-0463#21]"
    agent, _, _, grounds = draft(state, only_parity, model_ground("G1", "parity_with_co_accused", arg, [("SC-2014-0463", 21)]))
    assert agent.check_claims(grounds)[0].check == ClaimCheck.NEEDS_REVIEW


def test_retrieved_and_supported_ground_is_marked_supported(state, packs):
    """The control case: retrieved authority, supported text, good law -> SUPPORTED."""
    agent, _, _, grounds = draft(state, packs, *two_grounds())
    assert [g.check for g in agent.check_claims(grounds)] == [ClaimCheck.SUPPORTED, ClaimCheck.SUPPORTED]
