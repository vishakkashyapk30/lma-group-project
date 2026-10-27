"""Rule inputs derived from the dossier and timeline (plan §7.3, Appendix C)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleInputs(BaseModel):
    """Superset of inputs any rule may read (Appendix C 'Inputs' column)."""

    as_of: str
    first_remand: str | None = None
    charge_sheet_date: str | None = None
    charge_sheet_filed: bool | None = None
    arrest_date: str | None = None
    production_date: str | None = None
    arrest_time: str | None = None
    production_time: str | None = None
    max_punishment: str | None = None  # e.g. '7 years', 'life', 'death'
    sections: list[str] = Field(default_factory=list)
    custody_days: int | None = None
    antecedents_known: bool = False
    first_time_offender: bool | None = None
    application_date: str | None = None
    arrest_memo_present: bool | None = None
    grounds_communicated: bool | None = None
    special_act: str | None = None
    # HA-03 (docs/qa/rights-verification.md): None means not on record
    other_pending_cases: bool | None = None  # BNSS s.479(2): another investigation, inquiry or trial pending against the person
    fir_date: str | None = None  # the date the case was registered (before or after 1 July 2024 decides which act applies)
    grounds_in_writing: bool | None = None  # were the grounds of arrest given in writing (Mihir Rajesh Shah)
