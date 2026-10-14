"""Vakeel assemble_brief (plan §8.1, §10): dependencies, statutory position, open issues, nothing dropped."""

from __future__ import annotations

import re

import pytest

from tests.unit.agents._helpers import build_agent, make_ground, make_state
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, SUPPORTED_G2
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief
from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    ClaimState,
    Factor,
    GoodLawStatus,
    OpenIssueType,
    TransferFlag,
)
from vakeel_sahayak.truth_maintenance.dependencies import hash_value

FACT_TAG = re.compile(r"\[F:([a-z_]+)\]")


def grounds_for_brief():
    g1 = make_ground("G1", Factor.PARITY_WITH_CO_ACCUSED, SUPPORTED_G1 + " [F:sections]", [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED)
    g2 = make_ground("G2", Factor.CHARGE_SHEET_FILED, SUPPORTED_G2, [("SC-2014-0463", 21)], check=ClaimCheck.REPAIRED)
    g3 = make_ground("G3", Factor.GRAVITY_AND_PUNISHMENT,
                     "The role attributed to the petitioner distinguishes him from the co-accused [F:sections] [A:DLHC-2023-0911#12]",
                     [("DLHC-2023-0911", 12)], check=ClaimCheck.NEEDS_REVIEW)
    g4 = make_ground("G4", Factor.CUSTODY_PERIOD, "Prolonged custody without trial weighs in favour of bail [F:custody_days] [A:DLHC-2021-0420#11]",
                     [("DLHC-2021-0420", 11)], check=ClaimCheck.SUPPORTED)
    g5 = make_ground("G5", Factor.TRIAL_DELAY, "Delay in trial; Article 21 [F:trial_stage] [A:BOMHC-2024-0355#8]",
                     [("BOMHC-2024-0355", 8)], check=ClaimCheck.SUPPORTED)
    g3.authorities[0] = Authority(doc_id="DLHC-2023-0911", para=12, good_law=GoodLawStatus.OVERRULED)
    g4.authorities[0] = Authority(doc_id="DLHC-2021-0420", para=11, transfer=TransferFlag.CHANGED, good_law=GoodLawStatus.OK)
    g5.authorities[0] = Authority(doc_id="BOMHC-2024-0355", para=8, good_law=GoodLawStatus.DISTINGUISHED)
    return [g1, g2, g3, g4, g5]


@pytest.fixture()
def assemble(dossier, expected_rights_report):
    """A callable running assemble_brief (so a missing implementation fails inside the test, not in fixture setup)."""

    def _assemble() -> BailBrief:
        # ASSUMPTION: assemble_brief completes the brief carried in state.brief (grounds already drafted and checked).
        agent, _, _ = build_agent(VakeelAgent)
        state = make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=grounds_for_brief()))
        return agent.assemble_brief(state)

    return _assemble


def test_all_grounds_survive_unchanged_in_text_and_order(assemble):
    """Assembly drops nothing and rewrites nothing: five grounds, same ids, order and argument text, still CURRENT."""
    brief = assemble()
    originals = grounds_for_brief()
    assert [g.id for g in brief.grounds] == [g.id for g in originals]
    assert [g.argument for g in brief.grounds] == [g.argument for g in originals]
    assert all(g.state == ClaimState.CURRENT for g in brief.grounds)


def test_statutory_position_for_case_0007(assemble):
    """BNS 318(4) (≈ IPC 420), not bailable, maximum 7 years (plan §8.1 example)."""
    brief = assemble()
    pos = brief.statutory_position
    assert pos.sections == ["BNS 318(4) (≈ IPC 420)"]
    assert pos.bailable is False
    assert pos.max_punishment == "7 years"
    assert pos.rights and "default" in pos.rights.lower()  # summarises the RightsReport: default-bail window closed


def test_label_is_the_fixed_disclaimer(assemble):
    """The assembled brief keeps the constant label."""
    brief = assemble()
    assert brief.label == "AI-generated draft. Not legal advice."


def test_depends_on_holds_a_hash_of_every_cited_fact(assemble, dossier):
    """Each [F:field] in a ground's text appears in depends_on.facts with hash_value of the dossier value."""
    brief = assemble()
    # ASSUMPTION: the hash is taken over the JSON-mode value of the tracked field.
    for g in brief.grounds:
        cited = set(FACT_TAG.findall(g.argument))
        assert set(g.depends_on.facts) == cited
        for field, digest in g.depends_on.facts.items():
            value = dossier.fields.model_dump(mode="json")[field]["value"]
            assert digest == hash_value(value)
            assert re.fullmatch(r"h:[0-9a-f]{4}", digest)


def test_depends_on_lists_authorities_as_doc_hash_para(assemble):
    """depends_on.authorities holds 'doc_id#para' for each cited authority (plan §10)."""
    brief = assemble()
    assert brief.grounds[0].depends_on.authorities == ["DLHC-2022-1187#14"]
    assert brief.grounds[1].depends_on.authorities == ["SC-2014-0463#21"]


def test_changed_provision_becomes_an_open_issue(assemble):
    """An authority whose transfer flag is CHANGED yields a CHANGED_PROVISION issue naming it (plan §8.1 example)."""
    brief = assemble()
    issues = [i for i in brief.open_issues if i.type == OpenIssueType.CHANGED_PROVISION]
    assert len(issues) == 1 and "DLHC-2021-0420" in issues[0].item


def test_overruled_authority_is_flagged_for_counsel(assemble):
    """An OVERRULED authority and a NEEDS_REVIEW ground produce a NEEDS_REVIEW issue that warns about it."""
    brief = assemble()
    # ASSUMPTION: the warning is a NEEDS_REVIEW open issue whose text names the ground or the doc and says 'overruled'.
    issues = [i for i in brief.open_issues if i.type == OpenIssueType.NEEDS_REVIEW]
    assert any("DLHC-2023-0911" in i.item and "overruled" in i.item.lower() for i in issues)
    assert any("G3" in i.item for i in issues)


def test_distinguished_authority_is_not_a_blocking_issue(assemble):
    """DISTINGUISHED is shown on the authority but raises no open issue."""
    brief = assemble()
    assert not any("BOMHC-2024-0355" in i.item for i in brief.open_issues)


def test_unknown_antecedents_are_an_open_question(assemble):
    """The dossier's antecedents field is UNSUPPORTED: counsel is asked to confirm (plan §8.1 example)."""
    brief = assemble()
    assert any(i.type == OpenIssueType.NEEDS_REVIEW and "antecedent" in i.item.lower() for i in brief.open_issues)


def test_clean_supported_grounds_raise_no_issue(assemble):
    """G1 and G2 are fine: no open issue names them."""
    brief = assemble()
    for i in brief.open_issues:
        assert "G1" not in i.item.split() and "DLHC-2022-1187" not in i.item
