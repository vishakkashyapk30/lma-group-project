"""Parse a maximum-punishment string such as '7 years', 'life' or 'may extend to ten years' (plan §7.3, App. C)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20,
}  # fmt: skip
_NUMBER = r"(\d+(?:\.\d+)?|" + "|".join(_WORDS) + r")"
_YEARS = re.compile(_NUMBER + r"\s*(?:-\s*)?(years?|yrs?|months?)", re.IGNORECASE)


_FLOOR = re.compile(
    r"not\s+less\s+than|at\s+least|minimum|or\s+more|or\s+above|and\s+above|more\s+than|exceeding|above\s+\d", re.IGNORECASE
)


class PunishmentKind(str, Enum):
    """Shape of a maximum punishment."""

    DEATH = "death"
    LIFE = "life"
    YEARS = "years"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Punishment:
    """A parsed maximum punishment; `years` is set only for a fixed term."""

    kind: PunishmentKind
    years: float | None = None
    text: str = ""

    @property
    def capital_or_life(self) -> bool:
        """True for death or life imprisonment."""
        return self.kind in (PunishmentKind.DEATH, PunishmentKind.LIFE)

    @property
    def is_minimum_wording(self) -> bool:
        """True when the text states a floor ('not less than 10 years', '10 years or more', 'more than 10 years')."""
        return self.kind == PunishmentKind.YEARS and bool(_FLOOR.search(self.text))

    @property
    def is_ten_years(self) -> bool:
        """True for a ten-year maximum ('may extend to ten years'): unsettled for the 60/90-day rule (App. C).

        A floor of ten years ('10 years or more') is not this case: App. C puts it on the 90-day limit.
        """
        return self.kind == PunishmentKind.YEARS and self.years == 10 and not self.is_minimum_wording

    @property
    def ninety_day(self) -> bool:
        """True when default bail has the 90-day limit: death, life, a term over ten years, or ten years or more."""
        if self.capital_or_life:
            return True
        years = self.years or 0.0
        return self.kind == PunishmentKind.YEARS and (years > 10 or (years == 10 and self.is_minimum_wording))

    def severity(self) -> float:
        """Ordering key: death > life > longer terms; unknown sorts lowest."""
        if self.kind == PunishmentKind.DEATH:
            return 1e9
        if self.kind == PunishmentKind.LIFE:
            return 1e8
        return self.years or 0.0


def parse_punishment(text: str | None) -> Punishment:
    """Parse free text into a Punishment; anything not understood is UNKNOWN (rules then return CHECK).

    Args:
        text: for example '7 years', 'imprisonment for life', 'death', 'up to three years and fine'

    Returns:
        The parsed punishment.
    """
    raw = (text or "").strip()
    low = raw.lower()
    if not low:
        return Punishment(PunishmentKind.UNKNOWN, None, raw)
    if re.search(r"\bdeath\b", low):
        return Punishment(PunishmentKind.DEATH, None, raw)
    if re.search(r"\blife\b", low):
        return Punishment(PunishmentKind.LIFE, None, raw)
    match = _YEARS.search(low)
    if match:
        num = match.group(1)
        value = float(_WORDS.get(num, num))
        years = value / 12 if match.group(2).startswith("m") else value
        return Punishment(PunishmentKind.YEARS, years, raw)
    return Punishment(PunishmentKind.UNKNOWN, None, raw)


def most_severe(texts: list[str | None]) -> str | None:
    """The most severe of several punishments, or None if any is missing or not understood (conservative)."""
    parsed = [parse_punishment(t) for t in texts]
    if not parsed or any(p.kind == PunishmentKind.UNKNOWN for p in parsed):
        return None
    return max(parsed, key=lambda p: p.severity()).text
