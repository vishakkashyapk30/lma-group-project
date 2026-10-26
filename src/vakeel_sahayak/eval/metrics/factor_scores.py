"""Metrics: Factor recall and precision against G1 on answerable factors (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import Factor


def factor_recall_precision(
    predicted: list[Factor], gold: list[Factor], answerable: list[Factor]
) -> tuple[float, float]:
    """Recall and precision restricted to answerable factors.

    Args:
        predicted: see behaviour
        gold: see behaviour
        answerable: see behaviour

    Returns:
        (recall, precision). Only factors whose supporting fact is in the input are scored (plan §15.1), so predicting or
        missing an unanswerable factor neither helps nor hurts.
    """
    answerable_set = set(answerable)
    pred = set(predicted) & answerable_set
    gold_a = set(gold) & answerable_set
    hit = pred & gold_a
    recall = len(hit) / len(gold_a) if gold_a else 1.0
    precision = len(hit) / len(pred) if pred else 1.0
    return recall, precision
