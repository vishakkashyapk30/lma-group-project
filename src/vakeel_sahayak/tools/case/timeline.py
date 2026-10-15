"""Tools in case.timeline (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

import re
from datetime import date

from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, invalid

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _window_bound(tool: str, label: str, value: str | None) -> date | None | ToolError:
    """Parse one end of the window; only YYYY-MM-DD is accepted, so a malformed date is an error, never a guess."""
    if value is None:
        return None
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        return invalid(tool, f"{label} must be an ISO date YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(value)
    except ValueError:
        return invalid(tool, f"{label} is not a real date: {value!r}")


def get_timeline(case_id: str, start: str | None = None, end: str | None = None) -> list[TimelineEvent] | ToolError:
    """Exact lookup of dated events. (plan §5.1)

    Args:
        case_id: see behaviour
        start: see behaviour
        end: see behaviour

    Returns:
        Events.
    """
    tool = "get_timeline"
    try:
        check_case_id(case_id)
    except (ValueError, TypeError) as exc:
        return invalid(tool, str(exc))
    lo = _window_bound(tool, "start", start)
    if isinstance(lo, ToolError):
        return lo
    hi = _window_bound(tool, "end", end)
    if isinstance(hi, ToolError):
        return hi
    if lo and hi and lo > hi:
        return invalid(tool, f"start {start} is after end {end}")
    return call_store(
        tool,
        StoreName.CASE_TIMELINE,
        lambda s: sorted(s.get(start, end), key=lambda e: e.date),
        case_id=case_id,
    )


GET_TIMELINE_SPEC = ToolSpec(
    name="get_timeline",
    description="Exact lookup of dated events.",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.PAIROKAR],
    stores=[StoreName.CASE_TIMELINE],
    plan_ref="§5.1",
)
