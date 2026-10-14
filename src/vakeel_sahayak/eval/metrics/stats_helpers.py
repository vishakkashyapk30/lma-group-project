"""Metrics: Shared helpers for per-case averaging over runs (plan §15.9) (plan §15.8)."""

from __future__ import annotations


def average_over_runs(per_run: list[dict[str, float]]) -> dict[str, float]:
    """Average runs per case.

    Args:
        per_run: see behaviour

    Returns:
        Averages.
    """
    raise NotImplementedError
