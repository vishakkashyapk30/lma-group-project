"""Approval gates as graph interrupts plus the export guard (plan §3.1, §16)."""

from __future__ import annotations

from vakeel_sahayak.record import gates as record_gates
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import GateId


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

    def approve(self, case_id: str, gate: GateId, acknowledged: list[str] | None = None) -> None:
        """Record approval and resume the interrupted graph. Raises if the checklist is not cleared.

        Args:
            case_id: see behaviour
            gate: see behaviour
            acknowledged: UNSUPPORTED fields counsel acknowledges
        """
        record_gates.approve_gate(self._log_for(case_id), case_id, gate, acknowledged)

    def assert_export_allowed(self, case_id: str) -> None:
        """Raise unless Gate 2 is approved for this very case (no bulk export; plan §11, §16).

        Args:
            case_id: see behaviour
        """
        record_gates.assert_export_allowed(self._log_for(case_id), case_id)
