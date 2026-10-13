"""Router 'upload' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from vakeel_sahayak.api.models import UploadResponse

router = APIRouter(prefix="/api/cases/{case_id}", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_files(case_id: str, files: list[UploadFile]) -> UploadResponse:
    """Upload PDFs, photos, DOCX (plan §4.1 K1-K10); raw files stay on the laptop.

    Args:
        case_id: see behaviour
        files: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.post("/audio", response_model=UploadResponse)
async def upload_audio(case_id: str, file: UploadFile) -> UploadResponse:
    """Voice dictation; audio deleted after transcription unless kept (plan §4.5).

    Args:
        case_id: see behaviour
        file: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
