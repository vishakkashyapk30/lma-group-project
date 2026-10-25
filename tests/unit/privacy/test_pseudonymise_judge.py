"""Judges named after 'Justice' (capitals, glued to the next heading word, title case) are found by the rules."""

from __future__ import annotations

import pytest

from vakeel_sahayak.privacy.pseudonymise import detect_names, pseudonymise_text


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("HIGH COURT\nHON'BLE MR. JUSTICE SHARANORAL ORDER", "SHARAN"),
        ("BEFORE JUSTICE RATNAKER BHENGRA\nBail Application", "RATNAKER BHENGRA"),
        ("The bench of Justice Rajesh Kumar heard the matter.", "Rajesh Kumar"),
    ],
)
def test_judge_name_detected(text, name):
    assert name in [s.text_of(text) for s in detect_names(text)]
    out, _ = pseudonymise_text(text, "case-0001")
    assert name not in out


def test_justice_without_a_name_is_left_alone():
    text = "Justice delayed is justice denied. JUSTICE\nORAL ORDER"
    assert detect_names(text) == []
