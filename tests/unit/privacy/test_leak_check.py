"""Leak-rate measurement for planted names (plan §15.8, §15.2 T7).

`find_leaks(text, planted_names)` returns the planted names that appear in outbound text: exact and case-sensitive.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI
from vakeel_sahayak.privacy.leak_check import find_leaks

ALL = PLANTED_NAMES + PLANTED_NAMES_HI


def test_returns_exactly_the_names_present():
    """Plan §15.8: only planted names that occur in the text are returned."""
    text = "Bail for Ramesh Kumar Yadav; surety Anil Pratap Singh."
    assert set(find_leaks(text, ALL)) == {"Ramesh Kumar Yadav", "Anil Pratap Singh"}


def test_no_leak_returns_empty_list():
    """Plan §15.8: a clean text has an empty leak list."""
    assert find_leaks("The accused Accused-1 was remanded to custody.", ALL) == []


def test_each_leaked_name_reported_once():
    """Plan §15.8: a name mentioned three times is one leak (a leak rate counts names, not mentions)."""
    text = "Ramesh Kumar Yadav, Ramesh Kumar Yadav and again Ramesh Kumar Yadav."
    assert find_leaks(text, ALL) == ["Ramesh Kumar Yadav"]


def test_match_is_case_sensitive():
    """Plan §15.8: exact, case-sensitive match (a lower-cased name is not the planted string)."""
    assert find_leaks("ramesh kumar yadav and RAMESH KUMAR YADAV", ALL) == []


def test_partial_name_is_not_a_leak():
    """Plan §15.8: only the full planted string counts; a surname alone does not."""
    assert find_leaks("Mr. Yadav and Ramesh were present.", ALL) == []


def test_punctuation_in_names_is_matched_literally():
    """Plan §15.8: 'Mohd. Irfan Qureshi' matches with its dot, and 'Mohd Irfan Qureshi' (no dot) does not."""
    assert find_leaks("Notice to Mohd. Irfan Qureshi.", ALL) == ["Mohd. Irfan Qureshi"]
    assert find_leaks("Notice to Mohd Irfan Qureshi.", ALL) == []


def test_devanagari_names_are_detected():
    """Plan §15.2 T7: Hindi planted names are found too."""
    assert find_leaks("आरोपी रमेश कुमार यादव उपस्थित हुआ।", ALL) == ["रमेश कुमार यादव"]


def test_empty_inputs():
    """Plan §15.8: empty text or no planted names yields no leaks."""
    assert find_leaks("", ALL) == []
    assert find_leaks("Ramesh Kumar Yadav", []) == []


@given(subset=st.lists(st.sampled_from(ALL), unique=True, max_size=len(ALL)))
def test_property_equals_independent_membership_oracle(subset):
    """Plan §15.8: for any subset embedded in text, the leaks are exactly that subset (oracle: plain `in`)."""
    text = "Order. " + " ; ".join(subset) + " . End."
    expected = {n for n in ALL if n in text}
    assert set(find_leaks(text, ALL)) == expected == set(subset)
