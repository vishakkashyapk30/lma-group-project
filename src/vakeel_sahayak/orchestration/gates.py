"""Approval gates as graph interrupts plus the export guard (plan §3.1, §16).

`GateGuard` checks and records approvals through the case's event log (record/gates.py): only counsel approves, and
export works only after Gate 2 for that very case. `await_gate` is the node-side half: inside a LangGraph node it opens
the gate (one GATE_OPENED event), then calls `langgraph.types.interrupt` with the checklist so the run pauses until
counsel answers; when the run is resumed the node runs again, finds counsel's GATE_APPROVED in the log and passes.
Approval is never taken from the resume value, only from the log (an agent cannot approve its own gate).
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.record import gates as record_gates
from vakeel_sahayak.record import views
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import AgentName, EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event

GATE_REQUESTERS: dict[GateId, AgentName] = {GateId.GATE_1_DOSSIER: AgentName.PESHKAR, GateId.GATE_2_EXPORT: AgentName.VAKEEL}


class GateGuard:
    """Enforces that export works only after Gate 2, in code (plan §16). Batch mode never exports in bulk.

    Checks and records go through the case's event log (record/gates.py). Resuming an interrupted LangGraph run
    after `approve` is the graph's job (Phase 2).
    """

    def __init__(self, log: EventLog | None = None) -> None:
        """Bind to an event log; None uses the tool runtime's per-case log.

        Args:
            log: event log holding the case's approvals
        """
        self._log = log

    def _log_for(self, case_id: str) -> EventLog:
        """The injected log, or the runtime's log for the case."""
        if self._log is not None:
            return self._log
        from vakeel_sahayak.tools.runtime import get_runtime

        return get_runtime().event_log(case_id)

    def status(self, case_id: str, gate: GateId) -> GateStatus:
        """Compute the gate checklist: unresolved UNSUPPORTED, NEEDS_REVIEW and UNANSWERED items (plan §13.5).

        Args:
            case_id: see behaviour
            gate: see behaviour

        Returns:
            GateStatus.
        """
        return record_gates.gate_status(self._log_for(case_id), case_id, gate)

    def is_approved(self, case_id: str, gate: GateId) -> bool:
        """True when counsel's approval is the latest word on the gate."""
        return views.gate_is_approved(self._log_for(case_id).read(case_id), GateId(gate))

    def is_open(self, case_id: str, gate: GateId) -> bool:
        """True when the gate's latest decisive event is GATE_OPENED (waiting for counsel)."""
        ev = views.gate_event(self._log_for(case_id).read(case_id), GateId(gate))
        return ev is not None and ev.kind == EventKind.GATE_OPENED

    def open(self, case_id: str, gate: GateId, requested_by: AgentName | str | None = None) -> Event:
        """Record that an agent opened the gate (never approves). Peshkar opens Gate 1, Vakeel Gate 2 by default."""
        who = requested_by or GATE_REQUESTERS[GateId(gate)]
        return record_gates.open_gate(self._log_for(case_id), case_id, GateId(gate), str(getattr(who, "value", who)))

    def approve(self, case_id: str, gate: GateId, acknowledged: list[str] | None = None) -> None:
        """Record approval and resume the interrupted graph. Raises if the checklist is not cleared.

        Args:
            case_id: see behaviour
            gate: see behaviour
            acknowledged: UNSUPPORTED fields counsel acknowledges
        """
        record_gates.approve_gate(self._log_for(case_id), case_id, gate, acknowledged)

    def reject(self, case_id: str, gate: GateId, reason: str = "") -> Event:
        """Record counsel's rejection (sends the case back; revokes an earlier approval of the gate)."""
        return self._log_for(case_id).append(
            Event(
                event_id="", ts="", case_id=case_id, kind=EventKind.GATE_REJECTED, actor=COUNSEL,
                inputs={"gate": GateId(gate).value, "reason": reason}, outputs={"gate": GateId(gate).value},
            )
        )  # fmt: skip

    def assert_export_allowed(self, case_id: str) -> None:
        """Raise unless Gate 2 is approved for this very case (no bulk export; plan §11, §16).

        Args:
            case_id: see behaviour
        """
        record_gates.assert_export_allowed(self._log_for(case_id), case_id)


def gate_decision(log: EventLog, case_id: str, gate: GateId) -> str | None:
    """'approved', 'rejected', 'open' or None (never opened) for a gate, from the log."""
    ev = views.gate_event(log.read(case_id), GateId(gate))
    if ev is None:
        return None
    return {EventKind.GATE_APPROVED: "approved", EventKind.GATE_REJECTED: "rejected"}.get(ev.kind, "open")


def await_gate(state: Any, gate: GateId, *, log: EventLog | None = None, requested_by: AgentName | str | None = None, interrupt: bool = True) -> Any:
    """Pause the graph at a gate until counsel decides (plan §3.3: the two gates are interrupts).

    Call it inside the gate node. It reads the gate's latest decisive event in the log:

    - approved by counsel: returns at once with the gate 'approved' (`pending_gate` cleared);
    - rejected by counsel: returns with the gate 'rejected' (the wiring routes back to Peshkar or Vakeel, whose
      `request_approval` re-opens the gate after the rework);
    - open, or never opened (then it opens it, once): with `interrupt=True` it calls `langgraph.types.interrupt(payload)`
      so LangGraph pauses the run; on resume the node runs again and finds counsel's decision in the log. The resume
      value is never trusted as an approval. Outside LangGraph (`interrupt=False`, or langgraph missing) it returns
      with the gate 'open' and `pending_gate` set, so a plain state machine stops there.

    Args:
        state: CaseGraphState
        gate: which gate
        log: the case's event log (default: `state.event_log()`)
        requested_by: the agent opening the gate (default: Peshkar for Gate 1, Vakeel for Gate 2)
        interrupt: use LangGraph's interrupt

    Returns:
        A copy of the state with `gates[gate]` and `pending_gate` updated.
    """
    gate = GateId(gate)
    log = log or state.event_log()
    guard = GateGuard(log)
    case_id = state.case_id

    def _with(decision: str) -> Any:
        gates = {**state.gates, gate.value: decision}
        return state.model_copy(update={"gates": gates, "pending_gate": None if decision == "approved" else gate})

    decision = gate_decision(log, case_id, gate)
    if decision in ("approved", "rejected"):
        return _with(decision)
    if decision is None:
        guard.open(case_id, gate, requested_by)
    if interrupt:
        try:
            from langgraph.types import interrupt as lg_interrupt
        except ImportError:  # pragma: no cover - langgraph is a core dependency
            lg_interrupt = None
        if lg_interrupt is not None:
            status = guard.status(case_id, gate)
            lg_interrupt({"case_id": case_id, "gate": gate.value, "checklist": status.model_dump(mode="json")})
            after = gate_decision(log, case_id, gate)
            return _with(after if after in ("approved", "rejected") else "open")
    return _with("open")
