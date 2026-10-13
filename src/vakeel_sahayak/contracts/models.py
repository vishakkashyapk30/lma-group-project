"""Contract models (plan §6.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import Factor, StoreName


class Slot(BaseModel):
    """One evidence slot of a contract (plan §6.1). need: 'required', 'optional' or an integer count."""

    need: str | int
    stores: list[StoreName] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)  # non-store sources, e.g. rights_check, date_calc
    description: str = ""


class ContractBudget(BaseModel):
    """Per-factor budget (plan §6.1)."""

    store_calls: int = 8
    tokens: int = 12000


class EvidenceContract(BaseModel):
    """Declarative evidence needs for one factor (plan §6.1, Appendix B). Fixes what evidence and where it may be; Sutradhar decides the rest."""

    factor: Factor
    number: int  # Appendix A order
    name: str
    applies_if: str
    slots: dict[str, Slot]
    budget: ContractBudget = Field(default_factory=ContractBudget)
