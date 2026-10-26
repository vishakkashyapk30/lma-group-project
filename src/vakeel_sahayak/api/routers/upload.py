"""Router 'upload' (plan §4.1 K1-K10, §4.5, §16): files and dictation come in; raw files stay on the laptop.

Raw client files are stored below `$VS_DATA_DIR/cases/<case_id>/` (laptop only); the event log holds file names only, never
page text (plan §16). Audio is transcribed, read back for confirmation, and deleted unless counsel asks to keep it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from vakeel_sahayak.api.deps import _data_dir, get_event_log
from vakeel_sahayak.api.models import UploadResponse
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

router = APIRouter(prefix="/api/cases/{case_id}", tags=["upload"])

# Plan §4.1 K1-K10: PDFs, photos (JPG/PNG/HEIC) and DOCX are read directly.
ACCEPTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".docx"}


def _case_dir(case_id: str) -> Path:
    return (_data_dir() / "cases" / case_id).resolve()


def _looks_corrupt(content: bytes) -> bool:
    """True when a PDF cannot be opened at all (K9: a broken file is never guessed at)."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=content, filetype="pdf") as doc:
            return doc.page_count == 0 and len(content) > 64  # a real-looking file that still has no pages
    except ImportError:
        return False
    except Exception:  # noqa: BLE001 - any open failure means the file is unusable
        return True


@router.post("/upload", response_model=UploadResponse)
async def upload_files(case_id: str, files: list[UploadFile], log: Annotated[EventLog, Depends(get_event_log)]) -> UploadResponse:
    """Upload PDFs, photos or DOCX (plan §4.1); raw files stay on the laptop."""
    accepted: list[str] = []
    questions: list[str] = []
    case_dir = _case_dir(case_id)
    for upload in files:
        name = Path(upload.filename or "").name  # strips any directory part: a name cannot escape the case directory
        suffix = Path(name).suffix.lower()
        content = await upload.read()
        if suffix not in ACCEPTED_SUFFIXES:
            raise HTTPException(status_code=415, detail=f"unsupported file type {suffix or name!r}")
        target = case_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        accepted.append(name)
        if suffix == ".pdf" and _looks_corrupt(content):
            questions.append(f"{name} could not be opened. Please upload an unlocked or intact copy.")
    log.append(Event(event_id="", case_id=case_id, ts="", kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "upload", "files": accepted}))  # names only, never page text (plan §16)
    # The agents run in a worker thread: inside this async handler they would freeze every other request (and the event stream).
    questions += await run_in_threadpool(_run_intake, log, case_id, [str(case_dir / name) for name in accepted])
    return UploadResponse(case_id=case_id, accepted=accepted, questions=questions)


def _run_intake(log: EventLog, case_id: str, paths: list[str]) -> list[str]:
    """Run Munshi over the just-uploaded files, then Peshkar (dossier, List of Dates, Rights Radar), as the graph's intake and
    dossier nodes do (plan §13.6 flow 1); returns any questions Munshi raised. A failed intake is swallowed so the upload
    response still returns (the error is recorded in the log by the agent)."""
    if not paths:
        return []
    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.api import service
    from vakeel_sahayak.orchestration.state import CaseGraphState
    from vakeel_sahayak.schemas.enums import AgentName

    try:
        state = CaseGraphState(case_id=case_id, log_path=log.db_path, files=paths)
        munshi = create_agent(AgentName.MUNSHI, service.agent_context(log, case_id))
        try:
            state = munshi.run(state)
        finally:
            munshi.close()
        report = state.ingestion
        questions = list(report.questions) if report is not None else []
        peshkar = create_agent(AgentName.PESHKAR, service.agent_context(log, case_id))
        try:
            peshkar.run(state)
        finally:
            peshkar.close()
        return questions
    except Exception:  # noqa: BLE001 - intake failure must not fail the upload; the agent logs the error
        return []


@router.post("/audio", response_model=UploadResponse)
async def upload_audio(case_id: str, file: UploadFile, log: Annotated[EventLog, Depends(get_event_log)], keep: bool = False) -> UploadResponse:
    """Voice dictation (plan §4.5): transcribe, read the dates and sections back for confirmation, delete the audio unless kept."""
    from vakeel_sahayak.models.factory import get_asr

    case_dir = _case_dir(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    audio_path = case_dir / Path(file.filename or "dictation.wav").name
    audio_path.write_bytes(await file.read())
    try:
        transcript = get_asr().transcribe(str(audio_path))
    finally:
        if not keep:
            audio_path.unlink(missing_ok=True)

    # Dictated facts are USER_STATED, never VERIFIED without a court record (plan §4.5). The log holds pseudonymised text only (plan §16): the
    # names in the transcript get the case's aliases (learned here too, so a name first heard in dictation is replaced everywhere later).
    from vakeel_sahayak.privacy.pseudonymise import load_map, pseudonymise_text, save_map

    mapping = load_map(case_id)
    stated, _ = pseudonymise_text(transcript, case_id, mapping)
    save_map(case_id, mapping)
    log.append(Event(event_id="", case_id=case_id, ts="", kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "state_field", "field": "personal", "value": [stated], "chat": "dictation"}))
    question = f"I heard: {transcript} Please confirm these dates and sections before I rely on them."
    return UploadResponse(case_id=case_id, accepted=[Path(file.filename or "dictation.wav").name], questions=[question])
