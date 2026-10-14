"""`date_calc` tool (plan §5.1 case.timeline row, §7.1, Appendix C): deterministic day counting.

Case-0007: custody from the arrest (2024-08-20) to the as-of date (2025-02-03) is 167 days; with the first remand
(2024-08-21) as day 1 the charge sheet (2024-11-02) is day 74.
"""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.tools_law_case._helpers import assert_tool_error
from vakeel_sahayak.rights.day_count import DateRule
from vakeel_sahayak.tools.case.dates import DATE_CALC_SPEC, date_calc
from vakeel_sahayak.tools.types import DateCalcResult


def test_spec_is_readable_by_peshkar_sutradhar_vakeel_over_the_timeline_store():
    """ToolSpec facts (plan §3.2, §5.1)."""
    assert {a.value for a in DATE_CALC_SPEC.agents} == {"PESHKAR", "SUTRADHAR", "VAKEEL"}
    assert [s.value for s in DATE_CALC_SPEC.stores] == ["case.timeline"]
    assert DATE_CALC_SPEC.gated is False


def test_custody_days_case_0007():
    """167 days in custody (calendar days between arrest and as-of)."""
    res = date_calc("2024-08-20", "2025-02-03", rule=DateRule.CALENDAR_DAYS_BETWEEN.value)
    assert isinstance(res, DateCalcResult)
    assert res.value == 167
    assert (res.start, res.end) == ("2024-08-20", "2025-02-03")
    assert res.rule  # the rule used is reported back


def test_default_rule_counts_the_first_remand_as_day_1():
    """The default rule gives the charge-sheet day number: 74."""
    assert date_calc("2024-08-21", "2024-11-02").value == 74


def test_rule_name_is_case_insensitive():
    """The skeleton's default is the lowercase 'inclusive_day_1' while the enum values are upper case: accept both."""
    assert date_calc("2024-08-21", "2024-11-02", rule="inclusive_day_1").value == 74
    assert date_calc("2024-08-21", "2024-11-02", rule="INCLUSIVE_DAY_1").value == 74


@pytest.mark.parametrize(("start", "end", "day"), [("2024-08-21", "2024-10-19", 60), ("2024-08-21", "2024-10-20", 61)])
def test_sixty_day_window_boundary(start, end, day):
    """Day 60 and day 61 of the default-bail window."""
    assert date_calc(start, end).value == day


@pytest.mark.parametrize("bad", [("2024-13-45", "2025-01-01"), ("2024-08-20", "03/02/2025"), ("", "2025-01-01")])
def test_malformed_date_is_an_error_not_a_guess(bad):
    """Plan §15.8 recovery from injected errors: a malformed date raises/returns a ToolError."""
    assert_tool_error(lambda: date_calc(*bad))


def test_unknown_rule_is_rejected():
    """An unknown counting rule is an error."""
    assert_tool_error(lambda: date_calc("2024-08-20", "2025-02-03", rule="lunar_months"))


@given(a=st.dates(min_value=date(2019, 1, 1), max_value=date(2030, 12, 31)), n=st.integers(0, 2000))
def test_property_inclusive_is_calendar_plus_one(a, n):
    """INCLUSIVE_DAY_1 = CALENDAR_DAYS_BETWEEN + 1 for every start <= end."""
    b = a + timedelta(days=n)
    cal = date_calc(a.isoformat(), b.isoformat(), rule=DateRule.CALENDAR_DAYS_BETWEEN.value).value
    inc = date_calc(a.isoformat(), b.isoformat(), rule=DateRule.INCLUSIVE_DAY_1.value).value
    assert cal == n and inc == n + 1
