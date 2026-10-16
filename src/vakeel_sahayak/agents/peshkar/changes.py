"""Change detection helpers (plan §7.4): the baseline a diff is taken against, and which fields a new document touches.

All of it is read off the event log, so nothing is stored twice. The baseline is the dossier, timeline, chunks and
Rights Radar report as they stood at counsel's last Gate 1 approval, or, before any approval, at Peshkar's last
snapshot (`dossier_snapshot` view). A diff compares per-field hashes of value and status (not of the source, so the same
value re-read from another page is not a change).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.peshkar.fields import ALL_FIELDS, COMPUTED_FIELDS, FIELD_SPECS
from vakeel_sahayak.ingestion.events import field_of_label
from vakeel_sahayak.record import views
from vakeel_sahayak.schemas.change_set import FieldChange
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.rights_report import RightsReport

SNAPSHOT_VIEW = "dossier_snapshot"
# Which dossier fields a dated event of each kind speaks to.
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "arrest_date": ("arrest_date",), "fir_date": ("fir",), "charge_sheet_date": ("charge_sheet", "trial_stage"),
    "offence_date": ("offence_date",), "first_remand": ("first_remand",), "remand": ("first_remand",),
    "bail_outcome": ("previous_bail",),
}  # fmt: skip


@dataclass
class Baseline:
    """The state a diff is taken against."""

    kind: str  # 'approved' (Gate 1) or 'snapshot'
    index: int  # position of the deciding event in the log
    dossier: CaseDossier
    event_ids: set[str] = field(default_factory=set)
    chunk_ids: set[str] = field(default_factory=set)
    rights: RightsReport | None = None

    @property
    def hashes(self) -> dict[str, str]:
        """Per-field hashes of the baseline dossier."""
        return field_hashes(self.dossier)

    @property
    def dossier_hash(self) -> str:
        """Hash of the whole baseline dossier."""
        return views.dossier_hash(self.dossier)


def field_hashes(dossier: CaseDossier) -> dict[str, str]:
    """Hash of each field's value and status (the source is left out on purpose)."""
    out = {}
    for name in ALL_FIELDS:
        tracked = getattr(dossier.fields, name)
        out[name] = views.hash_value({"value": tracked.value, "status": tracked.status.value})
    return out


def chunk_ids(events: list[Event]) -> set[str]:
    """Ids of the document chunks filed so far (Munshi's `case.docs` writes)."""
    ids: set[str] = set()
    for ev in events:
        if ev.kind == EventKind.STORE_WRITE and ev.inputs.get("store") == "case.docs":
            ids.update(str(c) for c in ev.outputs.get("chunk_ids") or [])
    return ids


def facts_written(events: list[Event], after_index: int = -1) -> set[str]:
    """Dossier fields written to `case.facts` by someone other than Peshkar after a point in the log."""
    names: set[str] = set()
    for ev in events[after_index + 1 :]:
        actor = str(getattr(ev.actor, "value", ev.actor))
        if ev.kind == EventKind.STORE_WRITE and ev.inputs.get("store") == "case.facts" and actor != "PESHKAR" and ev.inputs.get("field"):
            names.add(str(ev.inputs["field"]))
    return names


def _at(events: list[Event], case_id: str, index: int, kind: str) -> Baseline:
    upto = events[: index + 1]
    return Baseline(
        kind=kind,
        index=index,
        dossier=views.fold_dossier_for(case_id, upto),
        event_ids={r.event_id for r in views.fold_timeline(upto)},
        chunk_ids=chunk_ids(upto),
        rights=views.fold_rights_report(upto),
    )


def baseline(events: list[Event], case_id: str) -> Baseline | None:
    """The state to diff against: counsel's last Gate 1 approval, else Peshkar's last snapshot, else None."""
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.kind == EventKind.GATE_APPROVED and ev.inputs.get("gate") == GateId.GATE_1_DOSSIER.value and str(getattr(ev.actor, "value", ev.actor)) == COUNSEL:
            return _at(events, case_id, i, "approved")
    for i in range(len(events) - 1, -1, -1):
        ev = events[i]
        if ev.kind == EventKind.STORE_WRITE and ev.inputs.get("store") == "case.views" and ev.inputs.get("view") == SNAPSHOT_VIEW:
            return _at(events, case_id, i, "snapshot")
    return None


def diff_fields(old: dict[str, str] | None, new: dict[str, str], skip: tuple[str, ...] = ()) -> list[FieldChange]:
    """The fields whose hash differs (a field new on one side counts; its missing hash is None)."""
    old = old or {}
    return [
        FieldChange(field=n, old_hash=old.get(n), new_hash=new.get(n))
        for n in ALL_FIELDS
        if n not in skip and old.get(n) != new.get(n)
    ]


def touched_by_events(rows: list[Any]) -> set[str]:
    """Dossier fields that new timeline rows speak to (rows with a `label`)."""
    out: set[str] = set()
    for row in rows:
        kind = field_of_label(row.label)
        out.update(EVENT_FIELDS.get(kind or "", ()))
    return out


def touched_by_text(texts: list[str]) -> set[str]:
    """Dossier fields whose cue appears in the text of new chunks."""
    return {name for name, spec in FIELD_SPECS.items() if any(spec.cue.search(t) for t in texts)}


def touched_fields_by_search(case_id: str, new_chunks: set[str], search: Any) -> set[str]:
    """Fields whose cue appears in newly filed chunks, found through the case.docs search each field uses.

    Args:
        case_id: the case (for messages only)
        new_chunks: ids of the chunks filed since the baseline
        search: callable (query, k) -> list of CaseChunk, or a ToolError (that query is skipped)
    """
    texts: list[str] = []
    seen: set[str] = set()
    for spec in FIELD_SPECS.values():
        found = search(spec.queries[0], 25)
        if isinstance(found, list):
            for chunk in found:
                if chunk.chunk_id in new_chunks and chunk.chunk_id not in seen:
                    seen.add(chunk.chunk_id)
                    texts.append(" ".join((chunk.text_en or chunk.text).split()))
    return touched_by_text(texts)


def derived(fields: set[str]) -> set[str]:
    """Computed fields that follow from the touched ones (custody days follow the arrest date)."""
    return set(COMPUTED_FIELDS) if "arrest_date" in fields else set()
