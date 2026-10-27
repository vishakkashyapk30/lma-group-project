"""Request and response models for the API (plan §13.5). Core schemas live in vakeel_sahayak.schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.enums import ExportFormat
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport
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


class RightsCheckOut(RightsCheckResult):
    """One Rights Radar check as the API returns it: the stored fields plus `verification` ('unverified' until a person re-checks the rule text against the bare act, else the date)."""

    verification: str = "unverified"


class RightsReportOut(RightsReport):
    """`GET /api/cases/{id}/rights`: the stored report plus, additively, `verification` on every check and `unverified_checks` (the names). The stored report and its golden files are unchanged."""

    checks: list[RightsCheckOut] = Field(default_factory=list)  # type: ignore[assignment]
    unverified_checks: list[str] = Field(default_factory=list)  # type: ignore[assignment]

    model_config = {"json_schema_extra": {"example": {
        "case_id": "case-0007", "as_of": "2025-02-03", "unverified_checks": ["default_bail_window"],
        "checks": [{"check": "default_bail_window", "status": "WINDOW_OPEN", "detail": "Default-bail window opens in 3 days", "uses": ["custody_start"], "rule": "BNSS s.187(3)",
                    "rule_text": "Default bail if the charge sheet is not filed within 60 or 90 days.", "sources": ["BNSS s.187(3)"], "dates": {"first_remand": "2024-08-21"},
                    "last_verified": None, "verification": "unverified"}]}}}

    @classmethod
    def from_report(cls, report: RightsReport) -> RightsReportOut:
        """Build the API view of a stored report (nothing is written back)."""
        checks = [RightsCheckOut(**c.model_dump(), verification=c.verification) for c in report.checks]
        return cls(case_id=report.case_id, as_of=report.as_of, checks=checks, unverified_checks=report.unverified_checks)
