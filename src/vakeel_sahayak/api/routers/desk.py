"""Router 'desk' (plan §11, §13.5 `/desk`): Pairokar's batch desk.

Upload a zip or a single PDF (one case per PDF, the file stem is the case id), see the triage board sorted by urgency, open
a case. Safety: no bulk export, and opening a case approves nothing — each case still needs its own Gate 2 (plan §16).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import _data_dir, get_event_log
from vakeel_sahayak.api.models import DeskBoard
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.case import CaseSummary
from vakeel_sahayak.schemas.triage import TriageCard

router = APIRouter(prefix="/api/desk", tags=["desk"])


def _store(case_id: str, name: str, content: bytes) -> None:
    target = (_data_dir() / "cases" / case_id / Path(name).name).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


@router.post("/upload", response_model=list[str])
async def upload_folder(file: UploadFile, log: Annotated[EventLog, Depends(get_event_log)]) -> list[str]:
    """Upload a zip of PDFs or a single PDF (plan §13.5 /desk); each PDF becomes a case id (its file stem)."""
    name = file.filename or ""
    content = await file.read()
    ct = file.content_type or ""
    ids: list[str] = []
    if name.endswith(".zip") or ct in ("application/zip", "application/x-zip-compressed"):
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            for member in z.namelist():
                if member.endswith("/") or not member.lower().endswith(".pdf"):
                    continue
                case_id = Path(member).stem
                _store(case_id, member, z.read(member))
                ids.append(case_id)
    elif name.lower().endswith(".pdf") or ct == "application/pdf":
        case_id = Path(name).stem
        _store(case_id, name, content)
        ids.append(case_id)
    else:
        raise HTTPException(status_code=415, detail="desk upload takes a zip of PDFs or a single PDF")
    if not ids:
        raise HTTPException(status_code=422, detail="the zip holds no PDF")
    return ids


@router.get("/board", response_model=DeskBoard)
async def get_board(log: Annotated[EventLog, Depends(get_event_log)]) -> DeskBoard:
    """Triage board, most urgent first (ascending urgency_rank)."""
    from vakeel_sahayak.record import views

    cards: list[TriageCard] = []
    for case_id in service.all_case_ids(log):
        raw = views._latest(log.read(case_id), "triage_card")
        if raw is not None:
            cards.append(TriageCard.model_validate(raw))
    cards.sort(key=lambda c: c.urgency_rank)
    return DeskBoard(cards=cards)


@router.post("/{case_id}/open", response_model=CaseSummary)
async def open_case(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> CaseSummary:
    """Open a case from the board; it approves nothing, so the case still needs its own Gate 2 (plan §16)."""
    service.require_case(log, case_id)
    return service.case_summary(log, GateGuard(log), case_id)
