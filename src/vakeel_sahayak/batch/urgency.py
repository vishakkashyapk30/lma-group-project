"""The fixed urgency rule (plan §11).

The order never changes and is always explainable. Most urgent first:

1. **legal deadlines**: a default-bail window that is open (BNSS s.187(3)), one that opens within `SOON_DAYS`, or the
   s.479 undertrial threshold already crossed. Among them: open default-bail windows, then windows opening soon (the
   nearest first), then s.479 cases;
2. **days past a threshold** (the longer past, the sooner);
3. **custody length** (the longer, the sooner).

Ties go to the case with no missing documents. Nothing here is learned or estimated: every position comes from the
Rights Radar's own statuses and dates, and `assess` returns the reasons as codes (machine-readable) and as the text
shown on the TriageCard. A TriageCard carries only the text; `parse_reasons` reads it back (the texts are produced here
only), so `rank` can order cards without the rights report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.triage import TriageCard

SOON_DAYS = 7  # a default-bail window opening within this many days is a legal deadline

CODE_DEFAULT_BAIL_OPEN = "default_bail_open"
CODE_DEFAULT_BAIL_SOON = "default_bail_soon"
CODE_DEFAULT_BAIL_CLOSED = "default_bail_closed"
CODE_S479_CROSSED = "s479_crossed"
CODE_CUSTODY = "custody_length"
SUB_ORDER = {CODE_DEFAULT_BAIL_OPEN: 0, CODE_DEFAULT_BAIL_SOON: 1, CODE_S479_CROSSED: 2}
_NO_DEADLINE = 3

_TEXT_OPEN = "Default-bail window open for {days} day(s) (BNSS s.187(3))"
_TEXT_SOON = "Default-bail window opens in {days} day(s) (BNSS s.187(3))"
_TEXT_CLOSED = "Default-bail window closed: charge sheet {days} day(s) past the limit (BNSS s.187(3))"
_TEXT_479 = "s.479 threshold crossed {days} day(s) ago (BNSS s.479)"
_TEXT_CUSTODY = "In custody {days} days"
_PARSE = {
    CODE_DEFAULT_BAIL_OPEN: re.compile(r"Default-bail window open for (\d+) day"),
    CODE_DEFAULT_BAIL_SOON: re.compile(r"Default-bail window opens in (\d+) day"),
    CODE_DEFAULT_BAIL_CLOSED: re.compile(r"Default-bail window closed: charge sheet (\d+) day"),
    CODE_S479_CROSSED: re.compile(r"s\.479 threshold crossed (\d+) day"),
    CODE_CUSTODY: re.compile(r"In custody (\d+) days"),
}
_THRESHOLD_DAYS = re.compile(r"threshold[^.]*? of ([\d,]+) days")
_DAYS_PAST = re.compile(r"(\d+) days? past")  # the Radar's own wording, e.g. '12 days past the limit'
_OPENS_IN = re.compile(r"opens in (\d+) days?|(\d+) day\(s\) from now")
_LIMIT = re.compile(r"(\d+)-day limit")
_FILED_ON_DAY = re.compile(r"filed on day (\d+)")


@dataclass(frozen=True)
class UrgencyReason:
    """One reason a case sits where it does: a code, the days it rests on, the rule and the TriageCard text."""

    code: str
    days: int
    text: str
    rule: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON-able form."""
        return {"code": self.code, "days": self.days, "text": self.text, "rule": self.rule}


@dataclass(frozen=True)
class Urgency:
    """The urgency of one case: the sort key (smaller = more urgent) and why."""

    key: tuple
    reasons: list[UrgencyReason] = field(default_factory=list)
    legal_deadline: bool = False

    def texts(self) -> list[str]:
        """The reasons as TriageCard text."""
        return [r.text for r in self.reasons]

    def codes(self) -> list[str]:
        """The reasons' codes."""
        return [r.code for r in self.reasons]


