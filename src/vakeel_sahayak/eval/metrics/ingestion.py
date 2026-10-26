"""Metrics: CER, boundary F1, document-type accuracy, downstream field accuracy, escalation rate, questions asked, seconds and GPU-seconds per page (plan §15.8)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.dossier import CaseDossier


def _edit_distance(hyp: str, ref: str) -> int:
    """Levenshtein distance between two strings (character level)."""
    previous = list(range(len(ref) + 1))
    for i, hc in enumerate(hyp, start=1):
        current = [i]
        for j, rc in enumerate(ref, start=1):
            cost = 0 if hc == rc else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def character_error_rate(hyp: str, ref: str) -> float:
    """CER = character-level edit distance between `hyp` and `ref`, divided by the length of `ref`.

    Args:
        hyp: the transcribed/recognised text
        ref: the reference text

    Returns:
        CER (0.0 when identical; can exceed 1.0 when `hyp` is much longer).
    """
    if not ref:
        return 0.0 if not hyp else float(len(hyp))
    return _edit_distance(hyp, ref) / len(ref)


def boundary_f1(pred: list[tuple[int, int]], gold: list[tuple[int, int]]) -> float:
    """F1 over exact document-boundary (first, last) ranges.

    Args:
        pred: predicted document ranges
        gold: gold document ranges

    Returns:
        F1 of the exactly-matching ranges (1.0 when both are empty, 0.0 when either is empty or nothing matches).
    """
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    matches = len(set(pred) & set(gold))
    if matches == 0:
        return 0.0
    precision = matches / len(set(pred))
    recall = matches / len(set(gold))
    return 2 * precision * recall / (precision + recall)


def field_accuracy(dossier: CaseDossier, gold: dict[str, Any]) -> float:
    """Share of gold dossier fields the extracted dossier gets right (plan §15.8, G3).

    Args:
        dossier: the extracted dossier
        gold: field name -> gold value (a dict gold is matched on its keys only)

    Returns:
        Correct fields / gold fields.
    """
    if not gold:
        return 1.0
    correct = 0
    for name, want in gold.items():
        tracked = getattr(dossier.fields, name, None)
        actual = tracked.value if tracked is not None else None
        if hasattr(actual, "model_dump"):
            dump = actual.model_dump(mode="json")
            ok = all(dump.get(k) == v for k, v in want.items()) if isinstance(want, dict) else dump == want
        else:
            ok = actual == want
        correct += int(ok)
    return correct / len(gold)
