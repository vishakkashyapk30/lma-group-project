"""Rule-based facts read from an order's text: dated events, dossier-style fields and the fact signature (plan §5.1, §15.1 G3).

Used by the `caselaw.similar` builder (fact signature) and by the G3 gold labeler. Regexes only; every value is stated
in the text, nothing is inferred beyond arithmetic on stated dates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from vakeel_sahayak.pipelines.section_extract import charged_sections, extract_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date, split_sentences
from vakeel_sahayak.schemas.store_rows import FactSignature

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RE = re.compile(
    rf"\b(?:\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}(?:st|nd|rd|th)?[\s,.-]+{_MONTH}[\s,.-]+\d{{4}}|{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})\b",
    re.IGNORECASE,
)
_WORD_NUMBERS = {
    w: i for i, w in enumerate(
        ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
    )
} | {"fifteen": 15, "eighteen": 18, "twenty": 20, "thirty": 30, "sixty": 60, "ninety": 90}  # fmt: skip
_NUM = r"(\d{1,3}|" + "|".join(_WORD_NUMBERS) + r")"
_DURATION = re.compile(r"(\d{1,3})\s*(days?|months?|years?|yrs?)", re.IGNORECASE)
_CUSTODY_DURATION = re.compile(
    r"(?:in\s+(?:judicial\s+|police\s+)?custody|incarcerated|in\s+jail|behind\s+bars|languish\w*)[^.;]{0,40}?"
    r"(?:for|since|about|nearly|over|more\s+than|almost)?[^.;\d]{0,25}?\b" + _NUM + r"\s*(days?|months?|years?|yrs?)"
    r"|\b" + _NUM + r"\s*(days?|months?|years?|yrs?)\s+(?:in|of)\s+(?:judicial\s+|police\s+)?(?:custody|jail|incarceration)",
    re.IGNORECASE,
)
_SINCE_DATE = re.compile(rf"(?:in\s+custody|incarcerated|in\s+jail|arrested|detained)[^.;]{{0,30}}?\bsince\s+({DATE_RE.pattern})", re.IGNORECASE)
_ARREST = re.compile(rf"\barrest(?:ed)?\b[^.;]{{0,60}}?\bon\s+({DATE_RE.pattern})", re.IGNORECASE)
_CHARGE_SHEET_FILED = re.compile(r"charge[\s-]?sheet\s+(?:has\s+been\s+|was\s+|already\s+)?(?:filed|submitted|laid|presented)|final\s+report\s+(?:has\s+been\s+)?(?:filed|submitted)|filed\s+(?:the\s+)?charge[\s-]?sheet|investigation\s+(?:is\s+|has\s+been\s+)?(?:complete|completed|concluded)", re.IGNORECASE)
_CHARGE_SHEET_NOT = re.compile(r"charge[\s-]?sheet\s+(?:has\s+|is\s+|was\s+)?(?:not\s+(?:yet\s+)?(?:been\s+)?(?:filed|submitted)|yet\s+to\s+be\s+filed)|investigation\s+(?:is\s+)?(?:still\s+)?(?:pending|going\s+on|in\s+progress|ongoing)", re.IGNORECASE)
_CO_ACCUSED = re.compile(r"co[\s-]?accused[^.]{0,100}?\b(?:granted|released|enlarged|admitted)\b[^.]{0,30}?\bbail|co[\s-]?accused[^.]{0,100}?\b(?:bail\s+(?:was\s+)?(?:rejected|declined|refused|denied)|bail\s+application[^.]{0,30}?(?:rejected|dismissed))|(?:bail\s+(?:has\s+been\s+)?granted\s+to|released\s+on\s+bail)[^.]{0,60}?\bco[\s-]?accused", re.IGNORECASE)
_PREVIOUS = re.compile(r"(?:earlier|previous|first|second|prior)\s+(?:regular\s+)?(?:bail\s+)?(?:application|petition)[^.]{0,120}?(?:rejected|dismissed|withdrawn|declined|refused)", re.IGNORECASE)
_TRIAL_STAGE = re.compile(r"charges?\s+(?:have\s+been\s+|were\s+|has\s+been\s+)?framed|trial\s+(?:has\s+)?(?:commenced|begun|started)|evidence\s+(?:has\s+)?(?:commenced|begun)|witnesses?\s+(?:have\s+been\s+)?examined", re.IGNORECASE)

CUSTODY_BANDS = ("under_60d", "60_90d", "90d_6m", "6m_1y", "over_1y")


@dataclass(frozen=True)
class DatedMention:
    """A date found in text with the sentence around it."""

    iso: str
    sentence: str


def extract_dates(text: str) -> list[DatedMention]:
    """Every real date in the text (ISO-normalised) with its sentence, in order, one entry per (date, sentence).

    Args:
        text: order text

    Returns:
        Mentions.
    """
    out: list[DatedMention] = []
    seen: set[tuple[str, str]] = set()
    for sentence in split_sentences(text):
        for m in DATE_RE.finditer(sentence):
            iso = normalise_date(m.group(0).replace(",", ", ").strip())
            key = (iso or "", sentence)
            if iso and key not in seen:
                seen.add(key)
                out.append(DatedMention(iso, sentence[:240]))
    return out


def _duration_days(number: str, unit: str) -> int:
    """Convert '14 months' to days (30-day months, 365-day years)."""
    n = int(number) if number.isdigit() else _WORD_NUMBERS[number.lower()]
    unit = unit.lower()
    return n if unit.startswith("day") else n * 30 if unit.startswith("month") else n * 365


def custody_days(text: str, order_date: str | None = None) -> int | None:
    """Days in custody as the text states them: a stated duration, or 'since <date>' up to the order date.

    Args:
        text: order text
        order_date: ISO date of the order, needed for the 'since <date>' form

    Returns:
        Days, or None when the text states neither.
    """
    if m := _CUSTODY_DURATION.search(text):
        number, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return _duration_days(number, unit)
    if order_date and (m := _SINCE_DATE.search(text)):
        since = normalise_date(m.group(1))
        if since:
            return max(0, (date.fromisoformat(order_date) - date.fromisoformat(since)).days)
    return None


def custody_band(days: int | None) -> str | None:
    """Custody band used in the fact signature; the 60 and 90-day edges are the default-bail limits (plan §7.3)."""
    if days is None:
        return None
    if days < 60:
        return CUSTODY_BANDS[0]
    if days <= 90:
        return CUSTODY_BANDS[1]
    return CUSTODY_BANDS[2] if days <= 182 else CUSTODY_BANDS[3] if days <= 365 else CUSTODY_BANDS[4]


def charge_sheet_status(text: str) -> str | None:
    """'filed', 'not_filed' or None, from the text."""
    if _CHARGE_SHEET_NOT.search(text):
        return "not_filed"
    return "filed" if _CHARGE_SHEET_FILED.search(text) else None


def co_accused_outcome(text: str) -> str | None:
    """'granted' or 'rejected' for a co-accused's bail outcome as stated in the text, else None."""
    m = _CO_ACCUSED.search(text)
    if not m:
        return None
    return "rejected" if re.search(r"rejected|declined|refused|denied|dismissed", m.group(0), re.IGNORECASE) else "granted"


