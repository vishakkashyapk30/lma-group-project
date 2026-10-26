"""Router 'export' (plan §8.2, §13.1, §16): gated export of the application DOCX/PDF.

Export works only after Gate 2 of this very case, enforced in code (403 until then; no bulk export), and so does downloading a
file. The files are written below the case's data directory, the response lists them and `GET .../export/files/{name}` serves them. The DOCX assembler, hearing card and PDF converter live in
`vakeel_sahayak.export` (their content is tested in tests/unit/export/).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import _data_dir, get_event_log
from vakeel_sahayak.api.models import ExportRequest
from vakeel_sahayak.export import application, hearing_card, list_of_dates, objections, pdf
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.record.gates import GateNotApproved, assert_export_allowed
from vakeel_sahayak.schemas.enums import ExportFormat

router = APIRouter(prefix="/api/cases/{case_id}/export", tags=["export"])


@router.post("", response_model=list[str])
async def export_case(case_id: str, body: ExportRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> list[str]:
    """Gated export of DOCX/PDF; 403 unless Gate 2 is approved for this case (plan §16).

    Writes the application, the List of Dates, the objections sheet and the hearing-prep card as DOCX files (and a PDF of each
    for format PDF) under the case directory, and returns their paths; `GET .../export/files/{name}` serves them.
    """
    service.require_case(log, case_id)
    try:
        assert_export_allowed(log, case_id)
    except GateNotApproved as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return await run_in_threadpool(_write_files, log, case_id, body.format)


def _write_files(log: EventLog, case_id: str, fmt: ExportFormat) -> list[str]:
    from vakeel_sahayak.tools.runtime import get_runtime

    get_runtime().attach_log(case_id, log)  # the card reads the evidence packs Sutradhar wrote to this record
    cs = service.case_state(log, case_id)
    out_dir = _export_dir(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ingestion = cs.ingestion_report()
    docs = list(ingestion.documents) if ingestion is not None and hasattr(ingestion, "documents") else []
    brief, sparring, timeline = cs.brief(), cs.sparring(), cs.timeline()
    paths = [
        application.assemble_application_docx(brief, cs.dossier(), timeline, docs, str(out_dir / "application.docx")),
        list_of_dates.write_list_of_dates_docx(timeline, case_id, str(out_dir / "list_of_dates.docx")),
        objections.write_objections_docx(sparring, case_id, str(out_dir / "objections_sheet.docx")),
        hearing_card.write_hearing_card_docx(hearing_card.build_hearing_card(brief, sparring, case_id), case_id, str(out_dir / "hearing_card.docx")),
    ]
    if fmt == ExportFormat.PDF:
        paths += [pdf.docx_to_pdf(p) for p in paths]
    return paths


def _export_dir(case_id: str) -> Path:
    return (_data_dir() / "cases" / case_id / "export").resolve()


@router.get("/files/{name}")
async def download_file(case_id: str, name: str, log: Annotated[EventLog, Depends(get_event_log)]) -> FileResponse:
    """Download one exported file of this case; only after Gate 2, and only a file inside the case's export folder."""
    service.require_case(log, case_id)
    try:
        assert_export_allowed(log, case_id)
    except GateNotApproved as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    folder = _export_dir(case_id)
    target = (folder / Path(name).name).resolve()
    if target.parent != folder or not target.is_file():
        raise HTTPException(status_code=404, detail=f"no exported file {name!r} for case {case_id}")
    return FileResponse(target, filename=target.name)
