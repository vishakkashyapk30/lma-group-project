"""Router 'events' (plan §13.1, §3.3 use 4): agent events streamed to the UI as Server-Sent Events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from vakeel_sahayak.api.sse import event_stream

router = APIRouter(prefix="/api/cases/{case_id}/events", tags=["events"])


@router.get("")
async def stream_events(case_id: str, last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None) -> StreamingResponse:
    """SSE agent events for the live trace and animations (plan §13.1)."""
    return StreamingResponse(
        event_stream(case_id, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
