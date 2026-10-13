"""CaseDossier schema (plan §7.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.ids import CaseId, IsoDate


class FirValue(BaseModel):
    """FIR number, police station and date."""

    number: str | None = None
    police_station: str | None = None
    date: IsoDate | None = None


class SectionValue(BaseModel):
    """One charged section with its concordance equivalent (plan §7.1)."""

    as_written: str
    code: str
    section: str
    equivalent: str | None = None
    bailable: bool | None = None
    max_punishment: str | None = None


class ChargeSheetValue(BaseModel):
    """Charge-sheet status."""

    filed: bool
    date: IsoDate | None = None


class PreviousBail(BaseModel):
    """An earlier bail outcome."""

    court: str
    date: IsoDate
    outcome: str


class CoAccusedBail(BaseModel):
    """A co-accused's bail outcome."""

    id: str
    outcome: str
    date: IsoDate | None = None


class DossierFields(BaseModel):
    """The ~15 dossier fields, each tracked (plan §7.1). Note: bnss_479 moved to RightsReport."""

    fir: TrackedField[FirValue] = Field(default_factory=TrackedField)
    offence_date: TrackedField[str] = Field(default_factory=TrackedField)
    sections: TrackedField[list[SectionValue]] = Field(default_factory=TrackedField)
    arrest_date: TrackedField[str] = Field(default_factory=TrackedField)
    first_remand: TrackedField[str] = Field(default_factory=TrackedField)
    custody_days: TrackedField[int] = Field(default_factory=TrackedField)
    charge_sheet: TrackedField[ChargeSheetValue] = Field(default_factory=TrackedField)
    trial_stage: TrackedField[str] = Field(default_factory=TrackedField)
    previous_bail: TrackedField[list[PreviousBail]] = Field(default_factory=TrackedField)
    co_accused_bail: TrackedField[list[CoAccusedBail]] = Field(default_factory=TrackedField)
    antecedents: TrackedField[list[str]] = Field(default_factory=TrackedField)
    personal: TrackedField[list[str]] = Field(default_factory=TrackedField)
    parties: TrackedField[list[str]] = Field(default_factory=TrackedField)


class CaseDossier(BaseModel):
    """Peshkar's dossier (plan §7.1)."""

    case_id: CaseId
    court: str | None = None
    as_of: IsoDate | None = None
    fields: DossierFields = Field(default_factory=DossierFields)
    open_questions: list[str] = Field(default_factory=list)
