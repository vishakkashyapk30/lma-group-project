"""Router 'cases' (plan §13.1, §13.5): the cause list, one case, and the tabs of the workspace.

The tabs are folded views of the case record (record/case_state.py). Counsel's field edit is a USER_ACTION event (status
USER_EDITED). Drafting runs Sutradhar, Vakeel and Abhiyojak, and only after Gate 1 (plan §13.5). Conventions (404/409/422):
see tests/unit/api/_helpers.py.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import get_event_log
from vakeel_sahayak.api.models import FieldEditRequest, NewCaseRequest
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.case import BudgetState, CaseSummary
from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields
from vakeel_sahayak.schemas.enums import EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[CaseSummary])
async def list_cases(log: Annotated[EventLog, Depends(get_event_log)]) -> list[CaseSummary]:
    """Cause list, urgent cases first (plan §13.5)."""
    guard = GateGuard(log)
    summaries = [service.case_summary(log, guard, cid) for cid in service.all_case_ids(log)]
    rights = {cid: service.case_state(log, cid).rights_report() for cid in [s.case_id for s in summaries]}
    return sorted(summaries, key=lambda s: service.urgency_key(rights[s.case_id]))


@router.post("", response_model=CaseSummary)
async def create_case(body: NewCaseRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> CaseSummary:
    """Create a case at the intake stage (plan §13.5)."""
    existing = set(service.all_case_ids(log))
    n = 1
    while f"case-{n:04d}" in existing:
        n += 1
    case_id = f"case-{n:04d}"
    log.append(Event(event_id="", case_id=case_id, ts="", kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "create_case", "title": body.title or case_id}))
    return service.case_summary(log, GateGuard(log), case_id)


@router.get("/{case_id}", response_model=CaseSummary)
async def get_case(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> CaseSummary:
    """One case (plan §13.5)."""
    service.require_case(log, case_id)
    return service.case_summary(log, GateGuard(log), case_id)


@router.get("/{case_id}/ingestion", response_model=IngestionReport)
async def get_ingestion(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> IngestionReport:
    """Latest IngestionReport."""
    service.require_case(log, case_id)
    report = service.case_state(log, case_id).ingestion_report()
    if report is None:
        raise HTTPException(status_code=404, detail="no ingestion report yet")
    return report


@router.get("/{case_id}/dossier", response_model=CaseDossier)
async def get_dossier(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> CaseDossier:
    """Dossier tab."""
    service.require_case(log, case_id)
    return service.case_state(log, case_id).dossier()


@router.patch("/{case_id}/dossier/{field}", response_model=CaseDossier)
async def edit_field(case_id: str, field: str, body: FieldEditRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> CaseDossier:
    """Counsel edits a field; status becomes USER_EDITED and the edit is logged as counsel (audit trail)."""
    service.require_case(log, case_id)
    if field not in DossierFields.model_fields:
        raise HTTPException(status_code=404, detail=f"unknown dossier field {field}")
    log.append(Event(event_id="", case_id=case_id, ts="", kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "edit_field", "field": field, "value": body.value}))
    return service.case_state(log, case_id).dossier()


@router.get("/{case_id}/dates", response_model=list[TimelineEvent])
async def get_dates(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> list[TimelineEvent]:
    """Dates tab (List of Dates), oldest first."""
    service.require_case(log, case_id)
    return service.case_state(log, case_id).timeline()


@router.get("/{case_id}/rights", response_model=RightsReport)
async def get_rights(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> RightsReport:
    """Rights tab."""
    service.require_case(log, case_id)
    report = service.case_state(log, case_id).rights_report()
    if report is None:
        raise HTTPException(status_code=404, detail="no rights report yet")
    return report


@router.post("/{case_id}/draft", response_model=dict[str, Any])
async def start_draft(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> dict[str, Any]:
    """Draft the bail brief: Sutradhar plans, Vakeel drafts, Abhiyojak spars (plan §13.6 flow 3). Only after Gate 1."""
    service.require_case(log, case_id)
    guard = GateGuard(log)
    if not guard.is_approved(case_id, GateId.GATE_1_DOSSIER):
        raise HTTPException(status_code=409, detail="Gate 1 (dossier) is not approved yet")

    from vakeel_sahayak.agents.base import AgentContext
    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.orchestration.state import CaseGraphState
    from vakeel_sahayak.schemas.enums import AgentName

    cs = service.case_state(log, case_id)
    state = CaseGraphState(case_id=case_id, log_path=log.db_path, dossier=cs.dossier(), rights=cs.rights_report())
    ctx = AgentContext(case_id=case_id, log=log)
    sutradhar = create_agent(AgentName.SUTRADHAR, ctx)
    try:
        state = sutradhar.run(state)
        state = sutradhar.delegate(state, list(state.evidence_packs))
    finally:
        sutradhar.close()
    grounds = len(state.brief.grounds) if state.brief else 0
    return {"status": "drafted", "grounds": grounds}


@router.get("/{case_id}/brief", response_model=BailBrief)
async def get_brief(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> BailBrief:
    """Brief tab (404 before drafting)."""
    service.require_case(log, case_id)
    brief = service.case_state(log, case_id).brief()
    if not brief.grounds and not brief.open_issues:
        raise HTTPException(status_code=404, detail="no brief yet")
    return brief


@router.get("/{case_id}/spar", response_model=SparringRecord)
async def get_spar(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> SparringRecord:
    """Spar tab (404 before sparring)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    if views._latest(service.case_state(log, case_id).events(), "sparring") is None:
        raise HTTPException(status_code=404, detail="no sparring record yet")
    return service.case_state(log, case_id).sparring()


@router.get("/{case_id}/prep", response_model=dict[str, Any])
async def get_prep(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> dict[str, Any]:
    """Hearing-prep card (404 before drafting); no prediction, no grant rate (plan §8.3)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    card = views._latest(service.case_state(log, case_id).events(), "hearing_card")
    if card is None:
        raise HTTPException(status_code=404, detail="no hearing-prep card yet")
    return card


@router.get("/{case_id}/budget", response_model=BudgetState)
async def get_budget(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> BudgetState:
    """Spend and the per-case cap (plan §6.2)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    saved = views._latest(service.case_state(log, case_id).events(), "budget")
    return BudgetState.model_validate(saved) if saved is not None else BudgetState()


@router.get("/{case_id}/files/{doc_id}/pages/{page}")
async def get_page_image(case_id: str, doc_id: str, page: int, log: Annotated[EventLog, Depends(get_event_log)]) -> FileResponse:
    """Page image for the PDF viewer, served from the case's laptop directory only (plan §13.5)."""
    service.require_case(log, case_id)
    if "/" in doc_id or "\\" in doc_id or ".." in doc_id:
        raise HTTPException(status_code=404, detail="unknown page")
    from vakeel_sahayak.api.deps import _data_dir

    base = (_data_dir() / "cases" / case_id / "files").resolve()
    target = (base / doc_id / "pages" / f"{page}.png").resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="unknown page")
    return FileResponse(str(target), media_type="image/png")
