"""Shared helpers for the API routers (plan §13.5): case lookup, the cause-list summary and its Rights Radar chips.

The record is the source of truth (record/case_state.py folds the views); a case exists as soon as its log has an event.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import CaseSummary
from vakeel_sahayak.schemas.enums import EventKind, GateId, RightsStatus, Stage
from vakeel_sahayak.schemas.rights_report import RightsReport

_GATES = (GateId.GATE_1_DOSSIER, GateId.GATE_2_EXPORT)
_DAYS_RE = re.compile(r"opens in (\d+)\s*day", re.IGNORECASE)


def case_state(log: EventLog, case_id: str) -> CaseState:
    """The folded views of a case."""
    return CaseState(case_id, log)


def agent_context(log: EventLog, case_id: str) -> object:
    """An `AgentContext` for the case with the tool allow-list filled from the registry (the demo and tests share these)."""
    from vakeel_sahayak.agents.base import AgentContext
    from vakeel_sahayak.tools.registry import discover_tools, get_tool

    tools: dict[str, object] = {}
    for name in discover_tools():
        try:
            tools[name] = get_tool(name)
        except Exception:  # noqa: BLE001 - a tool the environment does not provide is simply left out
            pass
    return AgentContext(case_id=case_id, log=log, tools=tools)


def case_exists(log: EventLog, case_id: str) -> bool:
    """True once the case has any event (plan §13.5: a case is its record)."""
    return bool(log.read(case_id))


def require_case(log: EventLog, case_id: str) -> None:
    """404 when the case has no record yet."""
    if not case_exists(log, case_id):
        raise HTTPException(status_code=404, detail=f"unknown case {case_id}")


def all_case_ids(log: EventLog) -> list[str]:
    """Every case id in the log (works on the real log and the in-memory fake)."""
    if hasattr(log, "case_ids"):
        return list(log.case_ids())
    return sorted({e.case_id for e in getattr(log, "events", [])})


def case_title(log: EventLog, case_id: str) -> str:
    """The title counsel gave on creation, else the case id."""
    for ev in log.read(case_id, kind=EventKind.USER_ACTION):
        if ev.inputs.get("action") == "create_case" and ev.inputs.get("title"):
            return str(ev.inputs["title"])
    return case_id


def _chip_score(check: object, detail: str) -> int:
    """Smaller is more urgent: days until a window opens, then CHECK, then a window close, then everything else."""
    days = _DAYS_RE.search(detail)
    if days:
        return int(days.group(1))
    status = getattr(check, "status", None)
    if status == RightsStatus.CHECK:
        return 500
    if status == RightsStatus.WINDOW_CLOSED:
        return 800
    return 1000


def rights_chips(report: RightsReport | None) -> list[str]:
    """Rights Radar chips for the cause list, most urgent first (plan §13.5). None/empty before the Radar has run."""
    if report is None:
        return []
    scored: list[tuple[int, str]] = []
    for check in report.checks:
        if getattr(check, "status", None) == RightsStatus.NOT_APPLICABLE:
            continue
        detail = check.detail or check.check.value.replace("_", " ")
        scored.append((_chip_score(check, detail), detail))
    scored.sort(key=lambda s: s[0])
    return [text for _, text in scored]


def urgency_key(report: RightsReport | None) -> int:
    """The cause list orders urgent cases first: the smallest chip score, or a large number when nothing is pressing."""
    if report is None:
        return 10_000
    scores = [_chip_score(c, c.detail or "") for c in report.checks if getattr(c, "status", None) != RightsStatus.NOT_APPLICABLE]
    return min(scores, default=10_000)


def needs_attention(guard: GateGuard, case_id: str) -> int:
    """How many checklist items the open gate still has (0 when no gate is open)."""
    for gate in _GATES:
        if guard.is_open(case_id, gate):
            st = guard.status(case_id, gate)
            return len(st.unresolved_unsupported) + len(st.unresolved_needs_review) + len(st.unresolved_unanswered)
    return 0


def stage_of(cs: CaseState, guard: GateGuard, case_id: str) -> Stage:
    """The workspace stage derived from the record (plan §13.5)."""
    from vakeel_sahayak.record import views

    if cs.brief().grounds:
        return Stage.FILE if guard.is_approved(case_id, GateId.GATE_2_EXPORT) else Stage.SPAR
    if guard.is_approved(case_id, GateId.GATE_1_DOSSIER):
        return Stage.BRIEF
    events = cs.events()
    if cs.rights_report() is not None or any(views._is_write(e, "case.facts") for e in events):
        return Stage.DOSSIER
    return Stage.INTAKE


def case_summary(log: EventLog, guard: GateGuard, case_id: str) -> CaseSummary:
    """The cause-list card of a case (plan §13.5)."""
    cs = case_state(log, case_id)
    rights = cs.rights_report()
    return CaseSummary(
        case_id=case_id,
        title=case_title(log, case_id),
        stage=stage_of(cs, guard, case_id),
        rights_chips=rights_chips(rights),
        needs_attention=needs_attention(guard, case_id),
    )
