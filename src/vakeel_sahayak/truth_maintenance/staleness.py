"""Staleness propagation over claim dependencies (plan §10).

All pure: a change set in, claim ids and reasons out. `stale_events` builds the CLAIM_STALED events (actor
`TRUTH_MAINTENANCE`), `record_stale` appends them to a log.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields
from vakeel_sahayak.schemas.enums import ClaimState, EventKind, Factor
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.truth_maintenance.dependencies import build_index, field_value_hashes

_FIELD_ORDER = {n: i for i, n in enumerate(DossierFields.model_fields)}
ACTOR = "TRUTH_MAINTENANCE"
# Dossier fields that also speak to a factor but are not in Vakeel's FACTOR_FIELDS.
EXTRA_FIELD_FACTORS: dict[str, tuple[str, ...]] = {
    "previous_bail": ("antecedents", "parity_with_co_accused"),
    "personal": ("flight_risk", "health_age_family"),
}


def effective_fields(change_set: ChangeSet) -> list[FieldChange]:
    """The changed fields that really changed (old and new hash differ); a no-op entry is dropped."""
    return [f for f in change_set.fields if f.old_hash != f.new_hash]


def is_noop(change_set: ChangeSet) -> bool:
    """True when the change set changes nothing."""
    return not (effective_fields(change_set) or change_set.new_event_ids or change_set.rights_changed or change_set.authorities_changed)


def compute_change_set(
    old: CaseDossier, new: CaseDossier, old_rights: RightsReport, new_rights: RightsReport,
    trigger: str = "new_document", new_event_ids: list[str] | None = None,
) -> ChangeSet:
    """Diff approved states into a change set (plan §7.4).

    Fields are compared by the hash of their value (`hash_value`; a field with no value has no hash, and a changed source or status alone is not a change); Radar checks by status, detail, rule and dates
    (the verification date is not a change).

    Args:
        old: the dossier at the last approval
        new: the dossier now
        old_rights: the RightsReport at the last approval
        new_rights: the RightsReport now
        trigger: new_document | clock | counsel_edit
        new_event_ids: ids of timeline events added since

    Returns:
        ChangeSet.
    """
    def _checks(r: RightsReport) -> dict[str, Any]:
        return {c.check.value: c.model_dump(mode="json", exclude={"last_verified"}) for c in r.checks}

    a, b = _checks(old_rights), _checks(new_rights)
    before, after = field_value_hashes(old, skip_empty=True), field_value_hashes(new, skip_empty=True)
    changed = [FieldChange(field=n, old_hash=before.get(n), new_hash=after.get(n)) for n in after.keys() | before.keys() if before.get(n) != after.get(n)]
    changed.sort(key=lambda f: _FIELD_ORDER.get(f.field, len(_FIELD_ORDER)))
    return ChangeSet(
        case_id=new.case_id,
        trigger=trigger,
        fields=changed,
        new_event_ids=list(new_event_ids or []),
        rights_changed=sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)),
    )


def stale_reasons(brief: BailBrief, change_set: ChangeSet) -> dict[str, list[str]]:
    """Why each claim is stale: claim id -> reasons, in ground order. Claims that cite a stale claim follow transitively."""
    idx = build_index(brief)
    reasons: dict[str, list[str]] = {}

    def add(ids: list[str], why: str) -> None:
        for i in ids:
            if why not in reasons.setdefault(i, []):
                reasons[i].append(why)

    for f in effective_fields(change_set):
        add(idx.by_field.get(f.field, []), f"dossier field '{f.field}' changed")
    for e in change_set.new_event_ids:
        add(idx.by_event.get(e, []), f"timeline event '{e}' changed")
    for r in change_set.rights_changed:
        add(idx.by_rights.get(r, []), f"Rights Radar check '{r}' changed")
    for a in change_set.authorities_changed:
        add(idx.by_authority.get(a, []), f"authority '{a}' changed its transfer or good-law flag")
    frontier = list(reasons)
    while frontier:
        nxt: list[str] = []
        for c in frontier:
            for citing in idx.citing(c):
                if citing not in reasons:
                    nxt.append(citing)
                add([citing], f"cites stale claim {c}")
        frontier = nxt
    order = {g.id: n for n, g in enumerate(brief.grounds)}
    return dict(sorted(reasons.items(), key=lambda kv: order.get(kv[0], len(order))))


def mark_stale(brief: BailBrief, change_set: ChangeSet) -> list[str]:
    """Mark claims with a changed dependency STALE; claims citing a stale claim become stale too (plan §10 step 1).

    The brief is changed in place (ground.state); a change set that changes nothing marks nothing.

    Args:
        brief: the approved brief
        change_set: the approved change set

    Returns:
        Ids of stale claims, in ground order.
    """
    ids = list(stale_reasons(brief, change_set))
    for g in brief.grounds:
        if g.id in ids:
            g.state = ClaimState.STALE
    return ids


def stale_events(brief: BailBrief, change_set: ChangeSet) -> list[Event]:
    """One CLAIM_STALED event per stale claim (actor TRUTH_MAINTENANCE; `inputs.claim`, `outputs.claim_ids` and the reasons)."""
    out = []
    for cid, why in stale_reasons(brief, change_set).items():
        out.append(
            Event(
                event_id="", case_id=brief.case_id, ts="", kind=EventKind.CLAIM_STALED, actor=ACTOR, tool="truth_maintenance.mark_stale",
                inputs={"claim": cid}, outputs={"claim_ids": [cid], "reason": "; ".join(why), "reasons": why, "trigger": change_set.trigger},
            )
        )
    return out


def record_stale(log: Any, brief: BailBrief, change_set: ChangeSet, parent_id: str | None = None) -> list[str]:
    """Mark the claims stale and append their CLAIM_STALED events to `log` (anything with `append(event)`).

    Returns:
        Ids of stale claims.
    """
    events = stale_events(brief, change_set)
    for ev in events:
        log.append(ev.model_copy(update={"parent_id": parent_id}))
    return mark_stale(brief, change_set)


def touched_factors(change_set: ChangeSet) -> list[Factor]:
    """Factors that read a changed dossier field or Radar check: they may newly apply or drop out."""
    from vakeel_sahayak.agents.vakeel.facts import FACTOR_FIELDS, FACTOR_RIGHTS

    fields = {f.field for f in effective_fields(change_set)}
    rights = set(change_set.rights_changed)
    out: set[str] = set()
    for fac, used in FACTOR_FIELDS.items():
        if fields & set(used):
            out.add(fac)
    for fac, used in FACTOR_RIGHTS.items():
        if rights & set(used):
            out.add(fac)
    for name in fields:
        out.update(EXTRA_FIELD_FACTORS.get(name, ()))
    return [f for f in Factor if f.value in out]


def factors_to_reopen(brief: BailBrief, change_set: ChangeSet) -> list[Factor]:
    """Which factors may newly apply or drop out (plan §10 step 2).

    A factor reopens when its ground has a claim with a changed dependency of its own (a claim stale only because it cites a stale claim is redrafted, but its factor's evidence did not change), or when it reads a changed dossier field or Radar check (so a filed
    charge sheet opens `charge_sheet_filed`, `trial_delay` and `witness_tampering`). A no-op change set reopens none.

    Args:
        brief: the approved brief
        change_set: the approved change set

    Returns:
        Factors to re-plan, in Appendix A order.
    """
    if is_noop(change_set):
        return []
    direct = {c for c, why in stale_reasons(brief, change_set).items() if any(not w.startswith("cites stale") for w in why)}
    out = {g.factor for g in brief.grounds if g.id in direct}
    out.update(touched_factors(change_set))
    return [f for f in Factor if f in out]
