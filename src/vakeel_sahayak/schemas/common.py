"""Shared building blocks: SourceRef and TrackedField (plan §7.1)."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, model_validator

from vakeel_sahayak.schemas.enums import FieldStatus

T = TypeVar("T")


class SourceRef(BaseModel):
    """Where a value came from (plan §4.4, §7.1): page, box, route, language and quote."""

    doc: str | None = None
    page: int | None = None
    box: list[float] | None = None
    lang: str | None = None
    route: str | None = None
    quote: str | None = None
    quote_en: str | None = None  # English translation of a Hindi quote (plan §4.5)
    tool: str | None = None  # set when status is COMPUTED
    chat: str | None = None  # e.g. 'turn 3' for USER_STATED


class TrackedField(BaseModel, Generic[T]):
    """A dossier value wrapped as {value, source, status} (plan §7.1)."""

    value: T | None = None
    source: SourceRef | None = None
    status: FieldStatus = FieldStatus.UNSUPPORTED

    @model_validator(mode="after")
    def _status_needs_evidence(self) -> TrackedField[T]:
        """Enforce what each status promises (plan §7.1): no verified or computed value without its source."""
        needs_value = (
            FieldStatus.VERIFIED,
            FieldStatus.COMPUTED,
            FieldStatus.USER_STATED,
            FieldStatus.USER_EDITED,
        )
        if self.status in needs_value and self.value is None:
            raise ValueError(f"status {self.status.value} requires a value")
        if self.status in (FieldStatus.VERIFIED, FieldStatus.USER_STATED) and self.source is None:
            raise ValueError(f"status {self.status.value} requires a source")
        if self.status == FieldStatus.COMPUTED and not (self.source and self.source.tool):
            raise ValueError("status COMPUTED requires source.tool")
        return self
