"""Router 'library' (plan §13.1, §13.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vakeel_sahayak.schemas.store_rows import ParagraphRecord

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/search", response_model=list[ParagraphRecord])
async def search_precedents(q: str) -> list[ParagraphRecord]:
    """Precedent explorer search (plan §13.5 /library).

    Args:
        q: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/citations/{doc_id}", response_model=dict[str, Any])
async def get_citation_graph(doc_id: str) -> dict[str, Any]:
    """Citation graph with good-law badges.

    Args:
        doc_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("/bridge/{code}/{section}", response_model=dict[str, Any])
async def get_bridge(code: str, section: str) -> dict[str, Any]:
    """IPC<->BNS bridge with text diff.

    Args:
        code: see behaviour
        section: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
