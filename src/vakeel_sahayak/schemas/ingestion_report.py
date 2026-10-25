"""IngestionReport schema (plan §4.6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_serializer

from vakeel_sahayak.schemas.enums import DocumentType, PageStatus
from vakeel_sahayak.schemas.ids import CaseId


class PageRoute(BaseModel):
    """Route taken for one page (plan §4.6)."""

    page: int
    kind: str
    route: list[str]
    ocr_conf: float | None = None
    status: PageStatus = PageStatus.OK
    confidence: float | None = None  # set only for a page kept as a low-confidence read (dictionary-word share of its text layer)

    @model_serializer(mode="wrap")
    def _omit_unset_confidence(self, handler: Any) -> dict[str, Any]:
        """Leave `confidence` out of the dump when it is None, so reports of a default run are unchanged."""
        data = handler(self)
        if data.get("confidence") is None:
            data.pop("confidence", None)
        return data


class DocumentEntry(BaseModel):
    """One document found in a file (plan §4.6)."""

    doc_id: str
    type: DocumentType
    pages: list[int]  # [first, last]
    lang: str
    type_confidence: float | None = None
    page_routes: list[PageRoute] = Field(default_factory=list)


class FiledCounts(BaseModel):
    """Counts of items filed into the case shelf (plan §4.6)."""

    timeline_events: int = 0
    parties: int = 0
    sections: int = 0
    chunks: int = 0


class Gap(BaseModel):
    """A bail-file checklist gap and the action taken (plan §4.3 step 4)."""

    item: str
    action: str


class IngestionReport(BaseModel):
    """Munshi's output (plan §4.6)."""

    case_id: CaseId
    file: str
    documents: list[DocumentEntry] = Field(default_factory=list)
    filed: FiledCounts = Field(default_factory=FiledCounts)
    gaps: list[Gap] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
