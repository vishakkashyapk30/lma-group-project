"""Case-level view models for the API and UI (plan §13.5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import GateId, Stage
from vakeel_sahayak.schemas.ids import CaseId


class CaseSummary(BaseModel):
    """Card on the /cases cause list (plan §13.5)."""

    case_id: CaseId
    title: str
    stage: Stage
    rights_chips: list[str] = Field(default_factory=list)
    needs_attention: int = 0


class GateStatus(BaseModel):
    """State of an approval gate (plan §13.5)."""

    gate: GateId
    open: bool
    unresolved_unsupported: list[str] = Field(default_factory=list)
    unresolved_needs_review: list[str] = Field(default_factory=list)
    unresolved_unanswered: list[str] = Field(default_factory=list)


class BudgetState(BaseModel):
    """Spend shown in the UI (plan §6.2)."""

    tokens_spent: int = 0
    tokens_cap: int = 150000
    store_calls: dict[str, int] = Field(default_factory=dict)
