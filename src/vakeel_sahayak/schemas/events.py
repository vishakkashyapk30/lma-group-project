"""Event: the event-sourced case record's unit (plan §3.3)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.ids import CaseId, IsoDateTime

COUNSEL = "counsel"  # the only actor whose GATE_APPROVED / CHANGE_SET_APPROVED events count (plan §3.1, §16)


class Event(BaseModel):
    """One append-only event-log entry (plan §3.3): who, which tool, inputs, outputs, sources, time."""

    event_id: str  # required; '' means "not yet assigned": the log assigns an id on append
    case_id: CaseId
    ts: IsoDateTime | Literal[""]  # any ISO-8601 timestamp; '' means "not yet assigned": the log stamps it on append
    kind: EventKind
    actor: AgentName | str  # an agent or 'counsel'
    tool: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)  # pseudonymised only
    outputs: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceRef] = Field(default_factory=list)
    parent_id: str | None = None  # causal link used by truth maintenance
