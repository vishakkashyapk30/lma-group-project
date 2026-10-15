"""Typed graph state (plan §3.3).

`CaseGraphState` is what the LangGraph graph (or the plain fallback state machine) carries between nodes and what its
SQLite checkpointer saves. It is JSON-serialisable on purpose, so the event log is referenced by path
(`log_path`, None meaning the configured per-case log) and opened with `event_log()`. The event log stays the source
of truth: `refresh_from_log()` re-folds the dossier, rights report, brief and sparring record from it (plan §3.3:
those are views), and agents write through the log, never only into the state.

`open_graph_checkpointer(case_id)` opens LangGraph's SqliteSaver at configs/stores.yaml `checkpointer.path`
(cases/{case_id}/graph.sqlite).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.case import BudgetState
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.chat import ChatMessage
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import Factor, GateId, Stage
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, RetrievalPlan
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.schemas.triage import TriageCard

GATE_OPEN, GATE_APPROVED, GATE_REJECTED = "open", "approved", "rejected"
_OPEN_LOGS: dict[str, Any] = {}  # event logs opened from a state's log_path, one per file


class CaseGraphState(BaseModel):
    """State carried through the case graph."""

    case_id: str
    stage: Stage = Stage.INTAKE
    log_path: str | None = None  # the event-log handle: SQLite file of the case's log; None = the configured per-case log
    switches: Switches = Field(default_factory=Switches)
    before: str | None = None  # retrieval sees only documents dated before this (the case's order date; leakage rule, plan §2)
    as_of: str | None = None  # the date the Rights Radar counts to (default: today)
    files: list[str] = Field(default_factory=list)  # files waiting for Munshi
    facts_text: str | None = None  # pseudonymised raw facts (A1 and the baselines read these instead of the dossier)
    ingestion: IngestionReport | None = None
    dossier: CaseDossier | None = None
    list_of_dates: list[TimelineEvent] = Field(default_factory=list)
    rights: RightsReport | None = None
    evidence_packs: list[EvidencePack] = Field(default_factory=list)  # Sutradhar -> Vakeel, one per chosen factor
    plans: list[RetrievalPlan] = Field(default_factory=list)  # every RetrievalPlan round, for the trace
    brief: BailBrief | None = None
    sparring: SparringRecord | None = None
    hearing_card: dict[str, Any] | None = None
    pending_change_set: ChangeSet | None = None
    change_sets: list[ChangeSet] = Field(default_factory=list)  # approved change sets, oldest first
    reopened_factors: list[Factor] = Field(default_factory=list)  # factors re-run after the latest change set (plan §10)
    budget: BudgetState = Field(default_factory=BudgetState)
    budget_tracker: dict[str, Any] | None = None  # BudgetTracker.to_dict(), for resuming spend
    gates: dict[str, str] = Field(default_factory=dict)  # GateId value -> 'open' | 'approved' | 'rejected'
    pending_gate: GateId | None = None
    triage: TriageCard | None = None
    chat: list[ChatMessage] = Field(default_factory=list)
    exported: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    done: bool = False

    def event_log(self):  # noqa: ANN201
        """The case's EventLog: the file at `log_path`, else the tool runtime's per-case log (shared with the tools)."""
        from vakeel_sahayak.tools.runtime import get_runtime

        runtime = get_runtime()
        if self.log_path:
            from vakeel_sahayak.record.event_log import EventLog

            key = self.log_path if self.log_path == ":memory:" else str(Path(self.log_path).resolve())
            log = _OPEN_LOGS.get(key)
            if log is None:
                log = _OPEN_LOGS[key] = EventLog(self.log_path)
            runtime.attach_log(self.case_id, log)
            return log
        return runtime.event_log(self.case_id)

    def case_state(self):  # noqa: ANN201
        """record.case_state.CaseState over this case's log (the views)."""
        from vakeel_sahayak.record.case_state import CaseState

        return CaseState(self.case_id, self.event_log())

    def refresh_from_log(self) -> CaseGraphState:
        """A copy with the dossier, timeline, rights report, brief, sparring record and ingestion report re-folded from the log."""
        cs = self.case_state()
        events = cs.events()
        from vakeel_sahayak.record import views

        brief = views.fold_brief(events, self.case_id) if events else None
        sparring = views.fold_sparring(events, self.case_id) if events else None
        return self.model_copy(
            update={
                "dossier": views.fold_dossier_for(self.case_id, events),
                "list_of_dates": views.fold_timeline(events),
                "rights": views.fold_rights_report(events),
                "ingestion": views.fold_ingestion_report(events) or self.ingestion,
                "brief": brief if brief is not None and (brief.grounds or brief.open_issues) else self.brief,
                "sparring": sparring if sparring is not None and sparring.objections else self.sparring,
            }
        )

    def gate_state(self, gate: GateId) -> str | None:
        """'open', 'approved', 'rejected' or None for a gate."""
        return self.gates.get(GateId(gate).value)


def checkpoint_path(case_id: str, config: Any = None) -> str:
    """Where LangGraph's checkpoints of a case live (configs/stores.yaml `checkpointer.path`, under the cases folder)."""
    from vakeel_sahayak.schemas.ids import check_case_id

    if config is None:
        from vakeel_sahayak.config import load_config

        config = load_config()
    template = (config.stores.get("checkpointer") or {}).get("path", "cases/{case_id}/graph.sqlite")
    rel = str(template).format(case_id=check_case_id(case_id)).removeprefix("cases/")
    path = Path(config.paths.cases_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def open_graph_checkpointer(case_id: str | None = None, path: str | None = None, config: Any = None):  # noqa: ANN201
    """LangGraph's SqliteSaver for a case (plan §3.3), or None when langgraph-checkpoint-sqlite is not installed.

    Args:
        case_id: the case (its file is `checkpoint_path(case_id)`)
        path: an explicit SQLite file (':memory:' for tests); overrides case_id
        config: AppConfig (default: load_config())

    Returns:
        A `langgraph.checkpoint.sqlite.SqliteSaver`, or None.
    """
    try:
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        return None
    target = path or (checkpoint_path(case_id, config) if case_id else ":memory:")
    return SqliteSaver(sqlite3.connect(target, check_same_thread=False))
