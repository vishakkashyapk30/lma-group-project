"""Rights Radar: undertrial limit, BNSS s.479 / CrPC s.436A (plan §7.3 row 2, Appendix C row 2).

Rule as coded: release on bond after half the maximum sentence, or one-third for a first-time offender; not applicable
to offences punishable with death or life imprisonment. Maximum 7 years = 2,555 days -> one-third = 852 days (rounded up),
one-half = 1,278 days (rounded up). Case-0007: 167 days in custody, antecedents unknown -> CHECK.
"""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.rights._helpers import iso, mentions_date, number_in
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus

rule = UndertrialLimitRule()
ARREST = date(2024, 8, 20)


def inputs(custody: int, max_punishment: str = "7 years", first_time: bool | None = None, known: bool = True):
    return RuleInputs(
        as_of=iso(ARREST + timedelta(days=custody)),
        arrest_date=iso(ARREST),
        custody_days=custody,
        max_punishment=max_punishment,
        antecedents_known=known,
        first_time_offender=first_time,
    )


def test_rule_metadata():
    """Rule id, statuses, sources."""
    assert rule.rule_id == RightsCheckName.UNDERTRIAL_LIMIT
    assert set(rule.allowed_statuses) == {
        RightsStatus.ELIGIBLE, RightsStatus.NOT_YET, RightsStatus.NOT_APPLICABLE, RightsStatus.CHECK
    }
    assert "479" in " ".join(rule.sources) and "436A" in " ".join(rule.sources)


def test_case_0007_antecedents_unknown_is_check(rule_inputs_0007):
    """Plan §7.3: 167 days, thresholds 852 (first-time, 1/3 of 7 years) and 1,278 (1/2), antecedents unknown -> CHECK."""
    res = rule.evaluate(rule_inputs_0007)
    assert res.status == RightsStatus.CHECK
    d = res.detail or ""
    assert number_in(d, 167)
    assert number_in(d, 852) and number_in(d, 1278)
    assert "antecedent" in d.lower()
    assert {"custody_days", "sections", "antecedents"} <= set(res.uses)
    assert "479" in (res.rule or "")


@pytest.mark.parametrize(
    ("custody", "first_time", "expected"),
    [
        (851, True, RightsStatus.NOT_YET),
        (852, True, RightsStatus.ELIGIBLE),  # one-third of 7 years = 852 days
        (853, True, RightsStatus.ELIGIBLE),
        (1277, False, RightsStatus.NOT_YET),
        (1278, False, RightsStatus.ELIGIBLE),  # one-half of 7 years = 1,278 days
        (852, False, RightsStatus.NOT_YET),  # a repeat offender needs the half, not the third
        (167, True, RightsStatus.NOT_YET),
    ],
)
def test_thresholds_852_and_1278(custody, first_time, expected):
    """479 thresholds for a 7-year offence: 852 days (first-time) and 1,278 days (otherwise)."""
    assert rule.evaluate(inputs(custody, first_time=first_time)).status == expected


@pytest.mark.parametrize(
    ("custody", "expected"),
    [
        (167, RightsStatus.CHECK),  # the plan's own example
        (900, RightsStatus.CHECK),  # between the two thresholds: depends on antecedents we do not have
        (1278, RightsStatus.CHECK),  # RECONCILED: docs/qa/rights-verification.md: unknown antecedents also mean unknown pending cases (s.479(2)), so never ELIGIBLE
    ],
)
def test_unknown_antecedents_never_gives_a_false_eligible(custody, expected):
    """Without antecedents the radar returns CHECK rather than a verdict, except where both thresholds are met."""
    res = rule.evaluate(inputs(custody, first_time=None, known=False))
    assert res.status == expected


def test_not_yet_reports_the_date_the_threshold_is_reached():
    """NOT_YET (date): first-time offender, 167 days in -> 852 days reached on 2026-12-20 (arrest + 852 days)."""
    res = rule.evaluate(inputs(167, first_time=True))
    assert res.status == RightsStatus.NOT_YET
    assert mentions_date(res.detail or "", "2026-12-20")  # ASSUMPTION: ISO or dd.mm.yyyy
    res2 = rule.evaluate(inputs(167, first_time=False))
    assert mentions_date(res2.detail or "", "2028-02-19")  # arrest + 1,278 days


@pytest.mark.parametrize("punishment", ["death", "life", "imprisonment for life", "death or imprisonment for life"])
@pytest.mark.parametrize("custody", [10, 5000])
def test_death_or_life_is_not_applicable(punishment, custody):
    """Not for offences punishable with death or life imprisonment, however long the custody."""
    assert rule.evaluate(inputs(custody, punishment, first_time=True)).status == RightsStatus.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("punishment", "third", "half"),
    [("3 years", 365, 548), ("5 years", 609, 913), ("7 years", 852, 1278), ("10 years", 1217, 1825)],
)
def test_threshold_scales_with_the_maximum_sentence(punishment, third, half):
    """ceil(years*365/3) and ceil(years*365/2) are the thresholds (7 years -> 852 / 1,278 as in the plan)."""
    # ASSUMPTION: fractions are rounded UP (custody must be at least one-third / one-half); the plan's 852 and 1,278 are
    # consistent with this, and 5 years (609 vs 608) pins it down.
    assert rule.evaluate(inputs(third, punishment, first_time=True)).status == RightsStatus.ELIGIBLE
    assert rule.evaluate(inputs(third - 1, punishment, first_time=True)).status == RightsStatus.NOT_YET
    assert rule.evaluate(inputs(half, punishment, first_time=False)).status == RightsStatus.ELIGIBLE
    assert rule.evaluate(inputs(half - 1, punishment, first_time=False)).status == RightsStatus.NOT_YET


@given(custody=st.integers(min_value=0, max_value=3000), first_time=st.booleans())
def test_property_eligible_iff_threshold_met(custody, first_time):
    """For a 7-year offence the status flips exactly at the threshold (monotone in custody days)."""
    threshold = 852 if first_time else 1278
    status = rule.evaluate(inputs(custody, first_time=first_time)).status
    assert status == (RightsStatus.ELIGIBLE if custody >= threshold else RightsStatus.NOT_YET)


@given(first_time=st.booleans(), a=st.integers(0, 3000), b=st.integers(0, 3000))
def test_property_more_custody_never_loses_eligibility(first_time, a, b):
    """Monotonicity: if eligible at a days, eligible at any larger b."""
    lo, hi = sorted((a, b))
    if rule.evaluate(inputs(lo, first_time=first_time)).status == RightsStatus.ELIGIBLE:
        assert rule.evaluate(inputs(hi, first_time=first_time)).status == RightsStatus.ELIGIBLE
