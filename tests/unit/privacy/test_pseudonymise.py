"""Pseudonymisation (plan §4.4 role aliases, §16 privacy, §15.2 T7 planted names, §8.2 cause title restored locally).

Names are replaced by role aliases (Accused-1, Co-accused-1, Complainant-1, IO-1) after OCR and before text leaves
the laptop; the alias map stays local and `restore` fills real names back in on counsel's machine only.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI
from tests.unit.privacy._helpers import EN_TEXT, HI_TEXT
from vakeel_sahayak.privacy.leak_check import find_leaks
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, pseudonymise_text

CASE = "case-0007"
EN_NAMES = PLANTED_NAMES  # Ramesh Kumar Yadav, Sunita Devi Sharma, Mohd. Irfan Qureshi, Anil Pratap Singh


def test_no_planted_name_survives_in_english_text():
    """Plan §16/T7: the pseudonymised text contains none of the planted names (independent `in` check)."""
    out, _ = pseudonymise_text(EN_TEXT, CASE)
    for name in EN_NAMES:
        assert name not in out


def test_leak_check_agrees_that_english_text_is_clean():
    """Plan §15.8: `find_leaks` (second check) reports nothing on the pseudonymised text."""
    out, _ = pseudonymise_text(EN_TEXT, CASE)
    assert find_leaks(out, EN_NAMES) == []


@pytest.mark.parametrize(
    ("alias", "name"),
    [
        ("Accused-1", "Ramesh Kumar Yadav"),
        ("Co-accused-1", "Anil Pratap Singh"),
        ("Complainant-1", "Sunita Devi Sharma"),
        ("IO-1", "Mohd. Irfan Qureshi"),
    ],
)
def test_role_aliases_from_context(alias, name):
    """Plan §4.4: the role cue in the sentence selects the alias (Accused-1 / Co-accused-1 / Complainant-1 / IO-1)."""
    out, pmap = pseudonymise_text(EN_TEXT, CASE)
    assert alias in out
    assert pmap.restore(alias) == name


def test_alias_does_not_replace_surrounding_words():
    """Plan §4.4: only the names change; dates and role words stay (facts the pipeline needs are not damaged)."""
    out, _ = pseudonymise_text(EN_TEXT, CASE)
    for kept in ("20.08.2024", "05.12.2024", "arrested", "granted bail", "charge sheet", "Magistrate"):
        assert kept in out


def test_roundtrip_restore_gives_back_the_original():
    """Plan §8.2: `PseudonymMap.restore` restores the real names locally (exact roundtrip)."""
    out, pmap = pseudonymise_text(EN_TEXT, CASE)
    assert pmap.restore(out) == EN_TEXT


def test_restored_names_never_appear_in_the_pseudonymised_text():
    """Plan §16: restoring is a separate local step; the outbound text itself stays name-free."""
    out, pmap = pseudonymise_text(EN_TEXT, CASE)
    restored = pmap.restore(out)
    assert all(name in restored for name in EN_NAMES)
    assert all(name not in out for name in EN_NAMES)


def test_same_name_gets_same_alias_across_calls_with_the_same_map():
    """Plan §4.4: stable alias; a second document of the same case reuses the map and gets the same alias."""
    _, pmap = pseudonymise_text(EN_TEXT, CASE)
    out2, pmap2 = pseudonymise_text("Bail was prayed for the accused Ramesh Kumar Yadav again.", CASE, mapping=pmap)
    assert "Accused-1" in out2
    assert "Ramesh Kumar Yadav" not in out2
    assert pmap2.restore("Accused-1") == "Ramesh Kumar Yadav"
    assert "Accused-2" not in out2


def test_possessive_and_repeated_mentions_are_all_replaced():
    """Plan §16: every mention is replaced, including possessives and repeats."""
    text = "Ramesh Kumar Yadav's application. The accused Ramesh Kumar Yadav says Ramesh Kumar Yadav is innocent."
    out, _ = pseudonymise_text(text, CASE)
    assert "Ramesh Kumar Yadav" not in out
    assert "Ramesh" not in out.replace("Accused", "")


def test_hindi_devanagari_names_are_pseudonymised():
    """Plan §4.5/§16: names written in Devanagari are pseudonymised too."""
    out, pmap = pseudonymise_text(HI_TEXT, CASE)
    for name in PLANTED_NAMES_HI:
        assert name not in out
    assert find_leaks(out, PLANTED_NAMES_HI) == []
    assert re.search(r"Accused-1", out)  # ASSUMPTION: aliases are the Latin-script role labels of plan §4.4
    assert re.search(r"Complainant-1", out)
    assert pmap.restore(out) == HI_TEXT


def test_hindi_dates_and_sentence_markers_survive():
    """Plan §4.5: only names are replaced in Hindi text; the date stays."""
    out, _ = pseudonymise_text(HI_TEXT, CASE)
    assert "20.08.2024" in out
    assert "।" in out


def test_text_without_names_is_unchanged():
    """Plan §4.4: nothing to replace -> text unchanged and the map restores nothing."""
    text = "The charge sheet was filed on 02.11.2024. Next date of hearing is 04.09.2024."
    out, pmap = pseudonymise_text(text, CASE)
    assert out == text
    assert pmap.restore(text) == text


def test_map_is_a_pseudonym_map():
    """Plan §16: the returned map is a PseudonymMap (local-only)."""
    _, pmap = pseudonymise_text(EN_TEXT, CASE)
    assert isinstance(pmap, PseudonymMap)


# ---- PseudonymMap directly ---------------------------------------------------------------------------------
def test_alias_for_is_stable_for_the_same_name():
    """Plan §4.4: the same name always gets the same alias."""
    pmap = PseudonymMap()
    first = pmap.alias_for("Ramesh Kumar Yadav", "Accused")  # ASSUMPTION: role is the alias label, e.g. 'Accused'
    assert first == "Accused-1"
    assert pmap.alias_for("Ramesh Kumar Yadav", "Accused") == first


def test_alias_for_numbers_distinct_names_within_a_role():
    """Plan §4.4: a second person in the same role is Accused-2."""
    pmap = PseudonymMap()
    assert pmap.alias_for("Ramesh Kumar Yadav", "Accused") == "Accused-1"
    assert pmap.alias_for("Anil Pratap Singh", "Accused") == "Accused-2"


def test_alias_for_numbers_per_role_independently():
    """Plan §4.4: each role counts from 1."""
    pmap = PseudonymMap()
    pmap.alias_for("Ramesh Kumar Yadav", "Accused")
    assert pmap.alias_for("Sunita Devi Sharma", "Complainant") == "Complainant-1"


def test_restore_replaces_aliases_with_names():
    """Plan §8.2: restore fills real names into counsel's cause title."""
    pmap = PseudonymMap()
    alias = pmap.alias_for("Ramesh Kumar Yadav", "Accused")
    assert pmap.restore(f"State v. {alias}") == "State v. Ramesh Kumar Yadav"


