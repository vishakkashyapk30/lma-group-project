"""Incremental redrafting driver (plan §10) and the full-regeneration baseline (F2)."""

from __future__ import annotations

from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet


def redraft_incrementally(state: CaseGraphState, change_set: ChangeSet) -> BailBrief:
    """Re-plan only reopened factors, redraft only stale claims, re-spar only changed grounds, re-check only changed claims; unchanged claims stay word for word (plan §10 steps 3-4).

    Args:
        state: see behaviour
        change_set: see behaviour

    Returns:
        Updated BailBrief.
    """
    raise NotImplementedError


def diff_brief(old: BailBrief, new: BailBrief) -> list[dict[str, str]]:
    """Highlight what changed and why, for the brief view (plan §10 step 4).

    Args:
        old: see behaviour
        new: see behaviour

    Returns:
        Change rows.
    """
    raise NotImplementedError


def full_regeneration(state: CaseGraphState) -> BailBrief:
    """Baseline for F2: regenerate everything (plan §15.6).

    Args:
        state: see behaviour

    Returns:
        BailBrief.
    """
    raise NotImplementedError
