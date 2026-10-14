"""In-memory event log with the same public surface as `record.event_log.EventLog` (used to isolate agent tests)."""

from __future__ import annotations

import itertools
from collections.abc import Iterator

from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import Event


class InMemoryEventLog:
    def __init__(self, db_path: str | None = None) -> None:
        self.events: list[Event] = []
        self._ids = itertools.count(1)
        self._subscribers: list[list[Event]] = []

    def append(self, event: Event) -> Event:
        if not event.event_id:
            event = event.model_copy(update={"event_id": f"ev{next(self._ids):04d}"})
        if not event.ts:
            event = event.model_copy(update={"ts": "2025-02-03T09:00:00Z"})
        self.events.append(event)
        for q in self._subscribers:
            q.append(event)
        return event

    def read(self, case_id: str, kind: EventKind | None = None, actor: str | None = None, since: str | None = None) -> list[Event]:
        out = [e for e in self.events if e.case_id == case_id]
        if kind is not None:
            out = [e for e in out if e.kind == kind]
        if actor is not None:
            out = [e for e in out if str(getattr(e.actor, "value", e.actor)) == actor]
        if since is not None:
            out = [e for e in out if e.ts >= since]
        return out

    def children(self, event_id: str) -> list[Event]:
        found: list[Event] = []
        frontier = {event_id}
        while frontier:
            nxt = {e.event_id for e in self.events if e.parent_id in frontier and e not in found}
            found += [e for e in self.events if e.event_id in nxt and e not in found]
            frontier = nxt
        return found

    def subscribe(self, case_id: str) -> Iterator[Event]:
        q: list[Event] = []
        self._subscribers.append(q)
        while q:
            yield q.pop(0)

    # convenience for assertions
    def kinds(self) -> list[EventKind]:
        return [e.kind for e in self.events]

    def tools_called(self) -> list[str]:
        return [e.tool for e in self.events if e.kind == EventKind.TOOL_CALL and e.tool]

    def as_text(self) -> str:
        """Everything the log stores, flattened: used to assert no raw names ever reach logs (plan §16)."""
        return "\n".join(e.model_dump_json() for e in self.events)
