"""Request and response models for the API (plan §13.5). Core schemas live in vakeel_sahayak.schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import ExportFormat
from vakeel_sahayak.schemas.triage import TriageCard


class NewCaseRequest(BaseModel):
    """Create a case."""

    title: str | None = None


class ChatRequest(BaseModel):
    """Counsel's chat message."""

    text: str


class ApproveRequest(BaseModel):
    """Gate approval."""

    acknowledged_fields: list[str] = Field(default_factory=list)


class FieldEditRequest(BaseModel):
    """Counsel edits a dossier field (status becomes USER_EDITED)."""

    value: Any


class ExportRequest(BaseModel):
    """Export request."""

    format: ExportFormat = ExportFormat.DOCX


class UploadResponse(BaseModel):
    """Result of an upload."""

    case_id: str
    accepted: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class DeskBoard(BaseModel):
    """Triage board."""

    cards: list[TriageCard] = Field(default_factory=list)
