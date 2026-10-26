"""Approval records and the export guard, enforced against the event log (plan §3.1, §13.5, §16).

Approvals come only from counsel: `approve_gate` is the one function that writes GATE_APPROVED, always with actor
'counsel', and the log itself refuses GATE_APPROVED from anyone else. Agents can only open a gate.
"""

from __future__ import annotations

from vakeel_sahayak.record import views
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import ClaimCheck, EventKind, FieldStatus, GateId, SparringVerdict
from vakeel_sahayak.schemas.events import COUNSEL, Event


class GateNotApproved(PermissionError):
    """Raised when an action needs an approval that is not on record for this case (plan §16)."""


class ChecklistNotCleared(ValueError):
    """Raised when counsel tries to approve a gate while checklist items are unresolved (plan §13.5)."""


def gate_status(log: EventLog, case_id: str, gate: GateId) -> GateStatus:
    """Compute the gate checklist: unresolved UNSUPPORTED, NEEDS_REVIEW and UNANSWERED items (plan §13.5).

    Args:
        log: the case's event log
        case_id: see behaviour
        gate: which gate

    Returns:
        GateStatus; `open` is True while the gate has not been approved.
    """
    state = CaseState(case_id, log)
    dossier = state.dossier()
    approved = [e for e in state.events() if e.kind == EventKind.GATE_APPROVED and e.inputs.get("gate") == gate.value]
    acknowledged = set(approved[-1].inputs.get("acknowledged") or []) if approved else set()  # counsel's acknowledgement stands once approved
    unsupported = [
        n for n in type(dossier.fields).model_fields
        if getattr(dossier.fields, n).status == FieldStatus.UNSUPPORTED and n not in acknowledged
    ]
    brief = state.brief()
    resolved = {
        str(e.inputs.get("item"))
        for e in state.events()
        if e.kind == EventKind.USER_ACTION and e.inputs.get("action") == "resolve"
    }
    review = [g.id for g in brief.grounds if g.check == ClaimCheck.NEEDS_REVIEW and g.id not in resolved]
    unanswered = [o.id for o in state.sparring().objections if o.verdict == SparringVerdict.UNANSWERED and o.id not in resolved]
    # Gate 1 covers the dossier; Gate 2 adds the brief and the sparring record.
    if gate == GateId.GATE_1_DOSSIER:
        review, unanswered = [], []
    return GateStatus(
        gate=gate,
        open=not views.gate_is_approved(state.events(), gate),
        unresolved_unsupported=unsupported,
        unresolved_needs_review=review,
        unresolved_unanswered=unanswered,
    )


def open_gate(log: EventLog, case_id: str, gate: GateId, requested_by: str, status: GateStatus | None = None) -> Event:
    """Record that an agent opened an approval gate (an interrupt waiting for counsel). Never approves anything."""
    status = status or gate_status(log, case_id, gate)
    return log.append(
        Event(
            event_id="",
            ts="",
            case_id=case_id,
            kind=EventKind.GATE_OPENED,
            actor=requested_by,
            tool="request_approval",
            inputs={"gate": gate.value},
            outputs={"gate": gate.value, "checklist": status.model_dump(mode="json")},
        )
    )


def approve_gate(log: EventLog, case_id: str, gate: GateId, acknowledged: list[str] | None = None) -> Event:
    """Record counsel's approval. Raises ChecklistNotCleared if items remain (UNSUPPORTED ones may be acknowledged).

    Args:
        log: the case's event log
        case_id: see behaviour
        gate: which gate
        acknowledged: UNSUPPORTED fields counsel acknowledges

    Returns:
        The GATE_APPROVED event (actor 'counsel').
    """
    if gate == GateId.GATE_2_EXPORT:  # Gate 2 covers the brief and the sparring record: it exists only once Gate 1 is approved and Vakeel has opened it
        events = log.read(case_id)
        if not views.gate_is_approved(events, GateId.GATE_1_DOSSIER):
            raise GateNotApproved("Gate 2 cannot be approved before counsel has approved Gate 1 (plan §3.1)")
        if views.gate_event(events, GateId.GATE_2_EXPORT) is None:
            raise GateNotApproved("Gate 2 has not been opened: there is no brief to approve yet (plan §3.1)")
    status = gate_status(log, case_id, gate)
    ack = set(acknowledged or [])
    blocking = [f"UNSUPPORTED:{f}" for f in status.unresolved_unsupported if f not in ack]
    blocking += [f"NEEDS_REVIEW:{i}" for i in status.unresolved_needs_review]
    blocking += [f"UNANSWERED:{i}" for i in status.unresolved_unanswered]
    if blocking:
        raise ChecklistNotCleared(f"{gate.value} checklist not cleared: {', '.join(blocking)}")
    outputs: dict[str, str] = {"gate": gate.value}
    if gate == GateId.GATE_1_DOSSIER:  # the change-detection baseline (plan §7.4)
        outputs["dossier_hash"] = views.dossier_hash(CaseState(case_id, log).dossier())
    return log.append(
        Event(
            event_id="",
            ts="",
            case_id=case_id,
            kind=EventKind.GATE_APPROVED,
            actor=COUNSEL,
            inputs={"gate": gate.value, "acknowledged": sorted(ack)},
            outputs=outputs,
        )
    )


def assert_export_allowed(log: EventLog, case_id: str) -> None:
    """Raise unless counsel's Gate 2 approval for this very case is the latest word in this case's log.

    Approvals in other cases do not count (no bulk export; plan §11, §16), and neither does a Gate 2 approval that
    was later rejected or reopened.

    Args:
        log: the event log to check
        case_id: the case about to be exported

    Raises:
        GateNotApproved: if there is no valid Gate 2 approval.
    """
    events = log.read(case_id)
    if not views.gate_is_approved(events, GateId.GATE_2_EXPORT):
        raise GateNotApproved(f"export refused: no Gate 2 approval by counsel on record for case {case_id!r}")
