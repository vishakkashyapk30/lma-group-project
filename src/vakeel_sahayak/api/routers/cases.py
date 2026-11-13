"""Router 'cases' (plan §13.1, §13.5): the cause list, one case, and the tabs of the workspace.

The tabs are folded views of the case record (record/case_state.py). Counsel's field edit is a USER_ACTION event (status
USER_EDITED). Drafting runs Sutradhar, Vakeel and Abhiyojak, and only after Gate 1 (plan §13.5). Conventions (404/409/422):
see tests/unit/api/_helpers.py.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import get_event_log
from vakeel_sahayak.api.models import (
    BailBriefOut,
    FieldEditRequest,
    HearingPrepCardOut,
    NewCaseRequest,
    RightsReportOut,
)
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import BudgetState, CaseSummary
from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields
from vakeel_sahayak.schemas.enums import EventKind, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _indexed_source_pdf(case_dir: Path, doc_id: str, page: int) -> Path | None:
    """Find the original PDF for one filed page, without trusting index paths.

    Munshi's page index retains the uploaded filename and its physical page
    number. Page PNGs are optional local caches, so the viewer can fall back
    to this source when a case was ingested from the original PDF alone.
    """
    from vakeel_sahayak.ingestion.pageindex import PageIndex

    try:
        indexed = PageIndex.load(case_dir / "page_index.json")
    except (OSError, ValueError):
        return None
    record = next((item for item in indexed.pages if item.doc_id == doc_id and item.page == page), None)
    if record is None or Path(record.file).suffix.lower() != ".pdf":
        return None
    source = (case_dir / record.file).resolve()
    return source if case_dir in source.parents and source.is_file() else None


def _render_pdf_page(pdf_path: Path, page: int) -> bytes | None:
    """Rasterise one physical PDF page for the private, on-device viewer."""
    if page < 1:
        return None
    try:
        import fitz  # PyMuPDF

        with fitz.open(pdf_path) as pdf:
            if page > pdf.page_count:
                return None
            return pdf.load_page(page - 1).get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
    except (ImportError, OSError, RuntimeError, ValueError):
        return None


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


@router.delete("/{case_id}", status_code=204)
async def delete_case(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> None:
    """Permanently remove one case's record, files, caches and retained audio from this laptop."""
    service.require_case(log, case_id)
    from vakeel_sahayak.api.deps import _data_dir

    case_dir = (_data_dir() / "cases" / case_id).resolve()
    cases_dir = (_data_dir() / "cases").resolve()
    if cases_dir not in case_dir.parents:
        raise HTTPException(status_code=404, detail="unknown case")
    shutil.rmtree(case_dir, ignore_errors=True)
    log.purge_case(case_id)


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


