"""Tools in case.timeline (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.runtime import get_runtime


def get_timeline(case_id: str, start: str | None = None, end: str | None = None) -> list[TimelineEvent] | ToolError:
    """Exact lookup of dated events. (plan §5.1)

    Args:
        case_id: see behaviour
        start: see behaviour
        end: see behaviour

    Returns:
        Events.
    """
    from vakeel_sahayak.rights.day_count import parse_date

    try:
        lo = parse_date(start) if start else None
        hi = parse_date(end) if end else None
    except ValueError as exc:
        return ToolError(tool="get_timeline", kind="invalid_input", message=str(exc), retryable=True)
    events = CaseState(case_id, get_runtime().event_log(case_id)).timeline()
    return [e for e in events if (lo is None or e.date >= lo.isoformat()) and (hi is None or e.date <= hi.isoformat())]


GET_TIMELINE_SPEC = ToolSpec(
    name="get_timeline",
    description="Exact lookup of dated events.",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.PAIROKAR],
    stores=[StoreName.CASE_TIMELINE],
    plan_ref="§5.1",
)
