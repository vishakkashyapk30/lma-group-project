"""Vakeel steps 3-4 (plan §8.1): claim checks (transfer, good-law) and bounded repair; nothing is dropped silently."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.fakes.data import build_world
from tests.fakes.toolbox import FakeToolbox
from tests.unit.agents._helpers import build_agent, make_ground, make_state
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, UNSUPPORTED_G1, ground_llm, model_ground, pack, reword_llm
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    Factor,
    GoodLawStatus,
    StoreName,
    TransferFlag,
    Treatment,
)
from vakeel_sahayak.schemas.store_rows import CitationEdge

PARITY, CHARGE, CUSTODY, TRIAL, GRAVITY = (
    Factor.PARITY_WITH_CO_ACCUSED,
    Factor.CHARGE_SHEET_FILED,
    Factor.CUSTODY_PERIOD,
    Factor.TRIAL_DELAY,
    Factor.GRAVITY_AND_PUNISHMENT,
)

OVERRULED_ARG = "The role attributed to the petitioner distinguishes him from the co-accused [F:co_accused_bail] [A:DLHC-2023-0911#12]"
DISTINGUISHED_ARG = "Delay in trial; Article 21 [F:trial_stage] [A:BOMHC-2024-0355#8]"
CHANGED_ARG = "Prolonged custody without trial weighs in favour of bail [F:custody_days] [A:DLHC-2021-0420#11]"


def drafted_and_checked(paragraphs, dossier, rights, factor, argument, cited, world=None):
    """Draft one ground citing `cited` (retrieved in its pack), then run check_claims."""
    toolbox = FakeToolbox(world or build_world())
    llm = ground_llm(model_ground("G1", factor.value, argument, [cited]))
    agent, ctx, _ = build_agent(VakeelAgent, llm=llm, toolbox=toolbox)
    state = make_state(dossier, rights)
    grounds = agent.draft_grounds(state, [pack(factor, paragraphs, [cited])])
    return agent, agent.check_claims(grounds)


def test_overruled_authority_is_not_supported(paragraphs, dossier, expected_rights_report):
    """DLHC-2023-0911 is overruled by SC-2020-0100: the ground cannot be SUPPORTED and the flag is recorded."""
    _, grounds = drafted_and_checked(paragraphs, dossier, expected_rights_report, GRAVITY, OVERRULED_ARG, ("DLHC-2023-0911", 12))
    assert grounds[0].authorities[0].good_law == GoodLawStatus.OVERRULED
    assert grounds[0].check != ClaimCheck.SUPPORTED
    assert len(grounds) == 1  # shown to counsel, not removed


def test_distinguished_authority_is_shown_but_not_blocking(paragraphs, dossier, expected_rights_report):
    """A DISTINGUISHED authority keeps its flag and the ground stays SUPPORTED."""
    world = build_world()
    world.stores[StoreName.CASELAW_CITATIONS].edges.append(
        CitationEdge(citing_doc_id="DLHC-2024-0777", cited_doc_id="BOMHC-2024-0355", treatment=Treatment.DISTINGUISHED)
    )
    _, grounds = drafted_and_checked(paragraphs, dossier, expected_rights_report, TRIAL, DISTINGUISHED_ARG, ("BOMHC-2024-0355", 8), world)
    assert grounds[0].authorities[0].good_law == GoodLawStatus.DISTINGUISHED
    assert grounds[0].check == ClaimCheck.SUPPORTED


def test_good_authority_is_flagged_ok(paragraphs, dossier, expected_rights_report):
    """A clean authority is recorded as good law OK."""
    _, grounds = drafted_and_checked(paragraphs, dossier, expected_rights_report, PARITY, SUPPORTED_G1, ("DLHC-2022-1187", 14))
    assert grounds[0].authorities[0].good_law == GoodLawStatus.OK
    assert grounds[0].authorities[0].sc_root == "SC-2014-0463"  # the SC authority behind the HC paragraph (plan §5.3)


def test_ipc_authority_under_a_bns_charge_carries_the_changed_transfer_flag(paragraphs, dossier, expected_rights_report):
    """DLHC-2021-0420 interprets IPC 420 whose wording differs in BNS 318(4): transfer == CHANGED (plan §5.4, §8.1)."""
    # ASSUMPTION: the agent compares the paragraph's IPC section with the dossier's BNS section via transfer_check.
    _, grounds = drafted_and_checked(paragraphs, dossier, expected_rights_report, CUSTODY, CHANGED_ARG, ("DLHC-2021-0420", 11))
    assert grounds[0].authorities[0].transfer == TransferFlag.CHANGED


# ---- repair_or_flag --------------------------------------------------------------------------------------------------
def unsupported_ground(gid="G1", factor=PARITY):
    return make_ground(gid, factor, UNSUPPORTED_G1, [("DLHC-2022-1187", 14)], check=ClaimCheck.NEEDS_REVIEW)


def supported_ground(gid="G2"):
    return make_ground(gid, CHARGE, SUPPORTED_G1, [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED)


def test_unrepairable_claim_stays_in_the_brief_as_needs_review():
    """When rewording cannot make a claim supported it is flagged NEEDS_REVIEW and still present (nothing dropped)."""
    agent, _, _ = build_agent(VakeelAgent, llm=reword_llm(UNSUPPORTED_G1))
    out = agent.repair_or_flag([unsupported_ground(), supported_ground()])
    assert [g.id for g in out] == ["G1", "G2"]
    assert out[0].check == ClaimCheck.NEEDS_REVIEW
    assert out[1].check == ClaimCheck.SUPPORTED


def test_repairable_claim_is_reworded_to_what_the_source_supports():
    """A reword that the source supports turns the ground REPAIRED, after exactly one repair round."""
    llm = reword_llm(SUPPORTED_G1)
    agent, _, _ = build_agent(VakeelAgent, llm=llm)
    out = agent.repair_or_flag([unsupported_ground()])
    assert out[0].check == ClaimCheck.REPAIRED
    assert out[0].argument == SUPPORTED_G1
    assert len(llm.calls) == 1


def test_supported_claims_are_left_word_for_word():
    """Claims that already pass are not touched and cost no model call."""
    llm = reword_llm(SUPPORTED_G1)
    agent, _, _ = build_agent(VakeelAgent, llm=llm)
    ground = supported_ground()
    out = agent.repair_or_flag([ground])
    assert out[0].argument == ground.argument and out[0].check == ClaimCheck.SUPPORTED
    assert llm.calls == []


def test_at_most_two_repair_rounds():
    """A stubborn claim gets at most 2 reword attempts (configs/budgets.yaml repair_rounds: 2), then it is flagged."""
    llm = reword_llm(UNSUPPORTED_G1)
    agent, _, _ = build_agent(VakeelAgent, llm=llm)
    out = agent.repair_or_flag([unsupported_ground()])
    assert out[0].check == ClaimCheck.NEEDS_REVIEW
    assert 1 <= len(llm.calls) <= 2


def test_repair_round_limit_follows_the_budget_config():
    """The limit is read from budgets.repair_rounds, not hard-coded: with 1 round only one reword is attempted."""
    llm = reword_llm(UNSUPPORTED_G1)
    agent, ctx, _ = build_agent(VakeelAgent, llm=llm)
    ctx.config.budgets.repair_rounds = 1
    agent.repair_or_flag([unsupported_ground()])
    assert len(llm.calls) == 1


@settings(max_examples=25)
@given(pattern=st.lists(st.booleans(), min_size=1, max_size=6))
def test_repair_never_drops_a_claim_and_stays_bounded(pattern):
    """Property over random support patterns: grounds in == grounds out (ids and order), unsupported ones are
    NEEDS_REVIEW, supported ones stay SUPPORTED, model calls <= 2 per failing ground."""
    grounds = [
        supported_ground(f"G{i + 1}") if ok else unsupported_ground(f"G{i + 1}")
        for i, ok in enumerate(pattern)
    ]
    llm = reword_llm(UNSUPPORTED_G1)
    agent, _, toolbox = build_agent(VakeelAgent, llm=llm)
    out = agent.repair_or_flag(grounds)
    assert [g.id for g in out] == [g.id for g in grounds]
    for ok, g in zip(pattern, out):
        assert g.check == (ClaimCheck.SUPPORTED if ok else ClaimCheck.NEEDS_REVIEW)
    failing = pattern.count(False)
    assert len(llm.calls) <= 2 * failing
    # ASSUMPTION: each repair round re-checks once (check_claim), plus one initial check per ground.
    assert toolbox.count("check_claim") <= 3 * len(pattern)
