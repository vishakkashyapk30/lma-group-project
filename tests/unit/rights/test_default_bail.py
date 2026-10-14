"""Rights Radar: default bail, BNSS s.187(3) / CrPC s.167(2) (plan §7.3 table row 1, Appendix C row 1).

Rule as coded: release if no charge sheet within 90 days (death, life, or 10 years or more) or 60 days (other
offences), counted from the first remand with that day as day 1. The right lapses if the charge sheet is filed before an
application is made. 'May extend to ten years' returns CHECK.

Case-0007: first remand 2024-08-21 (day 1), charge sheet 2024-11-02 = day 74, 60-day limit (maximum 7 years), so default
bail was available on days 61-73 -> WINDOW_CLOSED.
"""

import re
from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.rights._helpers import day_n, default_bail_inputs, iso, mentions_date
from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus

FR = date(2024, 8, 21)  # first remand of case-0007 = day 1
rule = DefaultBailRule()


def test_rule_metadata():
    """Rule id, statuses and sources match plan §7.3 and Appendix C."""
    assert rule.rule_id == RightsCheckName.DEFAULT_BAIL
    assert set(rule.allowed_statuses) == {
        RightsStatus.ELIGIBLE, RightsStatus.NOT_YET, RightsStatus.WINDOW_CLOSED, RightsStatus.CHECK
    }
    joined = " ".join(rule.sources)
    assert "187(3)" in joined and "167(2)" in joined
    assert "Kapil Wadhawan" in joined and "Ravindran" in joined
    assert "60" in rule.rule_text and "90" in rule.rule_text


def test_case_0007_is_window_closed(rule_inputs_0007):
    """Plan §7.3 worked example: WINDOW_CLOSED, 60-day limit, day 1 = first remand, charge sheet on day 74, days 61-73."""
    res = rule.evaluate(rule_inputs_0007)
    assert res.check == RightsCheckName.DEFAULT_BAIL
    assert res.status == RightsStatus.WINDOW_CLOSED
    d = res.detail or ""
    assert re.search(r"\b60\b", d), "states the 60-day limit"
    assert mentions_date(d, "2024-08-21"), "names the first remand as day 1"
    assert re.search(r"day\s*74", d, re.I), "charge sheet was filed on day 74"
    assert mentions_date(d, "2024-11-02")
    assert re.search(r"61\s*[-–to ]+\s*73", d), "default bail was available on days 61-73"
    assert {"first_remand", "charge_sheet", "sections"} <= set(res.uses)
    assert "187(3)" in (res.rule or "")


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (59, RightsStatus.NOT_YET),
        (60, RightsStatus.NOT_YET),  # day 60 is the last day the police may still file
        (61, RightsStatus.ELIGIBLE),  # the right accrues on day 61 when no charge sheet is filed
    ],
)
def test_sixty_day_boundary_no_charge_sheet(day, expected):
    """60-day offence, no charge sheet: day 59 and 60 NOT_YET, day 61 ELIGIBLE."""
    inputs = default_bail_inputs(FR, day_n(FR, day), "7 years")
    assert rule.evaluate(inputs).status == expected


@pytest.mark.parametrize(
    ("max_punishment", "day", "expected"),
    [
        ("life", 89, RightsStatus.NOT_YET),
        ("life", 90, RightsStatus.NOT_YET),
        ("life", 91, RightsStatus.ELIGIBLE),
        ("death", 90, RightsStatus.NOT_YET),
        ("death", 91, RightsStatus.ELIGIBLE),
        ("imprisonment for life", 91, RightsStatus.ELIGIBLE),
        ("not less than 10 years", 90, RightsStatus.NOT_YET),  # ASSUMPTION: '10 years or more' wording -> 90 days
        ("not less than 10 years", 91, RightsStatus.ELIGIBLE),
        ("3 years", 61, RightsStatus.ELIGIBLE),
        ("3 years", 60, RightsStatus.NOT_YET),
    ],
)
def test_sixty_vs_ninety_day_limit(max_punishment, day, expected):
    """Death, life and 10-years-or-more offences get 90 days; other offences get 60."""
    inputs = default_bail_inputs(FR, day_n(FR, day), max_punishment)
    assert rule.evaluate(inputs).status == expected


def test_not_yet_reports_days_left():
    """NOT_YET shows the days left (plan §7.3 'NOT_YET (days left)')."""
    res = rule.evaluate(default_bail_inputs(FR, day_n(FR, 50), "7 years"))
    # ASSUMPTION: 'days left' is 10 (to day 60) or 11 (to the first eligible day 61); either is accepted.
    assert re.search(r"\b(10|11)\b", res.detail or "")


