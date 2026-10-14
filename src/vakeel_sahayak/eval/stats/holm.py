"""Holm-Bonferroni correction within each family of comparisons (plan §15.9)."""

from __future__ import annotations


def holm_bonferroni(p_values: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Reject/accept per comparison.

    Args:
        p_values: see behaviour
        alpha: see behaviour

    Returns:
        Decisions.
    """
    raise NotImplementedError
