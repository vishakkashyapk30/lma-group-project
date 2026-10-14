"""One-page hearing-prep card (plan §8.3): likely concerns from the bench (each with a short answer pointing to a ground and an
authority), three points to lead with (the strongest SUPPORTED grounds), conditions courts often impose in similar grants,
open issues. No outcome prediction, no grant rates (plan §1.3, §8.3, §16).

ASSUMPTION (the skeleton returns `dict[str, Any]`, keys not fixed): `bench_concerns` (list of {factor, answer, ground, authority}),
`lead_with` (list of ground ids), `conditions` (list of str), `open_issues` (list of str), `label` (str).
SKELETON-GAP: no tool or store is specified for 'conditions taken from operative orders' (the operative part is not in
`caselaw.reasoning`); the test only checks the shape of `conditions`.
"""

from __future__ import annotations

import json
import re

import pytest

from tests.unit.export._helpers import CASE, make_brief
from vakeel_sahayak.export.hearing_card import build_hearing_card
from vakeel_sahayak.schemas.enums import ClaimCheck, SparringVerdict
from vakeel_sahayak.schemas.sparring import Objection, SparringRecord

PROBABILITY = re.compile(r"\d+(?:\.\d+)?\s*(?:%|per\s?cent|percent)|\b0\.\d+\b|\b\d+\s*(?:in|out of)\s*\d+\b", re.I)
FORBIDDEN_KEYS = ("probability", "grant_rate", "grant rate", "chance", "likelihood", "prediction", "success")


def sparring(unanswered: bool = True) -> SparringRecord:
    objs = [Objection(id="O1", against="G1", factor="parity_with_co_accused", objection="Different role.", verdict=SparringVerdict.ANSWERED)]
    if unanswered:
        objs.append(Objection(id="O2", against="general", factor="witness_tampering",
                              objection="Charges are not framed and the complainant is yet to be examined.",
                              verdict=SparringVerdict.UNANSWERED))
    return SparringRecord(case_id=CASE, rounds=2, objections=objs)


@pytest.fixture()
def card(install_stores):
    install_stores()
    return build_hearing_card(make_brief(), sparring(), CASE)


def test_card_has_the_four_blocks_of_plan_8_3(card):
    assert {"bench_concerns", "lead_with", "conditions", "open_issues"} <= set(card)


def test_lead_points_are_the_strongest_supported_grounds(card):
    """G1 and G3 are SUPPORTED, so they lead. ASSUMPTION: a REPAIRED ground (G2) may fill the third slot; at most three points."""
    assert len(card["lead_with"]) <= 3
    assert set(card["lead_with"][:2]) == {"G1", "G3"}


def test_needs_review_grounds_are_never_led_with(install_stores):
    """A NEEDS_REVIEW ground is not one of the 'strongest SUPPORTED grounds'."""
    install_stores()
    card = build_hearing_card(make_brief(third_needs_review=True), sparring(), CASE)
    assert "G3" not in card["lead_with"]
    assert len(card["lead_with"]) <= 3


def test_open_issues_cover_the_brief_and_unanswered_objections(card):
    """Open issues to clear before the hearing: the brief's three issues plus the UNANSWERED objection O2."""
    joined = " ".join(card["open_issues"])
    assert "Antecedents unknown" in joined
    assert "wording differs" in joined
    assert "trial-delay" in joined
    assert "complainant is yet to be examined" in joined or "O2" in joined


def test_answered_objections_are_not_open_issues(card):
    assert "Different role" not in " ".join(card["open_issues"])


def test_each_bench_concern_points_to_a_ground_and_an_authority(card):
    """Plan §8.3: each concern comes with a short answer pointing to a ground and an authority."""
    assert card["bench_concerns"], "the card needs at least one concern"
    for concern in card["bench_concerns"]:
        assert concern["answer"]
        assert re.fullmatch(r"G\d+", str(concern["ground"]))
        assert "#" in str(concern["authority"]) or "para" in str(concern["authority"]).lower()


def test_conditions_is_a_list_of_text_items(card):
    """SKELETON-GAP: the source of the conditions is not specified; the shape is."""
    assert isinstance(card["conditions"], list) and all(isinstance(c, str) for c in card["conditions"])


def test_no_outcome_prediction_and_no_grant_rates(card):
    """No probabilities, percentages or fractions anywhere on the card; no prediction-like keys either."""
    dumped = json.dumps(card, ensure_ascii=False, default=str)
    assert not PROBABILITY.search(dumped), PROBABILITY.search(dumped)
    assert not [k for k in FORBIDDEN_KEYS if k in dumped.lower()]


def test_card_is_one_page_sized(card):
    """One page: at most 3 lead points and a bounded number of concerns and conditions (ASSUMPTION: <= 6 concerns, <= 6 conditions)."""
    assert len(card["lead_with"]) <= 3
    assert len(card["bench_concerns"]) <= 6 and len(card["conditions"]) <= 6


def test_card_carries_the_draft_label(card):
    """The AI-generated draft label of the brief travels with the card (ASSUMPTION: key `label`)."""
    assert "AI-generated draft" in card["label"]


def test_check_enum_is_what_decides_strength():
    """Self-check of the fixture: G2 is REPAIRED, the others SUPPORTED (so the ranking test is meaningful)."""
    checks = {g.id: g.check for g in make_brief().grounds}
    assert checks == {"G1": ClaimCheck.SUPPORTED, "G2": ClaimCheck.REPAIRED, "G3": ClaimCheck.SUPPORTED}
