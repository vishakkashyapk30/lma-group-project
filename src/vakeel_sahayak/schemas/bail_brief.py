"""BailBrief schema with claim dependencies and state (plan §8.1, §10)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    ClaimState,
    Factor,
    FactorStance,
    GoodLawStatus,
    OpenIssueType,
    TransferFlag,
)
from vakeel_sahayak.schemas.ids import CaseId

DRAFT_LABEL = "AI-generated draft. Not legal advice."  # shown on every brief and export (plan §8.1, §16)


class Authority(BaseModel):
    """A cited authority; citation text is rendered from corpus metadata, never model-written (plan §8.1)."""

    doc_id: str
    para: int
    citation: str | None = None
    transfer: TransferFlag | None = None
    good_law: GoodLawStatus = GoodLawStatus.UNKNOWN
    sc_root: str | None = None


class DependsOn(BaseModel):
    """Dependencies of a claim for truth maintenance (plan §10)."""

    facts: dict[str, str] = Field(default_factory=dict)  # field -> value hash 'h:3f2a'
    events: list[str] = Field(default_factory=list)
    rights: list[str] = Field(default_factory=list)
    authorities: list[str] = Field(default_factory=list)  # 'doc_id#para'
    claims: list[str] = Field(default_factory=list)  # claims this one cites


class Ground(BaseModel):
    """One ground of the brief (plan §8.1)."""

    id: str
    factor: Factor
    stance: FactorStance
    argument: str
    authorities: list[Authority] = Field(default_factory=list)
    depends_on: DependsOn = Field(default_factory=DependsOn)
    check: ClaimCheck = ClaimCheck.NEEDS_REVIEW
    state: ClaimState = ClaimState.CURRENT


class OpenIssue(BaseModel):
    """Open issue surfaced to counsel (plan §8.1)."""

    type: OpenIssueType
    item: str


class StatutoryPosition(BaseModel):
    """Statutory position block (plan §8.1)."""

    sections: list[str] = Field(default_factory=list)
    bailable: bool | None = None
    max_punishment: str | None = None
    rights: str | None = None


class BailBrief(BaseModel):
    """Vakeel's brief (plan §8.1)."""

    case_id: CaseId
    statutory_position: StatutoryPosition = Field(default_factory=StatutoryPosition)
    grounds: list[Ground] = Field(default_factory=list)
    open_issues: list[OpenIssue] = Field(default_factory=list)
    label: str = DRAFT_LABEL

    @field_validator("label")
    @classmethod
    def _label_is_fixed(cls, value: str) -> str:
        """The draft label cannot be removed or reworded (plan §8.1, §16)."""
        if value != DRAFT_LABEL:
            raise ValueError(f"label must be exactly {DRAFT_LABEL!r}")
        return value
