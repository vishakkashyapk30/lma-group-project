"""Tools in drafting.approval (plan §3.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, GateId
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.types import ApprovalRequest


def request_approval(case_id: str, gate: GateId) -> ApprovalRequest | ToolError:
    """Open an approval gate (graph interrupt) with its checklist. (plan §3.1)

    Args:
        case_id: exactly one case
        gate: GATE_1_DOSSIER or GATE_2_EXPORT

    Returns:
        ApprovalRequest listing the open checklist items (field names for Gate 1; ground and objection ids for Gate 2),
        or a ToolError for a bad case id or gate. It never approves.
    """
    from vakeel_sahayak.orchestration.gates import GateGuard
    from vakeel_sahayak.tools.drafting.export_tool import single_case_id

    one = single_case_id("request_approval", case_id)
    if isinstance(one, ToolError):
        return one
    try:
        which = GateId(gate)
    except ValueError:
        return ToolError(tool="request_approval", kind="invalid_input", message=f"gate must be one of {[g.value for g in GateId]}", retryable=False)
    guard = GateGuard()
    status = guard.status(one, which)
    guard.open(one, which)  # records the request only (Peshkar opens Gate 1, Vakeel Gate 2); approval is counsel's alone
    unresolved = [*status.unresolved_unsupported, *status.unresolved_needs_review, *status.unresolved_unanswered]
    return ApprovalRequest(gate=which, checklist_open=bool(unresolved), unresolved=unresolved)


REQUEST_APPROVAL_SPEC = ToolSpec(
    name="request_approval",
    description="Open an approval gate (graph interrupt) with its checklist.",
    agents=[AgentName.VAKEEL, AgentName.PESHKAR],
    stores=[],
    plan_ref="§3.1",
)
