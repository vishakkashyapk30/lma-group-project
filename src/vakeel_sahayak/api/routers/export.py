"""Router 'export' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter

from vakeel_sahayak.api.models import ExportRequest

router = APIRouter(prefix="/api/cases/{case_id}/export", tags=["export"])


@router.post("", response_model=list[str])
async def export_case(case_id: str, body: ExportRequest) -> list[str]:
    """Gated export of DOCX/PDF; 403 unless Gate 2 approved for this case (plan §16).

    Args:
        case_id: see behaviour
        body: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
