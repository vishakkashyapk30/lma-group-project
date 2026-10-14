"""Treatment labels (plan §5.3 'Treatment'): cue words give a first label; Llama labels the same sentences; only labels both
agree on are used, the rest are 'treatment unknown'."""

from __future__ import annotations

import pytest

from vakeel_sahayak.pipelines.citation_graph.treatment import agree_treatment, label_treatment
from vakeel_sahayak.schemas.enums import Treatment as T

CUES = [
    ("The Court followed the ratio in Arnesh Kumar while deciding the present application.", T.FOLLOWED),
    ("The decision in Antil was relied upon by the learned counsel and accepted.", T.RELIED_ON),
    ("The decision in that case is distinguished on facts as the accused there was a repeat offender.", T.DISTINGUISHED),
    ("That judgment was overruled by a larger bench of this Court.", T.OVERRULED),
    ("The earlier view was per incuriam as it ignored the binding precedent.", T.OVERRULED),
    ("Reference may be made to the judgment referred to in paragraph 12 of the order.", T.REFERRED),
    ("The accused is a resident of Delhi and has no previous cases.", T.UNKNOWN),
]


@pytest.mark.parametrize(("sentence", "expected"), CUES, ids=[c[1].value + str(i) for i, c in enumerate(CUES)])
def test_cue_words_give_the_first_label(sentence, expected):
    """Plan §5.3: followed / relied upon / distinguished / overruled or per incuriam / referred to, else unknown."""
    assert label_treatment(sentence) == expected


def test_cue_matching_is_case_insensitive():
    """Cue words match whatever the case ('OVERRULED')."""
    assert label_treatment("THE EARLIER JUDGMENT WAS OVERRULED.") == T.OVERRULED


def test_distinguished_is_not_overruled():
    """'Distinguished' only distinguishes; it must not be read as 'overruled' (the good-law check relies on this)."""
    assert label_treatment("The Court distinguished the earlier decision on facts.") == T.DISTINGUISHED


def test_empty_sentence_is_unknown():
    """No text, no treatment."""
    assert label_treatment("") == T.UNKNOWN


def test_treatment_enum_has_the_six_labels():
    """Five treatments plus UNKNOWN (plan §5.3)."""
    assert [t.value for t in T] == ["FOLLOWED", "RELIED_ON", "DISTINGUISHED", "OVERRULED", "REFERRED", "UNKNOWN"]


@pytest.mark.parametrize("cue", list(T))
@pytest.mark.parametrize("llm", list(T))
def test_agree_treatment_full_table(cue, llm):
    """Keep the label only when cue words and the LLM agree on a real label; otherwise 'treatment unknown'."""
    expected = cue if (cue == llm and cue != T.UNKNOWN) else T.UNKNOWN
    assert agree_treatment(cue, llm) == expected
