"""Tools in drafting.approval (plan §3.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, GateId
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import ApprovalRequest


def request_approval(case_id: str, gate: GateId) -> ApprovalRequest:
    """Open an approval gate (graph interrupt) with its checklist. (plan §3.1)

    Args:
        case_id: see behaviour
        gate: see behaviour

    Returns:
        ApprovalRequest.
    """
    from vakeel_sahayak.record.gates import gate_status, open_gate
    from vakeel_sahayak.tools.runtime import get_runtime

    # Gate 1 (dossier) is requested by Peshkar, Gate 2 (export) by Vakeel (plan §3.3)
    requested_by = AgentName.PESHKAR.value if gate == GateId.GATE_1_DOSSIER else AgentName.VAKEEL.value
    log = get_runtime().event_log(case_id)
    status = gate_status(log, case_id, gate)
    open_gate(log, case_id, gate, requested_by, status)  # records the request only; approval is counsel's alone
    unresolved = (
        [f"UNSUPPORTED:{f}" for f in status.unresolved_unsupported]
        + [f"NEEDS_REVIEW:{i}" for i in status.unresolved_needs_review]
        + [f"UNANSWERED:{i}" for i in status.unresolved_unanswered]
    )
    return ApprovalRequest(gate=gate, checklist_open=bool(unresolved), unresolved=unresolved)


REQUEST_APPROVAL_SPEC = ToolSpec(
    name="request_approval",
    description="Open an approval gate (graph interrupt) with its checklist.",
    agents=[AgentName.VAKEEL, AgentName.PESHKAR],
    stores=[],
    plan_ref="§3.1",
)
