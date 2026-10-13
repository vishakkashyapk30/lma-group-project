"""TriageCard schema (plan §11)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.ids import CaseId


class TriageCard(BaseModel):
    """Pairokar's per-case card (plan §11)."""

    case_id: CaseId
    urgency_rank: int
    reasons: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    missing_docs: list[str] = Field(default_factory=list)
    next_step: str | None = None
