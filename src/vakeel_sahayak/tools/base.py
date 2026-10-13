"""ToolSpec and ToolError shared by all tools (plan §3.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import AgentName, StoreName


class ToolSpec(BaseModel):
    """Declarative registration record for a tool. Agents get their tools from configs/tools.yaml, validated against SPEC.agents."""

    name: str
    description: str
    agents: list[AgentName] = Field(default_factory=list)
    stores: list[StoreName] = Field(default_factory=list)
    gated: bool = False  # export is gated by GateGuard
    plan_ref: str = ""


class ToolError(BaseModel):
    """Structured tool failure returned to the agent (plan §15.8 error recovery: OCR crash, store timeout, malformed date)."""

    tool: str
    kind: str
    message: str
    retryable: bool = False
