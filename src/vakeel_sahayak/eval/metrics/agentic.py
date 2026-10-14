"""Metrics: Task completion, pass^3, calls and tokens per case, repair success rate, objection recall, stale-claim rate (plan §15.8)."""

from __future__ import annotations

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet


def pass_hat_k(results: list[list[bool]], k: int = 3) -> float:
    """pass^k over repeated runs.

    Args:
        results: see behaviour
        k: see behaviour

    Returns:
        Rate.
    """
    raise NotImplementedError


def stale_claim_rate(brief: BailBrief, change_set: ChangeSet) -> float:
    """Claims still stating an old value.

    Args:
        brief: see behaviour
        change_set: see behaviour

    Returns:
        Rate.
    """
    raise NotImplementedError
