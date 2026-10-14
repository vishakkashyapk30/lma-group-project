"""Paired bootstrap 95% confidence intervals (plan §15.9)."""

from __future__ import annotations


def paired_bootstrap_ci(
    a: list[float], b: list[float], n_boot: int = 10000, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Bootstrap the mean paired difference.

    Args:
        a: see behaviour
        b: see behaviour
        n_boot: see behaviour
        alpha: see behaviour

    Returns:
        (mean diff, lo, hi).
    """
    raise NotImplementedError
