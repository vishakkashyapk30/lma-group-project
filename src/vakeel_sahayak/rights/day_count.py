"""Day-counting helpers shared by date_calc and the rules (plan §7.3, Appendix C)."""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum


class DateRule(str, Enum):
    """Counting rules for date_calc."""

    INCLUSIVE_DAY_1 = "INCLUSIVE_DAY_1"  # the start date is day 1 (default bail: first remand = day 1)
    EXCLUSIVE = "EXCLUSIVE"  # the start date is day 0: days elapsed since start
    CALENDAR_DAYS_BETWEEN = "CALENDAR_DAYS_BETWEEN"  # the calendar difference end - start (arrest to as-of: 167 days)


def parse_date(value: str) -> date:
    """Parse an ISO date 'YYYY-MM-DD'.

    Raises:
        ValueError: for anything else, including date-times and malformed or impossible dates.
    """
    try:
        if len(value) != 10:
            raise ValueError
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"not an ISO date (YYYY-MM-DD): {value!r}") from exc


def format_dmy(value: str) -> str:
    """Render an ISO date as dd.mm.yyyy, the style of Indian court records (plan §7.3 example)."""
    d = parse_date(value)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def count_days(start: str, end: str, rule: DateRule = DateRule.INCLUSIVE_DAY_1) -> int:
    """Count days between two dates under a rule.

    With INCLUSIVE_DAY_1, `start` is day 1, so the count on `end` is the day number of `end` (ED v. Kapil Wadhawan).

    Args:
        start: ISO date
        end: ISO date
        rule: e.g. first remand is day 1 (ED v. Kapil Wadhawan)

    Returns:
        Day count.

    Raises:
        ValueError: if either date is malformed or `end` is before `start`.
    """
    s, e = parse_date(start), parse_date(end)
    if e < s:
        raise ValueError(f"end {end} is before start {start}")
    delta = (e - s).days
    rule = DateRule(rule)
    if rule == DateRule.INCLUSIVE_DAY_1:
        return delta + 1
    return delta  # EXCLUSIVE and CALENDAR_DAYS_BETWEEN: the calendar difference, counted from the start day's end


def add_days(start: str, days: int, rule: DateRule = DateRule.INCLUSIVE_DAY_1) -> str:
    """Date on which a window of N days ends (e.g. day 60 or 90 of default bail).

    With INCLUSIVE_DAY_1 the result is day N (start is day 1); with the other rules it is start + N days.

    Args:
        start: see behaviour
        days: see behaviour
        rule: see behaviour

    Returns:
        ISO date.
    """
    offset = days - 1 if DateRule(rule) == DateRule.INCLUSIVE_DAY_1 else days
    return (parse_date(start) + timedelta(days=offset)).isoformat()
