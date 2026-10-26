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
from vakeel_sahayak.schemas.enums import EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event

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
    fields = _record_resolutions(log, case_id, body.acknowledged_fields)
    guard = GateGuard(log)
    try:
        guard.approve(case_id, gate, acknowledged=fields)
    except ChecklistNotCleared as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return guard.status(case_id, gate)


RESOLVABLE = ("NEEDS_REVIEW:", "UNANSWERED:")


def _record_resolutions(log: EventLog, case_id: str, acknowledged: list[str]) -> list[str]:
    """Record counsel's resolutions sent with an approval and return the plain field names to acknowledge.

    The workspace sends what counsel resolved as `NEEDS_REVIEW:<ground>` and `UNANSWERED:<objection>` next to the UNSUPPORTED field
    names. Each becomes counsel's USER_ACTION `resolve` event (the record `gate_status` reads), once; an open issue (`issue-<n>`) is
    not on the server's checklist and is ignored.
    """
    already = {
        str(e.inputs.get("item"))
        for e in log.read(case_id)
        if e.kind == EventKind.USER_ACTION and e.inputs.get("action") == "resolve"
    }
    fields: list[str] = []
    for entry in acknowledged:
        if not entry.startswith(RESOLVABLE):
            fields.append(entry)
            continue
        item = entry.split(":", 1)[1]
        if item.startswith("issue-") or item in already:
            continue
        log.append(Event(event_id="", ts="", case_id=case_id, kind=EventKind.USER_ACTION, actor=COUNSEL,
                         inputs={"action": "resolve", "item": item}, outputs={}))
        already.add(item)
    return fields
