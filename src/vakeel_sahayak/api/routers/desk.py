"""Router 'desk' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile

from vakeel_sahayak.api.models import DeskBoard
from vakeel_sahayak.schemas.case import CaseSummary

router = APIRouter(prefix="/api/desk", tags=["desk"])


@router.post("/upload", response_model=list[str])
async def upload_folder(file: UploadFile) -> list[str]:
    """Upload a folder or zip (plan §13.5 /desk).

    Args:
        file: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/board", response_model=DeskBoard)
async def get_board() -> DeskBoard:
    """Triage board sorted by urgency.

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.post("/{case_id}/open", response_model=CaseSummary)
async def open_case(case_id: str) -> CaseSummary:
    """Open a case from the board; each case still needs its own approval.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
