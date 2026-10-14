"""Keyword-rule labeler for the 12 bail factors of Appendix A (plan §5.2 'factors'). Rules only."""

from __future__ import annotations

import pytest

from vakeel_sahayak.pipelines.factor_tagger import tag_factors
from vakeel_sahayak.schemas.enums import Factor as F

# one table row per Appendix A factor (several cue phrases for custody and the s.436A/479 factor)
TABLE = [
    ("The co-accused has already been granted bail on similar facts.", F.PARITY_WITH_CO_ACCUSED),
    ("The charge sheet has been filed and the investigation is complete.", F.CHARGE_SHEET_FILED),
    ("The applicant is in custody since 20.08.2024.", F.CUSTODY_PERIOD),
    ("The period of custody undergone by the applicant is considerable.", F.CUSTODY_PERIOD),
    ("The applicant has no criminal antecedents.", F.ANTECEDENTS),
    ("There is no flight risk as the applicant has deep roots in the community.", F.FLIGHT_RISK),
    ("There is an apprehension that the applicant may tamper with witnesses.", F.WITNESS_TAMPERING),
    ("The twin conditions of Section 37 NDPS Act have not been satisfied.", F.STATUTORY_BAR),
    ("The applicant claims relief under Section 436A of the Code.", F.UNDERTRIAL_PERIOD),
    ("The applicant has undergone detention for the period contemplated in Section 479 BNSS.", F.UNDERTRIAL_PERIOD),
    ("The trial is likely to take long and has not begun.", F.TRIAL_DELAY),
    ("The applicant is of advanced old age and suffers from ill health.", F.HEALTH_AGE_FAMILY),
    ("On a reading of the record there is prima facie no case against the applicant.", F.WEAK_PRIMA_FACIE),
    ("The Court has considered the gravity of the offence and the punishment prescribed.", F.GRAVITY_AND_PUNISHMENT),
]


def test_table_covers_all_twelve_factors():
    """Appendix A lists 12 factors and the table has at least one row for each."""
    assert {f for _, f in TABLE} == set(F)
    assert len(set(F)) == 12


@pytest.mark.parametrize(("sentence", "factor"), TABLE, ids=[f"{f.value}-{i}" for i, (_, f) in enumerate(TABLE)])
def test_keyword_sentence_is_tagged_with_its_factor(sentence, factor):
    """A sentence with the factor's cue phrase is tagged with that factor."""
    tags = tag_factors(sentence)
    assert all(isinstance(t, F) for t in tags)
    assert factor in tags


@pytest.mark.parametrize(
    ("sentence", "factor"),
    [
        ("The co-accused has already been granted bail on similar facts.", F.PARITY_WITH_CO_ACCUSED),
        ("The applicant has no criminal antecedents.", F.ANTECEDENTS),
        ("There is no flight risk as the applicant has deep roots in the community.", F.FLIGHT_RISK),
        ("There is an apprehension that the applicant may tamper with witnesses.", F.WITNESS_TAMPERING),
    ],
)
def test_unambiguous_sentence_has_no_spurious_factor(sentence, factor):
    """Single-cue sentences are tagged with exactly that factor, no cross-talk."""
    assert tag_factors(sentence) == [factor]


def test_sentence_with_two_cues_returns_both():
    """A sentence discussing parity and flight risk is tagged with both factors."""
    tags = tag_factors("The co-accused has already been granted bail and there is no flight risk.")
    assert set(tags) == {F.PARITY_WITH_CO_ACCUSED, F.FLIGHT_RISK}


def test_no_cue_gives_no_factor():
    """Text with no factor cue returns an empty list."""
    assert tag_factors("The matter was listed on Monday before the Vacation Bench.") == []


def test_empty_text_gives_no_factor():
    """Empty text returns an empty list."""
    assert tag_factors("") == []


def test_matching_is_case_insensitive():
    """Cue phrases match regardless of case."""
    assert F.FLIGHT_RISK in tag_factors("THERE IS NO FLIGHT RISK.")


def test_repeated_cue_gives_one_tag():
    """A factor mentioned twice is returned once."""
    tags = tag_factors("There is no flight risk. The applicant is not a flight risk either.")
    assert tags.count(F.FLIGHT_RISK) == 1
