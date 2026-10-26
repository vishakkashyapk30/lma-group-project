"""Router 'events' (plan §13.1, §3.3 use 4): agent events streamed to the UI as Server-Sent Events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from vakeel_sahayak.api.deps import get_event_log
from vakeel_sahayak.api.sse import event_stream
from vakeel_sahayak.record.event_log import EventLog

router = APIRouter(prefix="/api/cases/{case_id}/events", tags=["events"])


@router.get("")
async def stream_events(
    case_id: str,
    log: Annotated[EventLog, Depends(get_event_log)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """SSE agent events for the live trace and animations (plan §13.1)."""
    return StreamingResponse(
        event_stream(case_id, last_event_id, log=log),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
