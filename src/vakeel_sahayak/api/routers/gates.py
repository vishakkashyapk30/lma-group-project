"""Router 'gates' (plan §13.1, §13.5, §16): the checklist modal and the two approvals.

Gate 1 (after the dossier) needs every UNSUPPORTED field resolved or acknowledged; Gate 2 (before export) needs every
NEEDS_REVIEW ground and UNANSWERED objection resolved. Approval is counsel's alone (a GATE_APPROVED event by `counsel`),
recorded for the case in the URL only (no bulk approval). A checklist that is not cleared is a 409.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import get_event_log
from vakeel_sahayak.api.models import ApproveRequest
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.record.gates import ChecklistNotCleared
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import GateId

router = APIRouter(prefix="/api/cases/{case_id}/gates", tags=["gates"])


@router.get("/{gate}", response_model=GateStatus)
async def get_gate(case_id: str, gate: GateId, log: Annotated[EventLog, Depends(get_event_log)]) -> GateStatus:
    """Gate checklist (plan §13.5)."""
    service.require_case(log, case_id)
    return GateGuard(log).status(case_id, gate)


@router.post("/{gate}/approve", response_model=GateStatus)
async def approve_gate(case_id: str, gate: GateId, body: ApproveRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> GateStatus:
    """Approve Gate 1 or Gate 2 once the checklist is cleared (counsel only); 409 while items remain."""
    service.require_case(log, case_id)
    guard = GateGuard(log)
    try:
        guard.approve(case_id, gate, acknowledged=body.acknowledged_fields)
    except ChecklistNotCleared as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return guard.status(case_id, gate)
