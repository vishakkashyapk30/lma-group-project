"""Treatment labels: cue words give a first label, Llama-3.1-8B labels the same sentences, only agreed labels kept, rest are UNKNOWN (plan §5.3)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

from vakeel_sahayak.schemas.enums import Treatment

# Strongest first: when a sentence has several cues the first row wins.
_CUES: list[tuple[Treatment, re.Pattern[str]]] = [
    (Treatment.OVERRULED, re.compile(r"\b(?:overrul(?:ed|es|ing)|per\s+incuriam|no\s+longer\s+(?:a\s+)?good\s+law|stands\s+overruled|expressly\s+overruled)\b", re.I)),
    (Treatment.DISTINGUISHED, re.compile(r"\b(?:distinguish(?:ed|es|able|ing)?|inapplicable|not\s+applicable\s+to\s+the\s+facts|different\s+on\s+facts)\b", re.I)),
    (Treatment.FOLLOWED, re.compile(r"\b(?:follow(?:ed|s|ing)|reaffirm(?:ed|s)?|reiterat(?:ed|es)|approv(?:ed|es|ing)|affirm(?:ed|s))\b", re.I)),
    (Treatment.RELIED_ON, re.compile(r"\b(?:reli(?:ed|es|ance)\s+(?:up)?on|reli(?:ed|es)|relying\s+(?:up)?on|reliance\s+(?:is\s+)?placed|applied|squarely\s+covered)\b", re.I)),
    (Treatment.REFERRED, re.compile(r"\b(?:referred\s+to|refer(?:s|ring)?|noticed|cited|see|cf\.?|vide|observed\s+in|held\s+in|laid\s+down\s+in)\b", re.I)),
]
_NEGATION = re.compile(r"\b(?:not|never|no|neither|nor|cannot|can't|without|hardly)\b(?:\s+\w+){0,2}\s*$", re.I)
PRIORITY = {t: i for i, (t, _) in enumerate(_CUES)}


class TreatmentLabeler(Protocol):
    """Client protocol for the evaluation labeler that labels a citing sentence (Llama-3.1-8B; plan §5.3, §12).

    No model is called from this package; `models.labeler.EvalLabeler` can be adapted to it in the evaluation environment.
    """

    def label_treatment(self, sentence: str) -> Treatment:
        """Label how the sentence treats the cited case."""
        ...


def label_treatment(sentence: str) -> Treatment:
    """Cue-word label.

    Cues are 'followed', 'relied upon', 'distinguished', 'overruled' / 'per incuriam' and 'referred to'; a cue preceded
    by a negation ('not overruled', 'cannot be distinguished') is ignored. Strongest cue wins.

    Args:
        sentence: see behaviour

    Returns:
        Treatment (UNKNOWN when no cue).
    """
    for treatment, pattern in _CUES:
        for m in pattern.finditer(sentence):
            if not _NEGATION.search(sentence[max(0, m.start() - 30) : m.start()]):
                return treatment
    return Treatment.UNKNOWN


def agree_treatment(cue: Treatment, llm: Treatment) -> Treatment:
    """Agreed label or UNKNOWN.

    Args:
        cue: see behaviour
        llm: see behaviour

    Returns:
        Treatment.
    """
    return cue if cue == llm and cue != Treatment.UNKNOWN else Treatment.UNKNOWN


def strongest(treatments: Iterable[Treatment]) -> Treatment:
    """The strongest treatment among several sentences about the same cited case (overruled > distinguished > followed > relied on > referred > unknown)."""
    ranked = [t for t in treatments if t != Treatment.UNKNOWN]
    return min(ranked, key=lambda t: PRIORITY[t]) if ranked else Treatment.UNKNOWN
