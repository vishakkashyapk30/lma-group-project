"""A prompt's public `corpus` is checked like the agents' own guard checks it (this case's names, PII), the case side in full."""

from __future__ import annotations

import pytest

from vakeel_sahayak.models.prompting import render_prompt
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_public_text, assert_pseudonymised, split_public_corpus
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap

CORPUS = [{"text": "Shri Jethmalani appeared in State v. Rajesh Kumar; the Witness Protection Scheme applies."}]


def prompt(case: dict, corpus: list) -> str:
    return render_prompt("vakeel.draft_ground", "Draft one ground.", {"case": case, "corpus": corpus}, system="You are Vakeel.")


def mapping() -> PseudonymMap:
    m = PseudonymMap()
    m.alias_for("Chando Mahto", "accused")
    return m


def test_names_inside_published_orders_do_not_trip_the_generic_name_rules():
    case_side, corpus = split_public_corpus({"messages": [{"role": "user", "content": prompt({"facts": "Accused-1 was arrested."}, CORPUS)}]})
    assert len(corpus) == 1
    assert_pseudonymised(case_side, mapping=mapping())
    assert_public_text(corpus[0], mapping=mapping())


def test_the_case_side_is_still_checked_in_full():
    case_side, _ = split_public_corpus({"messages": [{"role": "user", "content": prompt({"facts": "accused Rajesh Verma was arrested."}, CORPUS)}]})
    with pytest.raises(PrivacyBoundaryError):
        assert_pseudonymised(case_side, mapping=mapping())


def test_the_corpus_may_not_carry_this_cases_real_names_or_ids():
    for text in ("Chando Mahto was heard.", "Account Number 874310100063 of the applicant", "mail x@y.com"):
        with pytest.raises(PrivacyBoundaryError):
            assert_public_text([{"text": text}], mapping=mapping())


def test_text_without_the_prompt_layout_passes_through_whole():
    payload = {"messages": [{"role": "user", "content": "plain text with Shri Jethmalani"}]}
    assert split_public_corpus(payload) == (payload, [])
    with pytest.raises(PrivacyBoundaryError):
        assert_pseudonymised(payload)
