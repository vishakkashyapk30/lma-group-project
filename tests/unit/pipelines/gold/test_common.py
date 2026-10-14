"""Shared gold-label logic (plan §15.1): agreed labels only, labeler agreement (Cohen's kappa), answerable factors."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vakeel_sahayak.models.labeler import EvalLabeler
from vakeel_sahayak.pipelines.gold.common import agreed_labels, answerable_factors, cohen_kappa
from vakeel_sahayak.schemas.enums import Factor as F


# ---- agreed_labels -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("rules", "llm", "expected"),
    [
        (["a", "b", "c"], ["c", "a"], ["a", "c"]),          # intersection, order of the rule labels
        (["b", "a"], ["a", "b"], ["b", "a"]),                # order follows the rule labels, not the LLM
        (["a", "a", "b"], ["a"], ["a"]),                     # de-duplicated
        (["a", "b"], ["c", "d"], []),                        # disjoint
        ([], ["a"], []),
        (["a"], [], []),
        ([], [], []),
        (["parity_with_co_accused", "flight_risk"], ["flight_risk", "antecedents"], ["flight_risk"]),
    ],
)
def test_agreed_labels_is_the_intersection(rules, llm, expected):
    """Gold keeps only labels BOTH the keyword rules and the LLM gave, in rule order, without duplicates."""
    assert agreed_labels(rules, llm) == expected


_labels = st.lists(st.sampled_from(list("abcdefg")), max_size=8)


@given(_labels, _labels)
def test_agreed_labels_property(rules, llm):
    """Property: result = rule labels (order kept, deduped) that the LLM also gave."""
    oracle = [x for x in dict.fromkeys(rules) if x in set(llm)]
    assert agreed_labels(rules, llm) == oracle


@given(_labels, _labels)
def test_agreed_labels_is_a_subset_of_both(rules, llm):
    """Property: nothing outside either labeler's output can become gold."""
    out = agreed_labels(rules, llm)
    assert set(out) <= set(rules) and set(out) <= set(llm)


# ---- cohen_kappa -------------------------------------------------------------------------------------------------
VARIED = [["a"], ["b"], ["a", "b"], []]


def test_kappa_is_one_for_identical_labelings():
    """Two labelers that agree on every item and label have kappa 1."""
    assert cohen_kappa(VARIED, [list(x) for x in VARIED]) == pytest.approx(1.0)


def test_kappa_is_zero_or_below_for_independent_labelings():
    """Agreement no better than chance gives kappa <= 0."""
    rules = [["a", "b"], []]
    llm = [["a"], ["a"]]
    assert cohen_kappa(rules, llm) <= 1e-9


def test_kappa_is_minus_one_for_systematic_disagreement():
    """Labelers that always give opposite answers have kappa -1."""
    assert cohen_kappa([["a"], ["b"]], [["b"], ["a"]]) == pytest.approx(-1.0)


def test_kappa_rejects_mismatched_lengths():
    """ASSUMPTION: one label list per item on each side; different item counts are a ValueError."""
    with pytest.raises(ValueError):
        cohen_kappa([["a"], ["b"]], [["a"]])


@given(st.lists(st.tuples(_labels, _labels), min_size=1, max_size=12))
def test_kappa_range_property(pairs):
    """Property: kappa is finite and within [-1, 1] for any pair of labelings."""
    k = cohen_kappa([r for r, _ in pairs], [l for _, l in pairs])
    assert math.isfinite(k) and -1.0 - 1e-9 <= k <= 1.0 + 1e-9


@given(st.lists(_labels, min_size=1, max_size=12))
def test_kappa_of_a_labeling_with_itself_is_never_below_chance(labelings):
    """Property: comparing a labeling with itself gives kappa 1 (or the degenerate-case value, still in range, never negative)."""
    k = cohen_kappa(labelings, [list(x) for x in labelings])
    assert k >= 0.0 - 1e-9


# ---- answerable_factors ------------------------------------------------------------------------------------------
_KEYWORDS = {
    "parity_with_co_accused": ["co-accused"],
    "charge_sheet_filed": ["charge sheet"],
    "antecedents": ["antecedents"],
    "flight_risk": ["flight"],
}


class KeywordFakeLabeler:
    """A fake Llama: labels a factor whenever one of its keywords occurs in the text (a stand-in model, not product logic)."""

    def label(self, text: str, label_set: list[str]) -> list[str]:
        low = text.lower()
        return [f for f in label_set if any(k in low for k in _KEYWORDS.get(f, []))]


class OverEagerFakeLabeler:
    """A fake LLM that claims every factor is answerable; the rules must veto it."""

    def label(self, text: str, label_set: list[str]) -> list[str]:
        return list(label_set)


def test_factor_with_supporting_fact_in_input_is_answerable(monkeypatch):
    """A text mentioning a co-accused granted bail makes parity_with_co_accused answerable."""
    monkeypatch.setattr(EvalLabeler, "label", lambda self, text, label_set: KeywordFakeLabeler().label(text, label_set))
    out = answerable_factors("A co-accused with an identical role has been granted bail by this Court.")
    assert F.PARITY_WITH_CO_ACCUSED in out


def test_factor_without_supporting_fact_is_not_answerable(monkeypatch):
    """A text without any co-accused fact does not make parity answerable."""
    monkeypatch.setattr(EvalLabeler, "label", lambda self, text, label_set: KeywordFakeLabeler().label(text, label_set))
    out = answerable_factors("The applicant has no criminal antecedents and the charge sheet has been filed.")
    assert F.PARITY_WITH_CO_ACCUSED not in out
    assert F.ANTECEDENTS in out and F.CHARGE_SHEET_FILED in out


def test_answerable_needs_both_methods_to_agree(monkeypatch):
    """Plan §15.1: 'decided by the same two methods', so an LLM that claims every factor cannot create answerability."""
    monkeypatch.setattr(EvalLabeler, "label", lambda self, text, label_set: OverEagerFakeLabeler().label(text, label_set))
    out = answerable_factors("The applicant has no criminal antecedents.")
    assert set(out) == {F.ANTECEDENTS}


def test_text_with_no_supporting_facts_has_no_answerable_factor(monkeypatch):
    """Nothing in the input, nothing answerable."""
    monkeypatch.setattr(EvalLabeler, "label", lambda self, text, label_set: OverEagerFakeLabeler().label(text, label_set))
    assert answerable_factors("The matter is listed for hearing.") == []
