"""Labeler agreement and re-running main results with each labeler alone (plan §15.1)."""

from __future__ import annotations


def run(out_dir: str) -> dict[str, float]:
    """Agreement stats and single-labeler reruns.

    Args:
        out_dir: see behaviour

    Returns:
        Metrics.
    """
    raise NotImplementedError
