"""High Court caption names: the party named before 'W/o', 'S/o', 'R/o' or '@', glued words, 'Late X', and the boundary check after replacement."""

from __future__ import annotations

import re

import pytest

from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, detect_names, leaked_name_tokens, pseudonymise_text

CAPTION = (
    "MCRC No. 8355 of 2023\n\nSadhna Kushwaha, W/o Late Rakesh Roshan Kushwaha AgedAbout 36 Years Caste Koiri, R/o Village Banja, "
    "District : Surajpur, ChhattisgarhSadhna Kushwaha, W/o Late Rakesh Roshan Kushwaha AgedAbout 36 Years Caste Koiri, R/o Village Banja\n\n"
    "---- Applicant(in jail)\n\nVersus\n\nState Of Chhattisgarh Through The Station House Officer\n"
)


def _names(text: str) -> list[str]:
    return [s.text_of(text) for s in detect_names(text)]


def test_name_before_wife_of_marker_is_learned_and_removed() -> None:
    out, m = pseudonymise_text(CAPTION, "t1dev-017")
    for token in ("Sadhna", "Rakesh", "Roshan", "Kushwaha"):
        assert token not in out
    assert "Sadhna Kushwaha" in m.known_names() and "Rakesh Roshan Kushwaha" in m.known_names()
    assert re.search(r"Person-\d+, W/o Late Person-\d+", out)


def test_name_glued_to_previous_word_is_replaced_without_cutting_the_place() -> None:
    out, _ = pseudonymise_text(CAPTION, "t1dev-017")
    assert "Chhattisgarh Person-" in out  # the place stays, a space was put before the alias
    assert "State Of Chhattisgarh Through The Station House Officer" in out
    assert "Surajpur" in out and "Banja" in out


def test_late_and_titles_are_not_part_of_the_name() -> None:
    assert "Rakesh Roshan Kushwaha" in _names("Sadhna Kushwaha, W/o Late Rakesh Roshan Kushwaha Aged")
    assert "Ram Prasad" in _names("the deceased Late Ram Prasad was seen")
    assert "Sita Devi" in _names("Smt. Sita Devi appeared")


@pytest.mark.parametrize("marker", ["S/o", "D/o", "W/o", "S/O"])
def test_names_before_every_relation_marker(marker: str) -> None:
    assert "Munnu Lal" in [" ".join(n.split()) for n in _names(f"Munnu  Lal, {marker} Shri Hari,  Aged About 25 Years")]


def test_one_word_and_capital_names_before_a_marker() -> None:
    assert "Nitin" in _names("The Applicant, Nitin S/o Rakesh, resident of Harinagar")
    assert "AZAD HUSSAIN BARBHUIYA" in _names("\n\nAZAD HUSSAIN BARBHUIYA S/O GIASH UDDIN BARBHUIYA, VILL- TARAPUR")
    assert "GIASH UDDIN BARBHUIYA" in _names("AZAD HUSSAIN BARBHUIYA S/O GIASH UDDIN BARBHUIYA, VILL- TARAPUR")


def test_name_before_aged_without_a_marker() -> None:
    assert "AJMAL SHAH" in _names("AJMAL SHAH,AGED 19 YEARS")
    assert "Mukesh" in _names("Mukesh, Aged About 25 Years")
    assert _names("The accused is Aged 30 years") == []


def test_alias_names_with_at_sign() -> None:
    assert {"RAJENDRA", "RAJJAN"} <= set(_names("1.RAJENDRA @ RAJJAN S/O PARVAT SINGH LODHI,AGED ABOUT 42 YEARS"))


def test_name_glued_to_a_digit_or_after_year_text() -> None:
    out, _ = pseudonymise_text("Between:\n\n1Tapas Haldar, S/O Adir Haldar, Age.32", "c")
    assert "Tapas" not in out and "Haldar" not in out
    out, _ = pseudonymise_text("AJMAL SHAH,AGED 19 YEARSS/O AJAS, HASEENA MANZIL", "c")
    assert "AJMAL" not in out and "AJAS" not in out


def test_caption_words_and_legal_terms_are_not_names() -> None:
    text = "Accused No.7 in Crime No.305/2024. Aged About 25 Years, R/o Village Banja. At Present R/o Delhi. Police Station Kotwali."
    assert _names(text) == []
    out, _ = pseudonymise_text(text, "c")
    assert out == text


def test_consistency_check_finds_no_learned_token_after_replacement() -> None:
    out, m = pseudonymise_text(CAPTION, "t1dev-017")
    assert leaked_name_tokens(out, m) == []
    assert leaked_name_tokens("Sadhna was here", m) == ["Sadhna"]


def test_partial_name_left_behind_is_swept_to_the_alias() -> None:
    m = PseudonymMap()
    alias = m.alias_for("Sadhna Kushwaha", "person")
    out, _ = pseudonymise_text("Applicant Sadhna Kushwaha filed. Later Kushwaha said so.", "c", m)
    assert "Kushwaha" not in out and alias in out


def test_boundary_accepts_pseudonymised_caption_and_refuses_the_raw_one() -> None:
    out, m = pseudonymise_text(CAPTION, "t1dev-017")
    assert_pseudonymised({"facts_text": out}, m)
    with pytest.raises(PrivacyBoundaryError):
        assert_pseudonymised({"facts_text": CAPTION}, PseudonymMap())