def test_restore_does_not_confuse_prefix_aliases():
    """Plan §4.4: Accused-1 must not be restored inside Accused-10."""
    pmap = PseudonymMap()
    for i in range(10):
        pmap.alias_for(f"Person Number{i}", "Accused")
    assert pmap.restore("Accused-10") == "Person Number9"
    assert pmap.restore("Accused-1") == "Person Number0"


# ---- properties --------------------------------------------------------------------------------------------
_TEMPLATES = [
    "The accused {n} was arrested on 20.08.2024.",
    "{n}'s bail application was rejected.",
    "Counsel for the accused {n} argued at length.",
    "The complainant {n} deposed before the Magistrate.",
    "FIR lodged against {n} at PS-1.",
]


@given(
    names=st.lists(st.sampled_from(EN_NAMES + PLANTED_NAMES_HI), min_size=1, max_size=4, unique=True),
    template=st.sampled_from(_TEMPLATES),
)
def test_property_no_planted_name_survives(names, template):
    """Plan §15.2 T7: for any planted names in any sentence frame, the leak rate is zero."""
    text = " ".join(template.format(n=n) for n in names)
    out, _ = pseudonymise_text(text, CASE)
    assert [n for n in names if n in out] == []
    assert find_leaks(out, EN_NAMES + PLANTED_NAMES_HI) == []


@given(
    names=st.lists(st.sampled_from(EN_NAMES + PLANTED_NAMES_HI), min_size=1, max_size=4, unique=True),
    template=st.sampled_from(_TEMPLATES),
)
def test_property_restore_roundtrip(names, template):
    """Plan §8.2: restore(pseudonymise(text)) == text for any planted-name text."""
    text = " ".join(template.format(n=n) for n in names)
    out, pmap = pseudonymise_text(text, CASE)
    assert pmap.restore(out) == text