@router.get("/{case_id}/rights", response_model=RightsReportOut)
async def get_rights(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> RightsReportOut:
    """Rights tab. Each check carries `verification` ('unverified' until a person re-checks its rule text; else the date) and the report lists `unverified_checks`."""
    service.require_case(log, case_id)
    report = service.case_state(log, case_id).rights_report()
    if report is None:
        raise HTTPException(status_code=404, detail="no rights report yet")
    return RightsReportOut.from_report(report)


@router.post("/{case_id}/draft", response_model=dict[str, Any])
async def start_draft(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> dict[str, Any]:
    """Draft the bail brief: Sutradhar plans, Vakeel drafts, Abhiyojak spars (plan §13.6 flow 3). Only after Gate 1."""
    service.require_case(log, case_id)
    guard = GateGuard(log)
    if not guard.is_approved(case_id, GateId.GATE_1_DOSSIER):
        raise HTTPException(status_code=409, detail="Gate 1 (dossier) is not approved yet")

    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.schemas.enums import AgentName

    def draft():  # noqa: ANN202 - threadpool callback returns the typed product graph state
        cs = service.case_state(log, case_id)
        state = service.product_state(log, case_id, dossier=cs.dossier(), rights=cs.rights_report())
        sutradhar = create_agent(AgentName.SUTRADHAR, service.product_agent_context(log, case_id))
        try:
            state = sutradhar.run(state)
            return sutradhar.delegate(state, list(state.evidence_packs))
        finally:
            sutradhar.close()

    # A worker thread, so the API (and the event stream that shows the drafting live) keeps answering meanwhile.
    state = await run_in_threadpool(draft)
    # The product graph asks Vakeel to open Gate 2, but its tool runtime can be
    # detached from this request's injected log.  The API owns the browser
    # workflow, so make the persisted brief and its approval gate atomic from
    # counsel's point of view: a successful draft must always be approvable.
    if state.brief and not guard.is_approved(case_id, GateId.GATE_2_EXPORT) and not guard.is_open(case_id, GateId.GATE_2_EXPORT):
        guard.open(case_id, GateId.GATE_2_EXPORT)
    grounds = len(state.brief.grounds) if state.brief else 0
    return {"status": "drafted", "grounds": grounds}


@router.get("/{case_id}/brief", response_model=BailBriefOut)
async def get_brief(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> BailBriefOut:
    """Brief tab (404 before drafting). `withheld`: per ground, the sentences strict abstention (X4, c1457) left out of the argument and why."""
    service.require_case(log, case_id)
    cs = service.case_state(log, case_id)
    brief = cs.brief()
    if not brief.grounds and not brief.open_issues:
        raise HTTPException(status_code=404, detail="no brief yet")
    return BailBriefOut(**brief.model_dump(), withheld=service.withheld_by_ground(cs.events()))


@router.get("/{case_id}/spar", response_model=SparringRecord)
async def get_spar(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> SparringRecord:
    """Spar tab (404 before sparring)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    if views._latest(service.case_state(log, case_id).events(), "sparring") is None:
        raise HTTPException(status_code=404, detail="no sparring record yet")
    return service.case_state(log, case_id).sparring()


@router.get("/{case_id}/prep", response_model=HearingPrepCardOut)
async def get_prep(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> HearingPrepCardOut:
    """Hearing-prep card (404 before drafting); no prediction, no grant rate (plan §8.3)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    card = views._latest(service.case_state(log, case_id).events(), "hearing_card")
    if card is None:
        raise HTTPException(status_code=404, detail="no hearing-prep card yet")
    return HearingPrepCardOut.model_validate(card)


@router.get("/{case_id}/budget", response_model=BudgetState)
async def get_budget(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> BudgetState:
    """Spend and the per-case cap (plan §6.2)."""
    service.require_case(log, case_id)
    from vakeel_sahayak.record import views

    saved = views._latest(service.case_state(log, case_id).events(), "budget")
    return BudgetState.model_validate(saved) if saved is not None else BudgetState()


@router.get("/{case_id}/files/{doc_id}/pages/{page}")
def get_page_image(case_id: str, doc_id: str, page: int, log: Annotated[EventLog, Depends(get_event_log)]) -> Response:
    """Page image for the PDF viewer, served and rendered on this laptop only (plan §13.5)."""
    service.require_case(log, case_id)
    if "/" in doc_id or "\\" in doc_id or ".." in doc_id:
        raise HTTPException(status_code=404, detail="unknown page")
    from vakeel_sahayak.api.deps import _data_dir

    case_dir = (_data_dir() / "cases" / case_id).resolve()
    image_root = (case_dir / "files").resolve()
    target = (image_root / doc_id / "pages" / f"{page}.png").resolve()
    headers = {"Cache-Control": "private, no-store"}
    if image_root in target.parents and target.is_file():
        return FileResponse(str(target), media_type="image/png", headers=headers)

    # Ingestion does not have to materialise every page as a PNG. Render the
    # matching uploaded PDF only when the browser requests it, so an otherwise
    # complete local case never shows a broken source preview.
    source = _indexed_source_pdf(case_dir, doc_id, page)
    png = _render_pdf_page(source, page) if source is not None else None
    if png is None:
        raise HTTPException(status_code=404, detail="unknown page")
    return Response(content=png, media_type="image/png", headers=headers)
