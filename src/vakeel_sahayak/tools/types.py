"""Result types returned by tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import ConcordanceEdgeType, GateId, GoodLawStatus, StoreName, TransferFlag


class TextLayerResult(BaseModel):
    """Text layer of a page."""

    text: str
    boxes: list[list[float]] = Field(default_factory=list)


class LayoutResult(BaseModel):
    """Layout-parser result (tables, columns)."""

    text: str
    tables: list[list[list[str]]] = Field(default_factory=list)


class OcrResult(BaseModel):
    """OCR output."""

    text: str
    mean_conf: float
    boxes: list[list[float]] = Field(default_factory=list)
    lang: str


class ScriptInfo(BaseModel):
    """Detected script."""

    script: str
    confidence: float


class TranscriptResult(BaseModel):
    """Speech transcript."""

    text: str
    lang: str | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)


class FileItemResult(BaseModel):
    """Result of filing an item."""

    store: StoreName
    item_id: str


class SpanCheckResult(BaseModel):
    """span_check outcome (plan §7.1)."""

    supported: bool
    score: float
    quote: str


class DateCalcResult(BaseModel):
    """date_calc outcome."""

    value: int | str
    rule: str
    start: str
    end: str


class MapSectionResult(BaseModel):
    """map_section outcome (plan §5.1, §5.4)."""

    equivalent: str | None = None
    edge_type: ConcordanceEdgeType | None = None
    ambiguous: bool = False
    governing: str | None = None  # reference that governs an offence on the given date (BNS era from 2024-07-01)
    candidates: list[str] = Field(default_factory=list)


class TransferCheckResult(BaseModel):
    """transfer_check outcome (plan §5.4)."""

    flag: TransferFlag
    text_diff: str | None = None
    qualification: str | None = None


class GoodLawResult(BaseModel):
    """good_law_check outcome (plan §5.3)."""

    status: GoodLawStatus
    overruled_by: str | None = None
    sc_root: str | None = None
    note: str | None = None


class ClaimCheckResult(BaseModel):
    """check_claim outcome (plan §8.1)."""

    supported: bool
    fact_support: float | None = None
    authority_support: float | None = None
    transfer: TransferFlag | None = None
    good_law: GoodLawStatus | None = None
    unretrieved_citations: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    """request_approval outcome."""

    gate: GateId
    checklist_open: bool
    unresolved: list[str] = Field(default_factory=list)
