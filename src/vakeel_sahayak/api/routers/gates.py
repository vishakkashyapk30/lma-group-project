"""Router 'gates' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter

from vakeel_sahayak.api.models import ApproveRequest
from vakeel_sahayak.schemas.case import GateStatus
from vakeel_sahayak.schemas.enums import GateId

router = APIRouter(prefix="/api/cases/{case_id}/gates", tags=["gates"])


@router.get("/{gate}", response_model=GateStatus)
async def get_gate(case_id: str, gate: GateId) -> GateStatus:
    """Gate checklist (plan §13.5).

    Args:
        case_id: see behaviour
        gate: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.post("/{gate}/approve", response_model=GateStatus)
async def approve_gate(case_id: str, gate: GateId, body: ApproveRequest) -> GateStatus:
    """Approve Gate 1 or Gate 2 once the checklist is cleared.

    Args:
        case_id: see behaviour
        gate: see behaviour
        body: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
