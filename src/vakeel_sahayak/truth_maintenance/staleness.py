"""Staleness propagation over claim dependencies (plan §10)."""

from __future__ import annotations

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import Factor
from vakeel_sahayak.schemas.rights_report import RightsReport


def compute_change_set(
    old: CaseDossier, new: CaseDossier, old_rights: RightsReport, new_rights: RightsReport
) -> ChangeSet:
    """Diff approved states into a change set (plan §7.4).

    Args:
        old: see behaviour
        new: see behaviour
        old_rights: see behaviour
        new_rights: see behaviour

    Returns:
        ChangeSet.
    """
    raise NotImplementedError


def mark_stale(brief: BailBrief, change_set: ChangeSet) -> list[str]:
    """Mark claims with a changed dependency STALE; claims citing a stale claim become stale too (plan §10 step 1).

    Args:
        brief: see behaviour
        change_set: see behaviour

    Returns:
        Ids of stale claims.
    """
    raise NotImplementedError


def factors_to_reopen(brief: BailBrief, change_set: ChangeSet) -> list[Factor]:
    """Which factors may newly apply or drop out (plan §10 step 2).

    Args:
        brief: see behaviour
        change_set: see behaviour

    Returns:
        Factors to re-plan.
    """
    raise NotImplementedError
