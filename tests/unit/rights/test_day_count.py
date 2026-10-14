"""Day counting for Rights Radar and `date_calc` (plan §7.3, Appendix C: first remand is day 1; custody 167 days).

Case-0007: first remand 2024-08-21 is day 1, so the charge sheet of 2024-11-02 is day 74; custody from the arrest
(2024-08-20) to the as-of date (2025-02-03) is 167 calendar days.
"""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vakeel_sahayak.rights.day_count import DateRule, add_days, count_days

DATES = st.dates(min_value=date(2019, 1, 1), max_value=date(2031, 12, 31))


def test_date_rule_members():
    """The three counting rules named in the skeleton exist."""
    assert {r.name for r in DateRule} == {"INCLUSIVE_DAY_1", "EXCLUSIVE", "CALENDAR_DAYS_BETWEEN"}


@pytest.mark.parametrize(
    ("start", "end", "rule", "expected"),
    [
        ("2024-08-21", "2024-11-02", DateRule.INCLUSIVE_DAY_1, 74),  # plan §7.3: charge sheet on day 74
        ("2024-08-21", "2024-08-21", DateRule.INCLUSIVE_DAY_1, 1),  # first remand itself is day 1
        ("2024-08-21", "2024-10-19", DateRule.INCLUSIVE_DAY_1, 60),  # last day of the 60-day window
        ("2024-08-21", "2024-10-20", DateRule.INCLUSIVE_DAY_1, 61),  # first day default bail is available
        ("2024-08-20", "2025-02-03", DateRule.CALENDAR_DAYS_BETWEEN, 167),  # plan §7.1 custody_days
        ("2024-08-20", "2024-08-20", DateRule.CALENDAR_DAYS_BETWEEN, 0),
        ("2024-02-28", "2024-03-01", DateRule.CALENDAR_DAYS_BETWEEN, 2),  # 2024 is a leap year
        ("2023-02-28", "2023-03-01", DateRule.CALENDAR_DAYS_BETWEEN, 1),
        ("2024-12-31", "2025-01-01", DateRule.CALENDAR_DAYS_BETWEEN, 1),  # year boundary
    ],
)
def test_count_days_table(start, end, rule, expected):
    """count_days matches hand-computed values for each rule."""
    assert count_days(start, end, rule) == expected


def test_default_rule_is_inclusive_day_1():
    """The default counting rule is 'first remand is day 1'."""
    assert count_days("2024-08-21", "2024-11-02") == 74


@given(a=DATES, n=st.integers(min_value=0, max_value=1500))
def test_inclusive_is_exclusive_plus_one(a, n):
    """Counting the start day as day 1 always gives exactly one more than the calendar difference."""
    b = a + timedelta(days=n)
    assert count_days(a.isoformat(), b.isoformat(), DateRule.INCLUSIVE_DAY_1) == n + 1
    assert count_days(a.isoformat(), b.isoformat(), DateRule.CALENDAR_DAYS_BETWEEN) == n
    # ASSUMPTION: EXCLUSIVE excludes the start day and includes the end day, i.e. equals the calendar difference.
    assert count_days(a.isoformat(), b.isoformat(), DateRule.EXCLUSIVE) == count_days(
        a.isoformat(), b.isoformat(), DateRule.INCLUSIVE_DAY_1
    ) - 1


@pytest.mark.parametrize(
    ("days", "rule", "expected"),
    [
        (60, DateRule.INCLUSIVE_DAY_1, "2024-10-19"),  # day 60 when 2024-08-21 is day 1
        (90, DateRule.INCLUSIVE_DAY_1, "2024-11-18"),
        (1, DateRule.INCLUSIVE_DAY_1, "2024-08-21"),
        (60, DateRule.CALENDAR_DAYS_BETWEEN, "2024-10-20"),
    ],
)
def test_add_days_table(days, rule, expected):
    """add_days returns the date on which an N-day window ends."""
    assert add_days("2024-08-21", days, rule) == expected


@given(a=DATES, n=st.integers(min_value=1, max_value=900), rule=st.sampled_from(list(DateRule)))
def test_add_days_inverts_count_days(a, n, rule):
    """count_days(start, add_days(start, n)) == n under every rule (round trip)."""
    end = add_days(a.isoformat(), n, rule)
    assert count_days(a.isoformat(), end, rule) == n


@pytest.mark.parametrize("bad", ["2024-13-45", "21.08.2024", "", "not-a-date"])
def test_malformed_dates_are_rejected(bad):
    """A malformed date raises ValueError (tool-error recovery, plan §15.8) instead of returning a number."""
    with pytest.raises(ValueError):
        count_days(bad, "2024-11-02")
