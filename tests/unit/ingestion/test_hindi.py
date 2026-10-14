"""Hindi handling (plan §4.1 K5, §4.5): script detection, translation with both texts kept."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.fakes.models import FakeTranslator
from tests.unit.ingestion._helpers import patch_attr_everywhere
from vakeel_sahayak.ingestion.hindi import detect_script, to_english_with_original

HINDI_FIR = "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024"
HINDI_EN = "FIR No. 112/2024 dated 14.08.2024"  # from FakeTranslator.TABLE


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(HINDI_FIR, "devanagari", id="hindi_fir_line"),
        pytest.param("धारा 318(4) बी.एन.एस.", "devanagari", id="hindi_section"),
        pytest.param("The applicant was arrested on 20.08.2024 and remanded to judicial custody.", "latin", id="english_order"),
        pytest.param("FIR No. 112/2024 dated 14.08.2024", "latin", id="english_with_digits"),
        pytest.param("The informant states: मेरे साथ धोखाधड़ी हुई है और आरोपी ने पैसे नहीं लौटाए। The accused denied it.", "mixed", id="english_quoting_hindi"),
        pytest.param("आरोपी को गिरफ्तार किया गया was arrested on 20.08.2024 और जेल भेजा गया remanded to custody", "mixed", id="code_mixed_balanced"),
    ],
)
def test_detect_script(text, expected):
    """'devanagari', 'latin' or 'mixed' by the share of Devanagari letters; digits and punctuation do not count."""
    assert detect_script(text) == expected


@given(st.text(alphabet=[chr(c) for c in range(0x0915, 0x0939)], min_size=1, max_size=40))
def test_pure_devanagari_is_devanagari(text):
    """Property: any text made only of Devanagari letters is 'devanagari'."""
    assert detect_script(text) == "devanagari"


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=40).filter(lambda s: s.strip()))
def test_pure_latin_is_latin(text):
    """Property: any text made only of Latin letters is 'latin'."""
    assert detect_script(text) == "latin"


@given(st.text(max_size=60))
def test_detect_script_always_returns_one_of_three_labels(text):
    """Property: the result is always one of the three labels, never an error."""
    assert detect_script(text) in {"devanagari", "latin", "mixed"}


def _install_translator(monkeypatch) -> FakeTranslator:
    fake = FakeTranslator()
    patch_attr_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_translator", lambda *a, **k: fake)
    return fake


def test_to_english_keeps_both_texts(monkeypatch):
    """Plan §4.5: every quote keeps the Hindi original AND its English translation."""
    fake = _install_translator(monkeypatch)
    result = to_english_with_original(HINDI_FIR)
    assert len(result) == 2
    # ASSUMPTION: order-agnostic. The skeleton docstring says (original, translation); the lead's brief said (english, original).
    assert set(result) == {HINDI_FIR, HINDI_EN}
    assert fake.calls == [HINDI_FIR]


def test_original_hindi_is_returned_unchanged(monkeypatch):
    """The Hindi original is returned byte-for-byte, not normalised or translated, so counsel sees the original."""
    _install_translator(monkeypatch)
    text = "घटना दिनांक 10.08.2024"
    out = to_english_with_original(text)
    assert text in out
    assert [t for t in out if t != text] == ["date of occurrence 10.08.2024"]


def test_unknown_phrase_still_returns_both_texts(monkeypatch):
    """A phrase the translator does not know is translated (visibly, via the fake's '[en]' prefix) and the original kept."""
    _install_translator(monkeypatch)
    text = "आरोपी फरार है"
    out = to_english_with_original(text)
    assert text in out and f"[en] {text}" in out
