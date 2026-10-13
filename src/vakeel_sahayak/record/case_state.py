"""Views over the event log: dossier, timeline, brief, sparring (plan §3.3)."""

from __future__ import annotations

from vakeel_sahayak.record import views
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent


class CaseState:
    """Typed container for the case's views, computed from the event log (plan §3.3). Dossier, timeline, brief and sparring record are views, not stored truth."""

    def __init__(self, case_id: str, log: EventLog) -> None:
        """Bind to a case and its log.

        Args:
            case_id: the case whose events are folded
            log: the event log to read
        """
        self.case_id = check_case_id(case_id)
        self.log = log

    def events(self) -> list[Event]:
        """All events of the case, in order."""
        return self.log.read(self.case_id)

    def dossier(self) -> CaseDossier:
        """Current dossier view folded from events.

        Returns:
            CaseDossier.
        """
        return views.fold_dossier_for(self.case_id, self.events())

    def timeline(self) -> list[TimelineEvent]:
        """Current timeline view (plan §7.2).

        Returns:
            Sorted events.
        """
        return views.fold_timeline(self.events())

    def ingestion_report(self) -> IngestionReport | None:
        """Latest IngestionReport view.

        Returns:
            IngestionReport, or None before ingestion.
        """
        return views.fold_ingestion_report(self.events())

    def rights_report(self) -> RightsReport | None:
        """Latest RightsReport view.

        Returns:
            RightsReport, or None before the Rights Radar has run.
        """
        return views.fold_rights_report(self.events())

    def brief(self) -> BailBrief:
        """Current brief view, including claim states (plan §10).

        Returns:
            BailBrief.
        """
        return views.fold_brief(self.events(), self.case_id)

    def sparring(self) -> SparringRecord:
        """Current sparring record view.

        Returns:
            SparringRecord.
        """
        return views.fold_sparring(self.events(), self.case_id)

    def approved_dossier_hash(self) -> str | None:
        """Hash of the dossier at the last Gate-1 approval; basis for change detection (plan §7.4).

        Returns:
            Hash or None.
        """
        events = self.events()
        for i in range(len(events) - 1, -1, -1):
            ev = events[i]
            approved = ev.kind == EventKind.GATE_APPROVED and ev.inputs.get("gate") == GateId.GATE_1_DOSSIER.value
            if approved and str(getattr(ev.actor, "value", ev.actor)) == COUNSEL:
                recorded = ev.outputs.get("dossier_hash")
                return recorded or views.dossier_hash(views.fold_dossier_for(self.case_id, events[: i + 1]))
        return None
