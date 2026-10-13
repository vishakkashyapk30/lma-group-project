"""ChangeSet schema (plan §7.4, §10)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldChange(BaseModel):
    """One changed dossier field (plan §7.4)."""

    field: str
    old_hash: str | None = None
    new_hash: str | None = None


class ChangeSet(BaseModel):
    """Approved diff driving incremental redrafting (plan §7.4, §10)."""

    case_id: str
    trigger: str  # new_document | clock | counsel_edit
    fields: list[FieldChange] = Field(default_factory=list)
    new_event_ids: list[str] = Field(default_factory=list)
    rights_changed: list[str] = Field(default_factory=list)
