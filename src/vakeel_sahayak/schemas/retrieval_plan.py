"""RetrievalPlan and EvidencePack schemas (plan §6.3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus


class BudgetLeft(BaseModel):
    """Remaining budget for a factor (plan §6.3)."""

    store_calls: int
    tokens: int


class PlanStep(BaseModel):
    """One tool call in a plan (plan §6.3). Args may contain '$slot.field' references."""

    slot: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class RetrievalPlan(BaseModel):
    """Sutradhar's per-factor plan, round and assessment (plan §6.3)."""

    factor: Factor
    round: int = 1
    budget_left: BudgetLeft
    steps: list[PlanStep] = Field(default_factory=list)
    assessment: dict[str, str] = Field(default_factory=dict)  # slot -> 'FILLED' | 'WEAK (1 of 2)' | 'MISSING'
    next: str | None = None


class SlotResult(BaseModel):
    """Assessed result for one slot (plan §6.2)."""

    slot: str
    status: SlotStatus
    items: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None


class EvidencePack(BaseModel):
    """Evidence for one factor handed from Sutradhar to Vakeel (plan §6.2 step 3)."""

    factor: Factor
    stance: FactorStance
    reason: str | None = None
    slots: list[SlotResult] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
