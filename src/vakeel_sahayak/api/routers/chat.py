"""Router 'chat' (plan §13.1, §13.5)."""

from __future__ import annotations

from fastapi import APIRouter

from vakeel_sahayak.api.models import ChatRequest
from vakeel_sahayak.schemas.chat import ChatMessage

router = APIRouter(prefix="/api/cases/{case_id}/chat", tags=["chat"])


@router.post("", response_model=ChatMessage)
async def post_chat(case_id: str, body: ChatRequest) -> ChatMessage:
    """Chat (core): Sutradhar routes to store or tool; short cited answers (plan §6.4).

    Args:
        case_id: see behaviour
        body: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError


@router.get("", response_model=list[ChatMessage])
async def get_history(case_id: str) -> list[ChatMessage]:
    """Chat history.

    Args:
        case_id: see behaviour

    Returns:
        Response body.
    """
    raise NotImplementedError