def fact_signature(text: str, order_date: str | None = None) -> FactSignature:
    """The structured fact signature of an order (plan §5.1): sections, custody band, charge-sheet status, co-accused outcome.

    Args:
        text: facts part (or whole order)
        order_date: ISO date of the order, used for 'in custody since <date>'

    Returns:
        FactSignature; fields the text does not state are None or empty.
    """
    return FactSignature(
        sections=charged_sections(extract_sections(text)),
        custody_band=custody_band(custody_days(text, order_date)),
        charge_sheet_status=charge_sheet_status(text),
        co_accused_outcome=co_accused_outcome(text),
    )


def dossier_fields(text: str, order_date: str | None = None) -> dict[str, Any]:
    """Dossier-style fields stated in an order (plan §7.1 names; G3 rules, plan §15.1).

    Args:
        text: whole order text
        order_date: ISO date of the order

    Returns:
        Dict with only the fields found: `sections`, `arrest_date`, `custody_days`, `charge_sheet_filed`,
        `previous_bail`, `co_accused_bail`, `trial_stage`.
    """
    fields: dict[str, Any] = {}
    if sections := charged_sections(extract_sections(text)):
        fields["sections"] = sections
    if m := _ARREST.search(text):
        fields["arrest_date"] = normalise_date(m.group(1))
    if (days := custody_days(text, order_date)) is not None:
        fields["custody_days"] = days
    if status := charge_sheet_status(text):
        fields["charge_sheet_filed"] = status == "filed"
    if _PREVIOUS.search(text):
        fields["previous_bail"] = "rejected_or_withdrawn"
    if outcome := co_accused_outcome(text):
        fields["co_accused_bail"] = outcome
    if _TRIAL_STAGE.search(text):
        fields["trial_stage"] = "charges_framed_or_trial_started"
    return {k: v for k, v in fields.items() if v is not None}
