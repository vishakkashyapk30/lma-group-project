"""Per-case triage card construction (plan §11 'Output: TriageCard', §7.3 case-0007 RightsReport).

`make_card` turns a RightsReport and a dossier into urgency reasons, flags and missing documents.
ASSUMPTIONS: a flag 'CHECK: antecedents unknown' is raised when the dossier's antecedents are not established (plan §11
example); an open default-bail window yields a reason naming 'default-bail' and its rule 'BNSS s.187(3)'; a statutory
bar yields a flag mentioning 'statutory bar'; the reasons mention the custody length ('167 days in custody').
"""

from __future__ import annotations

import re

from tests.fakes.data import load_dossier, load_rights_report
from vakeel_sahayak.agents.pairokar.triage import make_card
from vakeel_sahayak.schemas.enums import FieldStatus, RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.triage import TriageCard


def test_case_0007_card(expected_rights_report, dossier):
    """Plan §11: card for the worked example: missing docs carried through, antecedents flag, reasons present."""
    card = make_card("case-0007", expected_rights_report, dossier, ["custody certificate"])
    assert isinstance(card, TriageCard)
    assert card.case_id == "case-0007"
    assert card.missing_docs == ["custody certificate"]
    assert "CHECK: antecedents unknown" in card.flags
    assert card.reasons and all(isinstance(r, str) and r.strip() for r in card.reasons)


def test_case_0007_reasons_mention_the_custody_length(expected_rights_report, dossier):
    """Plan §7.3: case-0007 is 167 days in custody; the urgency reasons say so."""
    card = make_card("case-0007", expected_rights_report, dossier, [])
    assert any("167" in r for r in card.reasons)


def test_no_missing_documents_gives_empty_list(expected_rights_report, dossier):
    """Plan §11: nothing missing -> missing_docs is empty."""
    assert make_card("case-0007", expected_rights_report, dossier, []).missing_docs == []


def test_antecedents_flag_disappears_when_antecedents_are_established(expected_rights_report):
    """Plan §11: the 'antecedents unknown' flag is only for unknown antecedents."""
    d = load_dossier()
    d.fields.antecedents.value = []
    d.fields.antecedents.status = FieldStatus.USER_STATED
    card = make_card("case-0007", expected_rights_report, d, [])
    assert "CHECK: antecedents unknown" not in card.flags


def test_open_default_bail_window_becomes_an_urgency_reason(dossier):
    """Plan §11: 'Default-bail window ... (BNSS s.187(3))' is an urgency reason when the radar says ELIGIBLE."""
    rights = load_rights_report()
    for c in rights.checks:
        if c.check is RightsCheckName.DEFAULT_BAIL:
            c.status = RightsStatus.ELIGIBLE
            c.detail = "No charge sheet by day 61 (60-day limit). The default-bail window is open."
    card = make_card("case-0142", rights, dossier, ["custody certificate"])
    joined = " ".join(card.reasons)
    assert re.search(r"default[- ]bail", joined, re.I)
    assert "BNSS s.187(3)" in joined
    assert card.missing_docs == ["custody certificate"]


def test_closed_default_bail_window_is_not_reported_as_open(expected_rights_report, dossier):
    """Plan §7.3: case-0007's window is WINDOW_CLOSED, so no reason says the window is open or opens soon."""
    card = make_card("case-0007", expected_rights_report, dossier, [])
    assert not any(re.search(r"window (is open|opens)", r, re.I) for r in card.reasons)


def test_statutory_bar_is_flagged(dossier):
    """Plan §11: BAR_APPLIES shows on the card so the scheduler can move the case down."""
    rights = load_rights_report()
    for c in rights.checks:
        if c.check is RightsCheckName.STATUTORY_BAR:
            c.status = RightsStatus.BAR_APPLIES
    card = make_card("case-0201", rights, dossier, [])
    assert any("statutory bar" in t.lower() for t in card.flags + card.reasons)


def test_no_statutory_bar_no_bar_flag(expected_rights_report, dossier):
    """Plan §7.3: statutory_bar NOT_APPLICABLE raises no bar flag."""
    card = make_card("case-0007", expected_rights_report, dossier, [])
    assert not any("statutory bar" in t.lower() for t in card.flags + card.reasons)
