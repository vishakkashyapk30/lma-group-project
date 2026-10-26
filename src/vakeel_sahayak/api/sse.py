"""Server-Sent Events stream of agent events to the UI (plan §13.1, §3.3 use 4).

One frame per event: `id:` the event id, `event:` the EventKind value, `data:` the event JSON. A reconnecting browser sends
`Last-Event-ID`; the stream replays the stored events of the case after it, then follows `EventLog.subscribe`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from vakeel_sahayak.schemas.events import Event


def _frame(event: Event) -> str:
    """One SSE frame for an event."""
    return f"id: {event.event_id}\nevent: {event.kind.value}\ndata: {event.model_dump_json()}\n\n"


async def event_stream(case_id: str, last_event_id: str | None = None) -> AsyncIterator[str]:
    """Yield SSE-formatted events for a case: the stored events after `last_event_id`, then the live ones.

    Args:
        case_id: the case whose events to stream
        last_event_id: resume after this event id (a reconnecting browser's `Last-Event-ID`)

    Returns:
        SSE frames.
    """
    from vakeel_sahayak.api import deps

    log = deps.get_event_log(case_id)
    seen_target = last_event_id is None  # skip every frame up to and including last_event_id, in stored then live

    def past_resume_point(event: Event) -> bool:
        nonlocal seen_target
        if seen_target:
            return True
        if event.event_id == last_event_id:
            seen_target = True
        return False

    for event in log.read(case_id):
        if past_resume_point(event):
            yield _frame(event)
    for event in log.subscribe(case_id):
        if past_resume_point(event):
            yield _frame(event)
