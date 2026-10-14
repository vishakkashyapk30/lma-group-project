"""Decline sexual-offence, POCSO and juvenile matters at intake (plan §16 'Sensitive matters').

The law protects the identity of victims and children: BNS s.72, POCSO s.23, JJ Act s.74. `is_declined_matter`
returns (declined, reason) and the reason names the protecting provision.
ASSUMPTION: sections are free strings in either order ('BNS 64' or '64 BNS', as in dossier `as_written`); the BNS
sexual-offence range is s.63-s.71 and IPC s.375-376 (with sub-letters).
"""

from __future__ import annotations

import pytest

from vakeel_sahayak.privacy.sensitive_matters import is_declined_matter


@pytest.mark.parametrize(
    "section",
    ["BNS 63", "BNS 64", "BNS 64(2)", "BNS 65(1)", "BNS 66", "BNS 69", "BNS 70(2)", "BNS 71", "64 BNS", "IPC 376", "IPC 376D", "376 IPC", "IPC 375"],
)
def test_sexual_offence_sections_are_declined_with_bns_72(section):
    """Plan §16: BNS 63-71 / IPC 375-376 are declined, citing BNS s.72."""
    declined, reason = is_declined_matter([section], ["FIR"])
    assert declined is True
    assert reason is not None
    assert "72" in reason and "BNS" in reason


@pytest.mark.parametrize("section", ["POCSO 4", "POCSO 6", "POCSO 12", "POCSO Act s.6", "Section 6 POCSO Act", "6 POCSO"])
def test_pocso_sections_are_declined_with_pocso_23(section):
    """Plan §16: any POCSO section is declined, citing POCSO s.23."""
    declined, reason = is_declined_matter([section], [])
    assert declined is True
    assert reason is not None
    assert "POCSO" in reason and "23" in reason


def test_juvenile_document_type_is_declined_with_jj_74():
    """Plan §16: a Juvenile Justice Board order document is declined, citing JJ Act s.74."""
    declined, reason = is_declined_matter(["BNS 318(4)"], ["FIR", "JUVENILE_BOARD_ORDER"])
    assert declined is True
    assert reason is not None
    assert "JJ Act" in reason and "74" in reason


@pytest.mark.parametrize("section", ["JJ Act 74", "JJ Act s.74", "JJ Act 15"])
def test_juvenile_act_sections_are_declined_with_jj_74(section):
    """Plan §16: JJ Act sections are declined, citing JJ Act s.74."""
    declined, reason = is_declined_matter([section], [])
    assert declined is True
    assert reason is not None
    assert "JJ Act" in reason and "74" in reason


@pytest.mark.parametrize(
    "section",
    ["BNS 318(4)", "IPC 420", "318(4) BNS", "BNS 303(2)", "BNS 62", "BNS 164", "BNS 363", "BNS 3(5)", "IPC 363", "NDPS 20"],
)
def test_ordinary_sections_are_not_declined(section):
    """Plan §16: ordinary offences (cheating etc.) and near-miss numbers (62, 164, 363) are not declined."""
    assert is_declined_matter([section], ["FIR", "REMAND_ORDER"]) == (False, None)


def test_empty_inputs_are_not_declined():
    """Plan §16: nothing to check -> (False, None)."""
    assert is_declined_matter([], []) == (False, None)


def test_mixed_list_declines_if_any_section_matches():
    """Plan §16: one sexual-offence section among ordinary ones declines the matter."""
    declined, reason = is_declined_matter(["BNS 318(4)", "BNS 64", "BNS 303(2)"], ["FIR"])
    assert declined is True
    assert "72" in reason


def test_mixed_list_declines_if_the_pocso_section_comes_first_or_last():
    """Plan §16: order in the list does not matter."""
    assert is_declined_matter(["POCSO 4", "BNS 318(4)"], [])[0] is True
    assert is_declined_matter(["BNS 318(4)", "POCSO 4"], [])[0] is True


def test_ordinary_sections_with_ordinary_documents_not_declined():
    """Plan §16: the document-type check only fires on juvenile documents."""
    assert is_declined_matter(["BNS 318(4)"], ["FIR", "ARREST_MEMO", "REMAND_ORDER", "BAIL_ORDER"]) == (False, None)