def _day(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _default_bail(rights: RightsReport | None, soon_days: int) -> tuple[str, int] | None:
    """('open', days open), ('soon', days to go) or ('closed', days past the limit) for the default-bail check, else None.

    Dates come from the check's `dates` (window_opens against as_of) when it has them, else from the Radar's own
    wording in `detail` ('N days past', 'opens in N days').
    """
    check = rights.get(RightsCheckName.DEFAULT_BAIL) if rights is not None else None
    if check is None:
        return None
    detail = check.detail or ""
    as_of, opens = _day(rights.as_of), _day(check.dates.get("window_opens"))  # type: ignore[union-attr]
    if check.status == RightsStatus.ELIGIBLE and not check.dates.get("charge_sheet"):  # no charge sheet yet: the right is live
        if as_of and opens:
            return "open", max(0, (as_of - opens).days)
        m = _DAYS_PAST.search(detail)
        return "open", int(m.group(1)) if m else 0
    if check.status == RightsStatus.NOT_YET:
        if as_of and opens:
            left = (opens - as_of).days
        else:
            m = _OPENS_IN.search(detail)
            left = int(m.group(1) or m.group(2)) if m else None
        return ("soon", left) if left is not None and 0 < left <= soon_days else None
    if check.status == RightsStatus.WINDOW_CLOSED:
        limit, filed = _LIMIT.search(detail), _FILED_ON_DAY.search(detail)
        if limit and filed and int(filed.group(1)) > int(limit.group(1)):
            return "closed", int(filed.group(1)) - int(limit.group(1))
    return None


def _days_past_479(rights: RightsReport | None, custody_days: int | None) -> int | None:
    """Days past the s.479 threshold when it is crossed (0 when the threshold's size is not stated), else None."""
    check = rights.get(RightsCheckName.UNDERTRIAL_LIMIT) if rights is not None else None
    if check is None or check.status != RightsStatus.ELIGIBLE:
        return None
    explicit = _DAYS_PAST.search(check.detail or "")
    if explicit:
        return int(explicit.group(1))
    m = _THRESHOLD_DAYS.search(check.detail or "")
    if m and custody_days is not None:
        return max(0, custody_days - int(m.group(1).replace(",", "")))
    return 0


def assess(rights: RightsReport | None, custody_days: int | None, missing_docs: list[str], soon_days: int = SOON_DAYS) -> Urgency:
    """Apply the urgency rule to one case.

    Args:
        rights: the Rights Radar report (None: no legal deadline can be shown)
        custody_days: days in custody as of the report (None when unknown)
        missing_docs: documents still missing (ties go to cases with none)
        soon_days: how soon "opening soon" is

    Returns:
        Urgency: key, reasons (codes and text), and whether a legal deadline applies.
    """
    reasons: list[UrgencyReason] = []
    db = _default_bail(rights, soon_days)
    past_479 = _days_past_479(rights, custody_days)
    sub, left, past = _NO_DEADLINE, 0, 0
    if db is not None:
        kind, days = db
        code, text = {"open": (CODE_DEFAULT_BAIL_OPEN, _TEXT_OPEN), "soon": (CODE_DEFAULT_BAIL_SOON, _TEXT_SOON), "closed": (CODE_DEFAULT_BAIL_CLOSED, _TEXT_CLOSED)}[kind]
        reasons.append(UrgencyReason(code, days, text.format(days=days), "BNSS s.187(3)"))
        if kind != "closed":  # a closed window is a threshold passed (criterion 2), no longer a deadline
            sub = SUB_ORDER[code]
        left, past = (days, 0) if kind == "soon" else (0, days)
    if past_479 is not None:
        reasons.append(UrgencyReason(CODE_S479_CROSSED, past_479, _TEXT_479.format(days=past_479), "BNSS s.479"))
        sub = min(sub, SUB_ORDER[CODE_S479_CROSSED])
        past = max(past, past_479)
    if custody_days is not None:
        reasons.append(UrgencyReason(CODE_CUSTODY, custody_days, _TEXT_CUSTODY.format(days=custody_days)))
    deadline = sub != _NO_DEADLINE
    key = (0 if deadline else 1, sub, left, -past, -(custody_days or 0), 1 if missing_docs else 0)
    return Urgency(key=key, reasons=reasons, legal_deadline=deadline)


def urgency_key(rights: RightsReport, custody_days: int | None, missing_docs: list[str]) -> tuple:
    """Fixed, explainable urgency order: (1) legal deadlines, (2) days past a threshold, (3) custody length; ties to cases with no missing documents (plan §11).

    Args:
        rights: the Rights Radar report
        custody_days: days in custody (None when unknown)
        missing_docs: documents still missing

    Returns:
        A sortable key; smaller is more urgent. Layout: (no deadline?, deadline kind, days left, -days past, -custody, has missing docs).
    """
    return assess(rights, custody_days, missing_docs).key


def parse_reasons(reasons: list[str]) -> dict[str, int]:
    """Read the codes and days back out of a card's reason texts (code -> days)."""
    found: dict[str, int] = {}
    for text in reasons:
        for code, pattern in _PARSE.items():
            if (m := pattern.search(text)) and code not in found:
                found[code] = int(m.group(1))
    return found


def card_key(card: TriageCard) -> tuple:
    """The urgency key of a card, rebuilt from its reasons and missing documents (same layout as `urgency_key`)."""
    found = parse_reasons(card.reasons)
    present = [c for c in SUB_ORDER if c in found]
    sub = min((SUB_ORDER[c] for c in present), default=_NO_DEADLINE)
    left = found.get(CODE_DEFAULT_BAIL_SOON, 0) if sub == SUB_ORDER[CODE_DEFAULT_BAIL_SOON] else 0
    past = max(found.get(c, 0) for c in (CODE_DEFAULT_BAIL_OPEN, CODE_DEFAULT_BAIL_CLOSED, CODE_S479_CROSSED))
    return (0 if present else 1, sub, left, -past, -found.get(CODE_CUSTODY, 0), 1 if card.missing_docs else 0)


def rank(cards: list[TriageCard]) -> list[TriageCard]:
    """Order cards by the urgency rule and assign urgency_rank (1 = most urgent).

    Args:
        cards: the cards (not modified)

    Returns:
        Copies of the cards in order with urgency_rank set; fully equal keys are ordered by case id, so the result is
        deterministic and ranking a ranked list changes nothing.
    """
    ordered = sorted(cards, key=lambda c: (*card_key(c), c.case_id))
    return [c.model_copy(update={"urgency_rank": i}) for i, c in enumerate(ordered, start=1)]
