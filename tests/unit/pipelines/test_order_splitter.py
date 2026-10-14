"""Cue-phrase order splitter (plan §5.2 chunking, §15.1): facts, defense submissions, prosecution submissions, reasoning,
operative order. Orders that do not split cleanly are dropped (None)."""

from __future__ import annotations

import pytest

from vakeel_sahayak.pipelines.order_splitter import split_order
from vakeel_sahayak.schemas.enums import OrderPart as P

FACTS = ("Facts: The applicant seeks regular bail in FIR No. 112/2024 PS-1 registered under Section 318(4) BNS. "
         "It is alleged that he induced the complainant to part with Rs. 5 lakh on 10.08.2024. He was arrested on 20.08.2024 "
         "and has been in judicial custody since 21.08.2024.")
DEFENSE = ("Learned counsel for the petitioner submits that the applicant is innocent and has been falsely implicated. "
           "It is urged that the charge sheet has been filed and custodial interrogation is no longer required.")
PROSECUTION = ("Learned APP submits that the offence is serious and that the applicant may flee from justice. "
               "It is stated that the investigation revealed the applicant's role in the cheating.")
REASONING = ("Heard learned counsel for the parties and perused the record. Considered the rival submissions. "
             "The charge sheet has been filed, the applicant has remained in custody for a considerable period and the trial "
             "is not likely to conclude soon. The co-accused stands on a similar footing.")
OPERATIVE_ALLOWED = ("Accordingly, the bail application is allowed. The applicant shall furnish a personal bond of Rs. 50,000 "
                     "with one surety and shall surrender his passport.")
OPERATIVE_DISMISSED = "Accordingly, the bail application is dismissed. Nothing stated herein shall affect the trial."

HEADER = "IN THE HIGH COURT OF DELHI\nBAIL APPLN. 1234/2024\n"


def order(operative: str = OPERATIVE_ALLOWED, *, facts=FACTS, defense=DEFENSE, prosecution=PROSECUTION, reasoning=REASONING) -> str:
    return HEADER + "\n".join(p for p in (facts, defense, prosecution, reasoning, operative) if p)


@pytest.mark.parametrize("operative", [OPERATIVE_ALLOWED, OPERATIVE_DISMISSED], ids=["allowed", "dismissed"])
def test_clean_order_splits_into_five_parts(operative):
    """A clean order gives all five OrderPart keys, whether the bail is allowed or dismissed."""
    parts = split_order(order(operative))
    assert parts is not None
    assert set(parts) == {P.FACTS, P.DEFENSE, P.PROSECUTION, P.REASONING, P.OPERATIVE}


def test_each_part_holds_its_own_text_and_not_the_neighbours():
    """The cue phrases separate the parts: each contains its own marker sentence and none of the other parts' markers."""
    parts = split_order(order())
    assert "FIR No. 112/2024" in parts[P.FACTS] and "Learned counsel" not in parts[P.FACTS]
    assert "falsely implicated" in parts[P.DEFENSE] and "Learned APP" not in parts[P.DEFENSE] and "flee from justice" not in parts[P.DEFENSE]
    assert "flee from justice" in parts[P.PROSECUTION] and "falsely implicated" not in parts[P.PROSECUTION]
    assert "perused the record" in parts[P.REASONING] and "personal bond" not in parts[P.REASONING]
    assert "bail application is allowed" in parts[P.OPERATIVE] and "perused the record" not in parts[P.OPERATIVE]


def test_operative_part_of_a_dismissal():
    """The operative order of a dismissal carries the dismissal sentence."""
    parts = split_order(order(OPERATIVE_DISMISSED))
    assert "dismissed" in parts[P.OPERATIVE]
    assert "dismissed" not in parts[P.REASONING]


def test_parts_are_non_empty_and_preserve_all_content():
    """No part is empty, and every sentence of the body appears in exactly one part (nothing lost, nothing duplicated)."""
    text = order()
    parts = split_order(text)
    assert all(v.strip() for v in parts.values())
    joined = "\n".join(parts.values())
    for marker in ("FIR No. 112/2024", "falsely implicated", "flee from justice", "perused the record", "personal bond"):
        assert joined.count(marker) == 1


def test_missing_prosecution_part_does_not_split_cleanly():
    """Plan §15.1: orders that do not split cleanly are dropped. No 'Learned APP submits' part means None."""
    assert split_order(order(prosecution="")) is None


def test_missing_defense_part_does_not_split_cleanly():
    """No defense submissions part means None as well."""
    assert split_order(order(defense="")) is None


def test_missing_operative_order_does_not_split_cleanly():
    """An order that never says what was ordered cannot be split into five parts."""
    assert split_order(order(operative="")) is None


def test_text_without_any_cue_phrases_is_dropped():
    """Plain prose with none of the cue phrases returns None, not a guess."""
    assert split_order("The applicant is in custody. The matter was heard on Monday.") is None


def test_empty_text_is_dropped():
    """Empty input returns None."""
    assert split_order("") is None


def test_splitting_is_deterministic():
    """The same order splits the same way every time."""
    assert split_order(order()) == split_order(order())
