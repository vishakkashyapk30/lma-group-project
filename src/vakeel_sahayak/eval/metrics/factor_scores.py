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
        (recall, precision).
    """
    raise NotImplementedError
