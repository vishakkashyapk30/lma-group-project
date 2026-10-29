"""Pure fold functions from events to views (plan §3.3).

Event vocabulary. A view is rebuilt by replaying events in order. Tools write to the case stores (plan §5.1), and each
write is a STORE_WRITE event (counsel's edits come as USER_ACTION events with an `inputs["action"]`):

- `inputs {store: "case.facts", field: name}`, `outputs {tracked: TrackedField}` -> one dossier field, last write wins
- `inputs {store: "case.timeline"}`, `outputs {event: TimelineEvent}` -> timeline row, upserted by event_id
- `inputs {store: "case.views", view: name}`, `outputs {value: model}` -> whole-object view (ingestion_report,
  rights_report, brief, sparring), the latest one wins
- GATE_APPROVED by counsel on GATE_1_DOSSIER carries `outputs.dossier_hash` ('h:...'), the change-detection baseline
- USER_ACTION `edit_field` (inputs: field, value) -> USER_EDITED; `state_field` -> USER_STATED
- USER_ACTION `answer_question` (inputs: question) -> removes the open question
- USER_ACTION `edit_timeline_event` (inputs: event_id, plus the changed date/label) -> USER_EDITED row
- CLAIM_STALED (inputs.claim or outputs.claim_ids) -> marks those brief grounds STALE until a newer brief replaces them

Shorthand accepted as well: outputs keys `dossier` (whole or partial CaseDossier), `field_update`, `timeline_event(s)`,
`ingestion_report`, `rights_report`, `brief`, `sparring`.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields
from vakeel_sahayak.schemas.enums import ClaimState, EventKind, FieldStatus, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent

_FIELD_TYPES = DossierFields.model_fields


def _case_id(events: list[Event], case_id: str | None) -> str:
    """Pick the case id from the argument or the events; a view of nothing needs an explicit id."""
    if case_id:
        return case_id
    if events:
        return events[0].case_id
    raise ValueError("case_id is required to fold an empty event list")


def _set_field(fields: dict[str, Any], name: str, tracked: Any) -> None:
    """Store one tracked field, validating it against the dossier's declared type."""
    if name not in _FIELD_TYPES:
        raise ValueError(f"unknown dossier field {name!r}")
    fields[name] = tracked


def fold_dossier(events: list[Event]) -> CaseDossier:
    """Fold events into the dossier view (the case id is taken from the events).

    Args:
        events: events of one case, in order (not empty; use `fold_dossier_for` for a case with no events yet)

    Returns:
        CaseDossier.
    """
    return fold_dossier_for(_case_id(events, None), events)


def fold_dossier_for(case_id: str, events: list[Event]) -> CaseDossier:
    """Fold events into the dossier view of a named case (works for an empty event list too)."""
    cid = case_id
    fields: dict[str, Any] = {}
    court: str | None = None
    as_of: str | None = None
    questions: list[str] = []
    for ev in events:
        out = ev.outputs
        if _is_write(ev, "case.facts") and "field" in ev.inputs and "tracked" in out:
            _set_field(fields, ev.inputs["field"], out["tracked"])
        if isinstance(out.get("dossier"), dict):
            d = out["dossier"]
            court = d.get("court", court)
            as_of = d.get("as_of", as_of)
            for name, tracked in (d.get("fields") or {}).items():
                _set_field(fields, name, tracked)
            if "open_questions" in d:
                questions = list(d["open_questions"])
        if "field_update" in out:
            upd = out["field_update"]
            _set_field(fields, upd["field"], upd["tracked"])
        if ev.kind == EventKind.USER_ACTION:
            _apply_user_action(ev, fields, questions)
    dossier_fields = DossierFields.model_validate(fields)
    return CaseDossier(case_id=cid, court=court, as_of=as_of, fields=dossier_fields, open_questions=questions)


def _apply_user_action(ev: Event, fields: dict[str, Any], questions: list[str]) -> None:
    """Apply counsel's field edit, statement or answer to the dossier under construction."""
    action = ev.inputs.get("action")
    if action in ("edit_field", "state_field"):
        status = FieldStatus.USER_EDITED if action == "edit_field" else FieldStatus.USER_STATED
        source = SourceRef(chat=ev.inputs.get("chat")).model_dump() if status == FieldStatus.USER_STATED else None
        _set_field(fields, ev.inputs["field"], {"value": ev.inputs["value"], "source": source, "status": status.value})
    elif action == "answer_question":
        question = ev.inputs.get("question")
        if question in questions:
            questions.remove(question)


def _is_write(ev: Event, store: str, view: str | None = None) -> bool:
    """True for a STORE_WRITE to `store` (and, for case.views, to the named view)."""
    return (
        ev.kind == EventKind.STORE_WRITE
        and ev.inputs.get("store") == store
        and (view is None or ev.inputs.get("view") == view)
    )


