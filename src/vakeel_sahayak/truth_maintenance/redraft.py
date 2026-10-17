"""Incremental redrafting driver (plan §10) and the full-regeneration baseline (F2).

Planning, staleness and the merge (`plan_redraft`, `apply_redraft`, `diff_brief`) are pure and deterministic. The drafting of
the stale claims is Vakeel's (`VakeelAgent.redraft`); `redraft_incrementally` calls it for the planned claims only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.enums import ClaimState, Factor, FactorStance
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.truth_maintenance.staleness import factors_to_reopen, is_noop, mark_stale, stale_reasons

if TYPE_CHECKING:
    from vakeel_sahayak.agents.vakeel.agent import VakeelAgent


@dataclass
class RedraftPlan:
    """What an approved change set sets in motion (plan §10 steps 1-3)."""

    reopened_factors: list[Factor] = field(default_factory=list)  # Sutradhar re-plans retrieval for these only
    new_factors: list[Factor] = field(default_factory=list)  # reopened, no ground yet: may now be drafted
    dropped_factors: list[Factor] = field(default_factory=list)  # have a ground but no longer apply
    stale_claims: list[str] = field(default_factory=list)
    redraft_claims: list[str] = field(default_factory=list)  # ground ids Vakeel rewrites (stale, plus grounds of reopened factors)
    unchanged_claims: list[str] = field(default_factory=list)  # stay word for word
    reasons: dict[str, list[str]] = field(default_factory=dict)  # claim id -> why it is stale or redrafted

    @property
    def is_noop(self) -> bool:
        """Nothing to redo."""
        return not (self.redraft_claims or self.new_factors or self.dropped_factors)


def plan_redraft(brief: BailBrief, change_set: ChangeSet, applicable: dict[Factor, bool] | None = None) -> RedraftPlan:
    """The redraft plan for an approved change set (plan §10).

    Args:
        brief: the brief approved before the change
        change_set: the approved change set
        applicable: optional, per factor, whether it applies after the change (Sutradhar's new stance); decides which
            reopened factors are new (applicable, no ground yet) and which are dropped (a ground, no longer applicable). Without it
            every reopened factor without a ground is new and none is dropped.

    Returns:
        RedraftPlan.
    """
    if is_noop(change_set):
        return RedraftPlan(unchanged_claims=[g.id for g in brief.grounds])
    reasons = {k: list(v) for k, v in stale_reasons(brief, change_set).items()}
    reopened = factors_to_reopen(brief, change_set)
    have = {g.factor for g in brief.grounds}
    if applicable is None:
        new, dropped = [f for f in reopened if f not in have], []
    else:
        new = [f for f in reopened if f not in have and applicable.get(f) is True]
        dropped = [f for f in reopened if f in have and applicable.get(f) is False]
    stale = list(reasons)
    redraft = [g.id for g in brief.grounds if g.id in reasons]
    for g in brief.grounds:
        if g.factor in dropped and g.id not in redraft:
            redraft.append(g.id)
            reasons.setdefault(g.id, []).append(f"factor '{g.factor.value}' no longer applies")
    return RedraftPlan(
        reopened_factors=reopened, new_factors=new, dropped_factors=dropped, stale_claims=stale,
        redraft_claims=redraft, unchanged_claims=[g.id for g in brief.grounds if g.id not in redraft], reasons=reasons,
    )


@dataclass
class RedraftResult:
    """The merged brief and the marked changes (the UI's 'changed since last approval')."""

    brief: BailBrief
    changes: list[dict[str, str]] = field(default_factory=list)


def diff_brief(old: BailBrief, new: BailBrief, reasons: dict[str, list[str]] | None = None) -> list[dict[str, str]]:
    """Highlight what changed and why, for the brief view (plan §10 step 4).

    Args:
        old: the brief at the last approval
        new: the brief now
        reasons: optional claim id -> reasons (from the plan)

    Returns:
        Change rows {ground_id, claim, factor, change, reason, old, new}; `change` is 'changed', 'added', 'removed' or 'stale'. Unchanged
        claims have no row.
    """
    reasons = reasons or {}
    before = {g.id: g for g in old.grounds}
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for g in new.grounds:
        seen.add(g.id)
        o = before.get(g.id)
        why = "; ".join(reasons.get(g.id, []))
        if o is None:
            rows.append({"ground_id": g.id, "claim": g.id, "factor": g.factor.value, "change": "added", "reason": why or f"factor '{g.factor.value}' is newly available", "old": "", "new": g.argument})
        elif o.argument != g.argument or o.authorities != g.authorities or o.stance != g.stance:
            rows.append({"ground_id": g.id, "claim": g.id, "factor": g.factor.value, "change": "changed", "reason": why or "redrafted", "old": o.argument, "new": g.argument})
        elif g.state == ClaimState.STALE and o.state != ClaimState.STALE:
            rows.append({"ground_id": g.id, "claim": g.id, "factor": g.factor.value, "change": "stale", "reason": why or "a dependency changed", "old": o.argument, "new": g.argument})
    for gid, o in before.items():
        if gid not in seen:
            rows.append({"ground_id": gid, "claim": gid, "factor": o.factor.value, "change": "removed", "reason": "; ".join(reasons.get(gid, [])) or "no longer applies", "old": o.argument, "new": ""})
    return rows


def apply_redraft(brief: BailBrief, redrafted: list[Ground], plan: RedraftPlan) -> RedraftResult:
    """Merge redrafted grounds into the brief; every other ground is kept as it was, byte for byte (plan §10 steps 3-4).

    A redrafted ground replaces the ground with its id (or, failing that, the ground of its factor) and keeps the state Vakeel gave it (CURRENT, or STALE when its factor no longer applies). A ground
    with no redraft that the plan lists as stale stays, marked STALE. A redrafted ground with no old one is appended as new.
    Grounds outside the plan are never replaced.

    Args:
        brief: the brief before the change
        redrafted: grounds Vakeel rewrote
        plan: the RedraftPlan

    Returns:
        RedraftResult: the new brief and its change rows (with reasons).
    """
    by_id = {g.id: g for g in redrafted}
    by_factor = {g.factor: g for g in redrafted}
    allowed = set(plan.redraft_claims)
    used: set[str] = set()
    grounds: list[Ground] = []
    for g in brief.grounds:
        rep = by_id.get(g.id) if g.id in allowed else None
        if rep is None and g.id in allowed:
            rep = by_factor.get(g.factor)
        if rep is not None:
            used.add(rep.id)
            grounds.append(rep.model_copy(update={"id": g.id}, deep=True))
        elif g.id in plan.stale_claims or g.id in plan.redraft_claims:
            grounds.append(g.model_copy(update={"state": ClaimState.STALE}, deep=True))
        else:
            grounds.append(g.model_copy(deep=True))
    taken = {g.id for g in grounds}
    have = {g.factor for g in grounds}
    for g in redrafted:
        if g.id in used or g.factor in have:
            continue
        gid = g.id
        n = 1 + max((int(x.id[1:]) for x in grounds if x.id[:1] == "G" and x.id[1:].isdigit()), default=0)
        if gid in taken:
            gid = f"G{n}"
        grounds.append(g.model_copy(update={"id": gid, "state": ClaimState.CURRENT}, deep=True))
        taken.add(gid)
        have.add(g.factor)
    merged = brief.model_copy(update={"grounds": grounds}, deep=True)
    return RedraftResult(brief=merged, changes=diff_brief(brief, merged, plan.reasons))


def _carried_packs(state: CaseGraphState, brief: BailBrief, factors: set[Factor]) -> list[EvidencePack]:
    """The state's evidence packs, plus a bare pack (the ground's own stance, no new retrieval) for each of `factors` that has none."""
    packs = list(state.evidence_packs)
    have = {p.factor for p in packs}
    for g in brief.grounds:
        if g.factor in factors and g.factor not in have:
            packs.append(EvidencePack(factor=g.factor, stance=g.stance))
            have.add(g.factor)
    return packs


def _vakeel(state: CaseGraphState, max_rounds: int | None = None) -> VakeelAgent:
    """Vakeel over the state's case (its LLM and NLI come from the model factory unless the caller set them)."""
    from vakeel_sahayak.agents.vakeel.agent import VakeelAgent

    try:
        log = state.event_log()
    except Exception:  # noqa: BLE001 - a state with no log still redrafts; the agent opens the configured one
        log = None
    return VakeelAgent(case_id=state.case_id, log=log, switches=state.switches, before=state.before, max_rounds=max_rounds)


def redraft_incrementally(state: CaseGraphState, change_set: ChangeSet) -> BailBrief:
    """Re-plan only reopened factors, redraft only stale claims, re-spar only changed grounds, re-check only changed claims; unchanged claims stay word for word (plan §10 steps 3-4).

    The plan (`plan_redraft`) names the stale claims and the factors that became available; Vakeel redrafts exactly those
    (one model call per ground; each is checked, and one that fails its check is flagged NEEDS_REVIEW rather than re-asked) from the state's evidence packs, and `apply_redraft` merges only those grounds, so every
    other ground is the old record, byte for byte. A change set that changes nothing costs no model call.

    Args:
        state: the graph state (its brief is the one approved before the change; its packs are Sutradhar's re-run ones)
        change_set: the approved change set

    Returns:
        Updated BailBrief.
    """
    brief = state.brief or BailBrief(case_id=state.case_id)
    packs = state.evidence_packs
    applicable = {p.factor: p.stance != FactorStance.NOT_APPLICABLE for p in packs}
    plan = plan_redraft(brief, change_set, applicable)
    if plan.is_noop:
        marked = brief.model_copy(deep=True)
        mark_stale(marked, change_set)
        return marked
    packs = _carried_packs(state, brief, {g.factor for g in brief.grounds if g.id in set(plan.redraft_claims)})
    agent = _vakeel(state, max_rounds=0)  # one model call per claim: a redrafted claim that fails its check is flagged for counsel, not re-asked
    targets = list(plan.redraft_claims) + [f.value for f in plan.new_factors]
    drafted = agent.redraft(targets, state.model_copy(update={"brief": brief, "evidence_packs": packs}), packs)
    merged = apply_redraft(brief, drafted.grounds, plan).brief
    return merged.model_copy(update={"statutory_position": drafted.statutory_position, "open_issues": drafted.open_issues})


def full_regeneration(state: CaseGraphState) -> BailBrief:
    """Baseline for F2: regenerate everything (plan §15.6).

    Every ground of the state's brief (one per factor, in order) is drafted, checked and repaired afresh by Vakeel, with
    the state's evidence packs where it has them.

    Args:
        state: see behaviour

    Returns:
        BailBrief, all grounds new.
    """
    brief = state.brief or BailBrief(case_id=state.case_id)
    packs = _carried_packs(state, brief, {g.factor for g in brief.grounds})
    fresh = state.model_copy(update={"brief": None, "evidence_packs": packs})
    agent = _vakeel(state)
    grounds = agent.draft_grounds(fresh, packs)
    if state.switches.check_and_repair:
        grounds = agent.repair_or_flag(agent.check_claims(grounds))
    return agent.assemble_brief(fresh, grounds)
