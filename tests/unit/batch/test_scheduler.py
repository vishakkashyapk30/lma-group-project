"""Batch scheduler (plan §11 'Pairokar decides').

Per case: queue a full brief, flag for counsel (for example an open default-bail window), or ask for documents first;
a case found to face a statutory bar moves down.

ASSUMPTIONS (TriageCard carries only reasons / flags / missing_docs): a default-bail window open or opening soon shows as
a reason mentioning 'default-bail'; a statutory bar shows as a flag or reason containing 'statutory bar'
(case-insensitive); `reprioritise` moves barred cards to the end, keeps the relative order of the rest and renumbers
`urgency_rank` 1..n.
"""

from __future__ import annotations

import pytest

from tests.unit.batch._helpers import hand_card
from vakeel_sahayak.batch.scheduler import Scheduler

DECISIONS = {"full_brief", "flag_counsel", "request_documents"}
BAR = "CHECK: statutory bar applies (NDPS s.37)"


@pytest.mark.parametrize(
    ("card", "decision"),
    [
        # an open or opening default-bail window is flagged for counsel (plan §11)
        (hand_card("c1", reasons=["Default-bail window is open (BNSS s.187(3))"]), "flag_counsel"),
        (hand_card("c2", reasons=["Default-bail window opens in 3 days (BNSS s.187(3))"]), "flag_counsel"),
        # a missing custody certificate with nothing urgent: ask for documents first
        (hand_card("c3", missing=["custody certificate"]), "request_documents"),
        (hand_card("c4", reasons=["167 days in custody"], flags=["CHECK: antecedents unknown"], missing=["custody certificate"]), "request_documents"),
        # nothing urgent, nothing missing: queue the full brief
        (hand_card("c5", reasons=["167 days in custody"]), "full_brief"),
        (hand_card("c6", reasons=["167 days in custody"], flags=["CHECK: antecedents unknown"]), "full_brief"),
    ],
)
def test_decide(card, decision):
    """Plan §11: open default-bail window -> flag_counsel; missing documents (nothing urgent) -> request_documents; else full_brief."""
    assert Scheduler().decide(card) == decision


def test_decide_only_returns_one_of_the_three_decisions():
    """Plan §11: the decision vocabulary is closed."""
    for c in (hand_card("a"), hand_card("b", missing=["x"]), hand_card("c", reasons=["Default-bail window is open"])):
        assert Scheduler().decide(c) in DECISIONS


def test_reprioritise_moves_a_barred_case_down():
    """Plan §11: a case found to face a statutory bar moves down."""
    cards = [
        hand_card("barred", 1, reasons=["Default-bail window is open"], flags=[BAR]),
        hand_card("b", 2, reasons=["900 days in custody"]),
        hand_card("c", 3, reasons=["300 days in custody"]),
    ]
    out = Scheduler().reprioritise(cards)
    assert [c.case_id for c in out] == ["b", "c", "barred"]
    assert [c.urgency_rank for c in out] == [1, 2, 3]


def test_reprioritise_keeps_the_order_of_the_other_cases():
    """Plan §11: only the barred case moves; the others keep their relative order."""
    cards = [hand_card("a", 1), hand_card("barred", 2, flags=[BAR]), hand_card("b", 3), hand_card("c", 4)]
    assert [c.case_id for c in Scheduler().reprioritise(cards)] == ["a", "b", "c", "barred"]


def test_reprioritise_without_a_bar_changes_nothing():
    """Plan §11: with no statutory bar the order is unchanged."""
    cards = [hand_card("a", 1), hand_card("b", 2), hand_card("c", 3)]
    out = Scheduler().reprioritise(cards)
    assert [c.case_id for c in out] == ["a", "b", "c"]
    assert [c.urgency_rank for c in out] == [1, 2, 3]


def test_reprioritise_is_a_permutation():
    """Plan §11: no card is lost or duplicated."""
    cards = [hand_card("a", 1, flags=[BAR]), hand_card("b", 2, flags=[BAR]), hand_card("c", 3)]
    out = Scheduler().reprioritise(cards)
    assert sorted(c.case_id for c in out) == ["a", "b", "c"]
    assert out[0].case_id == "c"