@pytest.mark.parametrize("text", ["imprisonment which may extend to ten years", "may extend to 10 years"])
def test_may_extend_to_ten_years_is_check(text):
    """Appendix C: 'may extend to ten years' returns CHECK (unsettled which limit applies), never ELIGIBLE."""
    res = rule.evaluate(default_bail_inputs(FR, day_n(FR, 75), text))
    assert res.status == RightsStatus.CHECK


def test_missing_first_remand_is_check():
    """Without a first-remand date the rule cannot count: CHECK."""
    inputs = default_bail_inputs(FR, date(2025, 2, 3), "7 years")
    inputs = inputs.model_copy(update={"first_remand": None})
    assert rule.evaluate(inputs).status == RightsStatus.CHECK


@pytest.mark.parametrize("filed_day", [30, 59, 60])
def test_charge_sheet_in_time_means_no_default_bail(filed_day):
    """A charge sheet filed within the limit means default bail never accrued."""
    inputs = default_bail_inputs(FR, date(2025, 2, 3), "7 years", charge_sheet=day_n(FR, filed_day))
    # ASSUMPTION: with the allowed outputs {ELIGIBLE, NOT_YET, WINDOW_CLOSED, CHECK}, an in-time filing is WINDOW_CLOSED.
    assert rule.evaluate(inputs).status == RightsStatus.WINDOW_CLOSED


def test_application_made_before_charge_sheet_keeps_right():
    """The right does not lapse when an application was made (day 65) before the charge sheet (day 74)."""
    inputs = default_bail_inputs(FR, date(2025, 2, 3), "7 years", charge_sheet=day_n(FR, 74), application=day_n(FR, 65))
    assert rule.evaluate(inputs).status == RightsStatus.ELIGIBLE


def test_application_after_charge_sheet_is_too_late():
    """An application made after the charge sheet (day 80 > day 74) does not revive the right (M. Ravindran)."""
    inputs = default_bail_inputs(FR, date(2025, 2, 3), "7 years", charge_sheet=day_n(FR, 74), application=day_n(FR, 80))
    assert rule.evaluate(inputs).status == RightsStatus.WINDOW_CLOSED


@given(
    first_remand=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 6, 30)),
    day=st.integers(min_value=1, max_value=200),
    case=st.sampled_from([(60, "7 years"), (60, "3 years"), (90, "life"), (90, "death")]),
)
def test_property_boundary_without_charge_sheet(first_remand, day, case):
    """For any first-remand date: NOT_YET up to and including day limit, ELIGIBLE from day limit+1."""
    limit, punishment = case
    inputs = default_bail_inputs(first_remand, day_n(first_remand, day), punishment)
    expected = RightsStatus.NOT_YET if day <= limit else RightsStatus.ELIGIBLE
    assert rule.evaluate(inputs).status == expected


@given(
    first_remand=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 6, 30)),
    filed_day=st.integers(min_value=62, max_value=400),
)
def test_property_late_charge_sheet_closes_the_window(first_remand, filed_day):
    """A charge sheet filed after day limit+1 (no application) -> WINDOW_CLOSED, never ELIGIBLE."""
    as_of = day_n(first_remand, filed_day) + timedelta(days=5)
    inputs = default_bail_inputs(first_remand, as_of, "7 years", charge_sheet=day_n(first_remand, filed_day))
    res = rule.evaluate(inputs)
    assert res.status == RightsStatus.WINDOW_CLOSED
    assert res.status != RightsStatus.ELIGIBLE


@given(shift=st.integers(min_value=-5, max_value=5))
def test_property_day_count_is_shift_invariant(shift):
    """Moving first remand and as-of by the same number of days never changes the status."""
    base = default_bail_inputs(FR, day_n(FR, 61), "7 years")
    moved = default_bail_inputs(FR + timedelta(days=shift), day_n(FR, 61) + timedelta(days=shift), "7 years")
    assert rule.evaluate(base).status == rule.evaluate(moved).status


def test_result_carries_rule_text_source_and_dates(rule_inputs_0007):
    """Plan §7.3 transparency: every output shows its rule, source and the dates it used."""
    res = rule.evaluate(rule_inputs_0007)
    assert res.rule and res.uses
    assert res.last_verified == rule.last_verified
    assert iso(FR) in (res.detail or "") or mentions_date(res.detail or "", iso(FR))
