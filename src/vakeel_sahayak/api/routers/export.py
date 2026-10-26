"""Router 'export' (plan §8.2, §13.1, §16): gated export of the application DOCX/PDF.

Export works only after Gate 2 of this very case, enforced in code (403 until then; no bulk export). The files are written
below the case's data directory and the response lists them. The DOCX assembler, hearing card and PDF converter live in
`vakeel_sahayak.export` (their content is tested in tests/unit/export/).
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import _data_dir, get_event_log
from vakeel_sahayak.api.models import ExportRequest
from vakeel_sahayak.export import application, hearing_card, pdf
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.record.gates import GateNotApproved, assert_export_allowed
from vakeel_sahayak.schemas.enums import ExportFormat

router = APIRouter(prefix="/api/cases/{case_id}/export", tags=["export"])


@router.post("", response_model=list[str])
async def export_case(case_id: str, body: ExportRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> list[str]:
    """Gated export of DOCX/PDF; 403 unless Gate 2 is approved for this case (plan §16)."""
    service.require_case(log, case_id)
    try:
        assert_export_allowed(log, case_id)
    except GateNotApproved as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    cs = service.case_state(log, case_id)
    out_dir = (_data_dir() / "cases" / case_id / "export").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ingestion = cs.ingestion_report()
    docs = list(ingestion.documents) if ingestion is not None and hasattr(ingestion, "documents") else []
    app_path = str(out_dir / "application.docx")
    application.assemble_application_docx(cs.brief(), cs.dossier(), cs.timeline(), docs, app_path)

    dates_path = out_dir / "list_of_dates.json"
    dates_path.write_text(json.dumps([e.model_dump(mode="json") for e in cs.timeline()], ensure_ascii=False), encoding="utf-8")
    objections_path = out_dir / "objections.json"
    objections_path.write_text(cs.sparring().model_dump_json(), encoding="utf-8")
    card = hearing_card.build_hearing_card(cs.brief(), cs.sparring(), case_id)
    card_path = out_dir / "hearing_card.json"
    card_path.write_text(json.dumps(card, ensure_ascii=False, default=str), encoding="utf-8")

    paths = [app_path, str(dates_path), str(objections_path), str(card_path)]
    if body.format == ExportFormat.PDF:
        paths.append(pdf.docx_to_pdf(app_path))
    return paths
