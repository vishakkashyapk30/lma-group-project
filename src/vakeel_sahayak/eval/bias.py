"""Results by offence type, court, outcome and input kind (plan §16 Bias)."""

from __future__ import annotations


def breakdown(run_dir: str) -> dict[str, dict[str, float]]:
    """Group metrics and report gaps.

    Args:
        run_dir: see behaviour

    Returns:
        Metrics by group.
    """
    raise NotImplementedError
