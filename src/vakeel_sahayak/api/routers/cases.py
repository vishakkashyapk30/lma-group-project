"""Router 'cases' (plan §13.1, §13.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vakeel_sahayak.api.models import FieldEditRequest, NewCaseRequest
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.case import BudgetState, CaseSummary
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=list[CaseSummary])
async def list_cases() -> list[CaseSummary]:
    """Cause list (plan §13.5).

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.post("", response_model=CaseSummary)
async def create_case(body: NewCaseRequest) -> CaseSummary:
    """Create a case.

    Args:
        body: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}", response_model=CaseSummary)
async def get_case(case_id: str) -> CaseSummary:
    """One case.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/ingestion", response_model=IngestionReport)
async def get_ingestion(case_id: str) -> IngestionReport:
    """Latest IngestionReport.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/dossier", response_model=CaseDossier)
async def get_dossier(case_id: str) -> CaseDossier:
    """Dossier tab.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.patch("/{case_id}/dossier/{field}", response_model=CaseDossier)
async def edit_field(case_id: str, field: str, body: FieldEditRequest) -> CaseDossier:
    """Counsel edits a field; status USER_EDITED.

    Args:
        case_id: see behaviour
        field: see behaviour
        body: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/dates", response_model=list[TimelineEvent])
async def get_dates(case_id: str) -> list[TimelineEvent]:
    """Dates tab (List of Dates).

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/rights", response_model=RightsReport)
async def get_rights(case_id: str) -> RightsReport:
    """Rights tab.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.post("/{case_id}/draft", response_model=dict[str, str])
async def start_draft(case_id: str) -> dict[str, str]:
    """Draft bail brief: Sutradhar plans, Vakeel drafts, Abhiyojak spars (plan §13.6 flow 3).

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/brief", response_model=BailBrief)
async def get_brief(case_id: str) -> BailBrief:
    """Brief tab.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/spar", response_model=SparringRecord)
async def get_spar(case_id: str) -> SparringRecord:
    """Spar tab.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/prep", response_model=dict[str, Any])
async def get_prep(case_id: str) -> dict[str, Any]:
    """Hearing-prep card.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/budget", response_model=BudgetState)
async def get_budget(case_id: str) -> BudgetState:
    """Spend and budget hits.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/{case_id}/files/{doc_id}/pages/{page}")
async def get_page_image(case_id: str, doc_id: str, page: int) -> bytes:
    """Page image for the PDF viewer highlights (laptop only).

    Args:
        case_id: see behaviour
        doc_id: see behaviour
        page: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
