"""Chat message schema (plan §6.4)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import AgentName, StoreName


class ToolChip(BaseModel):
    """Store/tool chip shown on an answer (plan §13.5)."""

    tool: str
    store: StoreName | None = None


class ChatMessage(BaseModel):
    """A chat turn (plan §6.4, §13.5)."""

    message_id: str
    case_id: str
    role: str  # counsel | agent
    agent: AgentName | None = None
    text: str
    chips: list[ToolChip] = Field(default_factory=list)
    refused: bool = False  # prediction / lay-advice requests are refused
