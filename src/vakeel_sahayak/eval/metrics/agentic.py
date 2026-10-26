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
        Share of cases where all k runs pass.
    """
    if not results:
        return 0.0
    return sum(1 for runs in results if all(runs[:k])) / len(results)


def stale_claim_rate(brief: BailBrief, change_set: ChangeSet) -> float:
    """Share of claims that still state the old value of a field the change set touched (plan §10, §15.8).

    The denominator is the grounds that depend on a changed field; a ground is stale when the hash it depends on is still
    the field's old hash.

    Args:
        brief: the current brief
        change_set: the fields that changed, with their old and new hashes

    Returns:
        Stale claims / claims depending on a changed field (0.0 when none depend on one).
    """
    changed = {fc.field: fc for fc in change_set.fields}
    denom = 0
    stale = 0
    for ground in brief.grounds:
        facts = ground.depends_on.facts if ground.depends_on else {}
        touched = [f for f in facts if f in changed]
        if not touched:
            continue
        denom += 1
        if any(facts[f] == changed[f].old_hash for f in touched):
            stale += 1
    return stale / denom if denom else 0.0
