"""Row types stored in the ten stores (plan §5)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import (
    ConcordanceEdgeType,
    DocumentType,
    Factor,
    FieldStatus,
    InfoKind,
    OrderPart,
    Treatment,
)
from vakeel_sahayak.schemas.ids import IsoDate


class StatuteRow(BaseModel):
    """One section of IPC/BNS/CrPC/BNSS or a special-act bar (plan §5.1)."""

    code: str
    section: str
    text: str
    max_punishment: str | None = None
    bailable: bool | None = None
    cognisable: bool | None = None


class ConcordanceEdge(BaseModel):
    """IPC<->BNS or CrPC<->BNSS edge with text diff (plan §5.1, §5.4)."""

    old_ref: str
    new_ref: str
    type: ConcordanceEdgeType
    text_diff: str | None = None


class ParagraphRecord(BaseModel):
    """A paragraph row with metadata (plan §5.2)."""

    doc_id: str
    para: int
    court: str
    date: str
    outcome: str | None = None
    part: OrderPart
    sections: list[str] = Field(default_factory=list)
    section_family: list[str] = Field(default_factory=list)
    factors: list[Factor] = Field(default_factory=list)
    cites: list[str] = Field(default_factory=list)
    authority: float = 0.0
    text: str = ""


class CitationEdge(BaseModel):
    """Citing -> cited edge with treatment (plan §5.3)."""

    citing_doc_id: str
    cited_doc_id: str
    treatment: Treatment = Treatment.UNKNOWN
    court_level: str | None = None
    sentence: str | None = None


class FactSignature(BaseModel):
    """Structured fact signature of an order (plan §5.1)."""

    sections: list[str] = Field(default_factory=list)
    custody_band: str | None = None
    charge_sheet_status: str | None = None
    co_accused_outcome: str | None = None


class SimilarOrderRow(BaseModel):
    """One whole-order facts vector's metadata plus signature (plan §5.1)."""

    doc_id: str
    court: str
    date: str
    signature: FactSignature = Field(default_factory=FactSignature)


class TimelineEvent(BaseModel):
    """A dated event with source (plan §4.4, §7.2)."""

    event_id: str
    date: IsoDate
    label: str
    source: SourceRef | None = None
    status: FieldStatus = FieldStatus.VERIFIED
    conflicts_with: list[str] = Field(default_factory=list)


class CaseChunk(BaseModel):
    """A structure-aware chunk of a client document (plan §4.4)."""

    chunk_id: str
    doc_id: str
    doc_type: DocumentType
    page: int
    box: list[float] | None = None
    text: str
    text_en: str | None = None
    info_kinds: list[InfoKind] = Field(default_factory=list)
