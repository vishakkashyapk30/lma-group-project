"""SparringRecord schema (plan §9)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.bail_brief import Authority
from vakeel_sahayak.schemas.enums import ClaimCheck, SparringVerdict
from vakeel_sahayak.schemas.ids import CaseId


class ObjectionGround(BaseModel):
    """What grounds an objection (plan §9): a bank paragraph, refusal reasoning, statute or dossier fact."""

    store: str | None = None
    doc_id: str | None = None
    para: int | None = None
    fact: str | None = None


class Reply(BaseModel):
    """Vakeel's reply to an objection (plan §9)."""

    text: str
    authorities: list[Authority] = Field(default_factory=list)
    check: ClaimCheck = ClaimCheck.NEEDS_REVIEW


class Objection(BaseModel):
    """One prosecution objection (plan §9)."""

    id: str
    against: str  # ground id or 'general'
    factor: str
    objection: str
    grounds: list[ObjectionGround] = Field(default_factory=list)
    reply: Reply | None = None
    verdict: SparringVerdict | None = None
    reason: str | None = None


class SparringRecord(BaseModel):
    """Abhiyojak's output (plan §9)."""

    case_id: CaseId
    rounds: int = 0
    objections: list[Objection] = Field(default_factory=list)
    discarded: list[str] = Field(default_factory=list)  # ungrounded objections, logged
