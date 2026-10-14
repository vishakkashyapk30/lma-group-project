"""Helpers for the Rights Radar tests: date arithmetic oracle and date-format tolerant text matching."""

from __future__ import annotations

import re
from datetime import date, timedelta

from vakeel_sahayak.rights.inputs import RuleInputs


def iso(d: date) -> str:
    return d.isoformat()


def dmy(iso_date: str) -> str:
    """'2024-08-21' -> '21.08.2024' (the format the plan's RightsReport details use)."""
    y, m, d = iso_date.split("-")
    return f"{d}.{m}.{y}"


def mentions_date(text: str, iso_date: str) -> bool:
    """True if `text` shows the date in ISO or the plan's dd.mm.yyyy form. # ASSUMPTION: either format is accepted."""
    return iso_date in text or dmy(iso_date) in text


def day_n(first_remand: date, n: int) -> date:
    """Calendar date of day `n` of a count in which the first remand is day 1 (Appendix C: ED v. Kapil Wadhawan)."""
    return first_remand + timedelta(days=n - 1)


def default_bail_inputs(first_remand: date, as_of: date, max_punishment: str, charge_sheet: date | None = None,
                        application: date | None = None) -> RuleInputs:
    return RuleInputs(
        as_of=iso(as_of),
        first_remand=iso(first_remand),
        charge_sheet_filed=charge_sheet is not None,
        charge_sheet_date=iso(charge_sheet) if charge_sheet else None,
        application_date=iso(application) if application else None,
        max_punishment=max_punishment,
    )


def number_in(text: str, *candidates: int) -> bool:
    """True if any of the candidate integers appears as a standalone number (thousands separators allowed)."""
    found = {int(m.replace(",", "")) for m in re.findall(r"\d[\d,]*", text)}
    return any(c in found for c in candidates)
