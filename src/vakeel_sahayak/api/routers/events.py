"""Router 'events' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/cases/{case_id}/events", tags=["events"])


@router.get("")
async def stream_events(case_id: str) -> StreamingResponse:
    """SSE agent events for the live trace and animations (plan §13.1).

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
