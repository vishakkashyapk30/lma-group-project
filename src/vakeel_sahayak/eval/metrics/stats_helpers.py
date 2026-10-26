"""Metrics: Shared helpers for per-case averaging over runs (plan §15.9) (plan §15.8)."""

from __future__ import annotations


def average_over_runs(per_run: list[dict[str, float]]) -> dict[str, float]:
    """Average runs per case.

    Args:
        per_run: see behaviour

    Returns:
        Each metric averaged across the runs (plan §15.9: three runs averaged per case).
    """
    if not per_run:
        return {}
    keys = per_run[0].keys()
    return {key: sum(run[key] for run in per_run) / len(per_run) for key in keys}
