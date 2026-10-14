"""Abhiyojak context isolation (plan §9): own stores only; grounds and dossier in, Vakeel's plan and notes out."""

from __future__ import annotations

import pytest

from tests.unit.agents._helpers import dumps, make_ground, make_state, tool_specs, tools_yaml
from vakeel_sahayak.agents.abhiyojak.isolation import VISIBLE_STORES, build_context
from vakeel_sahayak.schemas.bail_brief import BailBrief, OpenIssue
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, OpenIssueType, StoreName

SECRET = "VAKEEL_PRIVATE_NOTE"


def test_visible_stores_are_the_three_prosecution_side_stores():
    """Plan §9: advocacy.objections, refusal reasoning in caselaw.reasoning, and law.statutes."""
    assert VISIBLE_STORES == ["advocacy.objections", "caselaw.reasoning", "law.statutes"]
    assert all(StoreName(s) for s in VISIBLE_STORES)


def test_abhiyojak_tools_only_reach_its_stores_plus_case_facts_and_docs():
    """configs/tools.yaml: every abhiyojak tool reads only visible stores, case.facts or case.docs."""
    allowed = {StoreName(s) for s in VISIBLE_STORES} | {StoreName.CASE_FACTS, StoreName.CASE_DOCS}
    specs = tool_specs()
    tools = tools_yaml()["abhiyojak"]
    assert tools
    for t in tools:
        assert set(specs[t].stores) <= allowed, t


def test_abhiyojak_has_no_defence_bank_no_export_no_citation_graph():
    """It cannot read the defence argument bank, Vakeel's drafting tools, or export."""
    tools = set(tools_yaml()["abhiyojak"])
    assert not tools & {"search_arguments", "similar_orders", "get_paragraph", "check_claim", "render_citation", "export",
                        "assemble_application", "citations", "good_law_check"}


@pytest.fixture()
def grounds():
    return [
        make_ground("G1", Factor.PARITY_WITH_CO_ACCUSED, "Co-accused with an identical role has been enlarged on bail [F:co_accused_bail] [A:DLHC-2022-1187#14]",
                    [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED),
        make_ground("G2", Factor.CHARGE_SHEET_FILED, "Once the charge sheet is filed custodial interrogation is no longer required [F:charge_sheet] [A:SC-2014-0463#21]",
                    [("SC-2014-0463", 21)], check=ClaimCheck.REPAIRED),
    ]


def test_context_contains_grounds_with_cited_material_and_the_dossier(grounds, dossier, expected_rights_report):
    """The context carries every ground's text and authority ids and the dossier facts the prosecutor attacks."""
    state = make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=grounds))
    text = dumps(build_context(state))
    for g in grounds:
        assert g.argument in text
        assert g.id in text
        for a in g.authorities:
            assert a.doc_id in text
    assert "Co-accused-1" in text and "2024-12-05" in text  # dossier: co_accused_bail
    assert "318(4)" in text  # dossier: sections


@pytest.mark.parametrize("attr", ["vakeel_notes", "vakeel_plan", "plan", "notes", "retrieval_plan"])
def test_context_never_contains_vakeels_plan_or_notes(attr, grounds, dossier, expected_rights_report):
    """A marker placed in any Vakeel-side attribute of the state never appears in the prosecution context."""
    # ASSUMPTION: the state may carry Vakeel-side extras (attached with model_copy); none may leak into the context.
    state = make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=grounds), **{attr: f"{SECRET} {attr}"})
    assert SECRET not in dumps(build_context(state))


def test_context_does_not_show_vakeels_open_issues(grounds, dossier, expected_rights_report):
    """Vakeel's own open-issue notes (e.g. 'confirm antecedents') are not part of what the prosecutor sees."""
    # ASSUMPTION: plan §9 lists grounds, dossier and own stores only, so brief-level open issues are excluded.
    brief = BailBrief(case_id="case-0007", grounds=grounds,
                      open_issues=[OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item=f"{SECRET}: we are weak on antecedents")])
    state = make_state(dossier, expected_rights_report, brief=brief)
    assert SECRET not in dumps(build_context(state))


def test_context_is_plain_data(grounds, dossier, expected_rights_report):
    """The context is a JSON-serialisable dict (it becomes a prompt)."""
    import json

    state = make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=grounds))
    ctx = build_context(state)
    assert isinstance(ctx, dict)
    json.dumps(ctx)