def fold_timeline(events: list[Event]) -> list[TimelineEvent]:
    """Fold events into the timeline view.

    Args:
        events: events of one case, in order

    Returns:
        Sorted timeline (by date, then id).
    """
    rows: dict[str, TimelineEvent] = {}
    for ev in events:
        out = ev.outputs
        items = list(out.get("timeline_events") or [])
        if _is_write(ev, "case.timeline") and "event" in out:
            items.append(out["event"])
        if "timeline_event" in out:
            items.append(out["timeline_event"])
        for item in items:
            row = TimelineEvent.model_validate(item)
            rows[row.event_id] = row
        if ev.kind == EventKind.USER_ACTION and ev.inputs.get("action") == "edit_timeline_event":
            target = rows.get(ev.inputs["event_id"])
            if target is not None:
                changes = {k: ev.inputs[k] for k in ("date", "label") if k in ev.inputs}
                rows[target.event_id] = TimelineEvent.model_validate(
                    {**target.model_dump(), **changes, "status": FieldStatus.USER_EDITED}
                )
    return sorted(rows.values(), key=lambda r: (r.date, r.event_id))


def _latest(events: list[Event], key: str) -> Any | None:
    """Payload of the most recent write of the whole-object view `key` (a case.views write, or the shorthand)."""
    for ev in reversed(events):
        if _is_write(ev, "case.views", key) and "value" in ev.outputs:
            return ev.outputs["value"]
        if key in ev.outputs:
            return ev.outputs[key]
    return None


def fold_ingestion_report(events: list[Event]) -> IngestionReport | None:
    """Latest IngestionReport, or None before ingestion."""
    raw = _latest(events, "ingestion_report")
    return IngestionReport.model_validate(raw) if raw is not None else None


def fold_rights_report(events: list[Event]) -> RightsReport | None:
    """Latest RightsReport, or None before the Rights Radar has run."""
    raw = _latest(events, "rights_report")
    return RightsReport.model_validate(raw) if raw is not None else None


def fold_brief(events: list[Event], case_id: str | None = None) -> BailBrief:
    """Current brief; grounds named in a later CLAIM_STALED event are marked STALE (plan §10)."""
    cid = _case_id(events, case_id)
    brief = BailBrief(case_id=cid)
    for ev in events:
        if _is_write(ev, "case.views", "brief") and "value" in ev.outputs:
            brief = BailBrief.model_validate(ev.outputs["value"])
        elif "brief" in ev.outputs:
            brief = BailBrief.model_validate(ev.outputs["brief"])
        elif ev.kind == EventKind.CLAIM_STALED:
            stale = set(ev.outputs.get("claim_ids", []))
            if ev.inputs.get("claim"):
                stale.add(ev.inputs["claim"])
            for ground in brief.grounds:
                if ground.id in stale:
                    ground.state = ClaimState.STALE
    return brief


def fold_sparring(events: list[Event], case_id: str | None = None) -> SparringRecord:
    """Latest SparringRecord (empty before Abhiyojak has run)."""
    cid = _case_id(events, case_id)
    raw = _latest(events, "sparring")
    return SparringRecord.model_validate(raw) if raw is not None else SparringRecord(case_id=cid)


def hash_value(value: Any) -> str:
    """Stable short hash 'h:xxxxxxxx' of any JSON-able value (the style used in DependsOn.facts, plan §10)."""
    blob = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return "h:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8]


def dossier_hash(dossier: CaseDossier) -> str:
    """Hash of the whole dossier, the basis for change detection (plan §7.4)."""
    return hash_value(dossier.model_dump(mode="json"))


def export_content_hash(state: Any) -> str:
    """Full SHA-256 of everything export renders: brief, sparring record, timeline (List of Dates) and dossier.

    Stored with counsel's Gate 2 approval and compared before export, so an approval covers only the content counsel saw.
    """
    value = {
        "brief": state.brief().model_dump(mode="json"),
        "sparring": state.sparring().model_dump(mode="json"),
        "timeline": [t.model_dump(mode="json") for t in state.timeline()],
        "dossier": state.dossier().model_dump(mode="json"),
    }
    blob = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def gate_event(events: list[Event], gate: GateId) -> Event | None:
    """The event that currently decides a gate: the latest of GATE_OPENED / GATE_APPROVED / GATE_REJECTED.

    A GATE_APPROVED event only counts when counsel recorded it (plan §3.1, §16).
    """
    decisive: Event | None = None
    for ev in events:
        if ev.inputs.get("gate") != gate.value and ev.outputs.get("gate") != gate.value:
            continue
        if ev.kind == EventKind.GATE_APPROVED and str(getattr(ev.actor, "value", ev.actor)) != COUNSEL:
            continue
        if ev.kind in (EventKind.GATE_OPENED, EventKind.GATE_APPROVED, EventKind.GATE_REJECTED):
            decisive = ev
    return decisive


def gate_is_approved(events: list[Event], gate: GateId) -> bool:
    """True when counsel's approval is the latest word on the gate (a reopen or rejection revokes it)."""
    ev = gate_event(events, gate)
    return ev is not None and ev.kind == EventKind.GATE_APPROVED


def audit_trail(events: list[Event]) -> list[dict[str, Any]]:
    """Render the legal audit trail: who acted, which tool, sources, time (plan §3.3 use 1).

    Args:
        events: see behaviour

    Returns:
        Audit rows, one per event, in order.
    """
    return [
        {
            "event_id": ev.event_id,
            "time": ev.ts,
            "actor": str(getattr(ev.actor, "value", ev.actor)),
            "kind": ev.kind.value,
            "tool": ev.tool,
            "inputs": ev.inputs,
            "outputs": ev.outputs,
            "sources": [s.model_dump(exclude_none=True) for s in ev.sources],
            "parent_id": ev.parent_id,
        }
        for ev in events
    ]
