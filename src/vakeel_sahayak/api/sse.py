"""Server-Sent Events stream of agent events to the UI (plan §13.1, §3.3 use 4)."""

from __future__ import annotations

from collections.abc import AsyncIterator


async def event_stream(case_id: str, last_event_id: str | None = None) -> AsyncIterator[str]:
    """Yield SSE-formatted events from EventLog.subscribe.

    Args:
        case_id: see behaviour
        last_event_id: see behaviour

    Returns:
        SSE lines.
    """
    raise NotImplementedError
