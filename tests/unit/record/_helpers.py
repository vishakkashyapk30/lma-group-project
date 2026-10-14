"""Helpers to build case-record events for record/ and orchestration/ tests.

ASSUMPTION (payload shapes, documented in tests/fixtures/case_0007/events.jsonl):
* a dossier field is a STORE_WRITE with `inputs = {"store": "case.facts", "field": <name>}` and
  `outputs = {"tracked": <TrackedField as JSON>}`; a timeline entry is a STORE_WRITE with `inputs.store == "case.timeline"`
  and `outputs = {"event": <TimelineEvent as JSON>}`; later writes to the same field win.
* a whole-object view (ingestion_report, rights_report, brief, sparring) is a STORE_WRITE with
  `inputs = {"store": "case.views", "view": <name>}` and `outputs = {"value": <model as JSON>}`; the latest wins.
* gates are GATE_OPENED / GATE_APPROVED events with `inputs.gate` = GateId value; GATE_APPROVED of GATE_1_DOSSIER carries
  `outputs.dossier_hash` ('h:...') and `inputs.acknowledged`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.events import Event


def make_event(
    case_id: str = "case-0007",
    kind: EventKind = EventKind.AGENT_MESSAGE,
    actor: str = AgentName.PESHKAR.value,
    *,
    event_id: str = "",
    ts: str = "",
    tool: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    parent_id: str | None = None,
) -> Event:
    """An Event with id and time left empty unless given (the log assigns them on append)."""
    return Event(
        event_id=event_id,
        case_id=case_id,
        ts=ts,
        kind=kind,
        actor=actor,
        tool=tool,
        inputs=inputs or {},
        outputs=outputs or {},
        parent_id=parent_id,
    )


def field_write(case_id: str, field: str, tracked: BaseModel | dict, actor: str = "PESHKAR") -> Event:
    """STORE_WRITE of one dossier field."""
    dump = tracked if isinstance(tracked, dict) else tracked.model_dump(mode="json")
    return make_event(
        case_id,
        EventKind.STORE_WRITE,
        actor,
        tool="extract_dossier",
        inputs={"store": "case.facts", "field": field},
        outputs={"tracked": dump},
    )


def dossier_events(case_id: str, dossier) -> list[Event]:
    """One field-write event per field of a CaseDossier (so folding them reproduces the dossier)."""
    return [field_write(case_id, name, getattr(dossier.fields, name)) for name in type(dossier.fields).model_fields]


def view_write(case_id: str, view: str, model: BaseModel, actor: str = "VAKEEL") -> Event:
    """STORE_WRITE of a whole-object view (ingestion_report, rights_report, brief, sparring)."""
    return make_event(
        case_id,
        EventKind.STORE_WRITE,
        actor,
        inputs={"store": "case.views", "view": view},
        outputs={"value": model.model_dump(mode="json")},
    )


def gate_opened(case_id: str, gate: str) -> Event:
    return make_event(case_id, EventKind.GATE_OPENED, "PESHKAR", inputs={"gate": gate})


def gate_approved(case_id: str, gate: str, acknowledged: list[str] | None = None, dossier_hash: str | None = None) -> Event:
    outputs = {"dossier_hash": dossier_hash} if dossier_hash else {}
    return make_event(
        case_id, EventKind.GATE_APPROVED, "counsel", inputs={"gate": gate, "acknowledged": acknowledged or []}, outputs=outputs
    )
