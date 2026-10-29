"""Rights Radar engine (plan §7.3, §7.4): all seven rules over dossier + timeline, and the clock.

Case-0007 as of 2025-02-03 must reproduce the RightsReport printed in plan §7.3 (statuses, order, `uses`, rule strings).
"""

from datetime import date, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vakeel_sahayak.rights.acts import special_default_bail_limit
from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.engine import RightsEngine
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.antil_category import AntilCategoryRule
from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
from vakeel_sahayak.rights.rules.grounds_of_arrest import GroundsOfArrestRule
from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
from vakeel_sahayak.rights.rules.production_24h import Production24hRule
from vakeel_sahayak.rights.rules.statutory_bar import StatutoryBarRule
from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport

ALL_RULES = [
    DefaultBailRule, UndertrialLimitRule, NoticeOfAppearanceRule, GroundsOfArrestRule, Production24hRule,
    AntilCategoryRule, StatutoryBarRule,
]
PLAN_ORDER = [
    "default_bail", "undertrial_limit", "notice_of_appearance", "grounds_of_arrest", "production_24h",
    "antil_category", "statutory_bar",
]


# ------------------------------------------------------------------ pass-today structural checks
def test_seven_rules_cover_the_seven_checks():
    """One rule class per Rights Radar check, ids unique, all subclasses of Rule."""
    ids = [r.rule_id for r in ALL_RULES]
    assert sorted(i.value for i in ids) == sorted(PLAN_ORDER)
    assert len(set(ids)) == 7
    assert all(issubclass(r, Rule) for r in ALL_RULES)


@pytest.mark.parametrize("cls", ALL_RULES, ids=lambda c: c.__name__)
def test_every_rule_has_text_sources_and_last_verified_slot(cls):
    """Plan §7.3 'Transparency/Testing': each rule has rule text, sources and a 'last verified' field."""
    assert cls.rule_text.strip()
    assert cls.sources and all(s.strip() for s in cls.sources)
    assert hasattr(cls, "last_verified")  # None until the week-0 check against the bare act sets the date
    assert cls.allowed_statuses and all(isinstance(s, RightsStatus) for s in cls.allowed_statuses)


def test_rules_yaml_agrees_with_rule_classes(load_yaml):
    """configs/rights_rules.yaml statuses and sources equal the rule classes' (single source of truth check)."""
    cfg = load_yaml("rights_rules.yaml")
    for cls in ALL_RULES:
        entry = cfg[cls.rule_id.value]
        assert set(entry["statuses"]) == {s.value for s in cls.allowed_statuses}, cls.__name__
        assert entry["sources"], cls.__name__


# ------------------------------------------------------------------ engine behaviour (fail until implemented)
def test_default_engine_has_seven_rules():
    """RightsEngine() defaults to the seven rules of rights/rules."""
    engine = RightsEngine()
    assert len(engine.rules) == 7  # ASSUMPTION: rules are exposed as `.rules`


def test_build_inputs_for_case_0007(dossier, timeline):
    """Inputs derived from the case-0007 dossier and timeline."""
    inputs = RightsEngine().build_inputs(dossier, timeline, "2025-02-03")
    assert inputs.as_of == "2025-02-03"
    assert inputs.first_remand == "2024-08-21"
    assert inputs.charge_sheet_filed is True and inputs.charge_sheet_date == "2024-11-02"
    assert inputs.arrest_date == "2024-08-20"
    assert inputs.max_punishment == "7 years"
    assert any("318(4)" in s for s in inputs.sections)
    assert inputs.custody_days == 167
    assert inputs.antecedents_known is False  # antecedents field is UNSUPPORTED
    assert inputs.production_date == "2024-08-21"  # ASSUMPTION: first remand date is the production date on record
    assert inputs.arrest_time is None and inputs.production_time is None
    assert inputs.special_act is None


def test_run_reproduces_the_plan_report(dossier, timeline, expected_rights_report):
    """Plan §7.3: seven checks in the plan's order with the plan's statuses for case-0007 as of 2025-02-03."""
    report = RightsEngine().run(dossier, timeline, "2025-02-03")
    assert isinstance(report, RightsReport)
    assert report.case_id == "case-0007" and report.as_of == "2025-02-03"
    assert [c.check.value for c in report.checks] == PLAN_ORDER
    assert {c.check.value: c.status for c in report.checks} == {
        c.check.value: c.status for c in expected_rights_report.checks
    }


def test_run_results_show_rule_source_and_dates(dossier, timeline, expected_rights_report):
    """Every output shows the rule, its source and the inputs it used (transparency)."""
    report = RightsEngine().run(dossier, timeline, "2025-02-03")
    expected = {c.check: c for c in expected_rights_report.checks}
    for c in report.checks:
        assert c.rule, c.check
        if expected[c.check].detail:  # the plan's statutory_bar entry has a rule but no detail text
            assert c.detail, c.check
        if expected[c.check].uses:
            assert set(expected[c.check].uses) <= set(c.uses), c.check


def test_clock_custody_grows_daily(dossier, timeline):
    """The radar runs on a clock: a day later custody is 168 days."""
    r1 = RightsEngine().run(dossier, timeline, "2025-02-03")
    r2 = RightsEngine().run(dossier, timeline, "2025-02-04")
    d1 = next(c for c in r1.checks if c.check == RightsCheckName.UNDERTRIAL_LIMIT).detail
    d2 = next(c for c in r2.checks if c.check == RightsCheckName.UNDERTRIAL_LIMIT).detail
    assert "167" in d1 and "168" in d2


def _report(case_id: str, as_of: str, **statuses: RightsStatus) -> RightsReport:
    return RightsReport(
        case_id=case_id, as_of=as_of,
        checks=[RightsCheckResult(check=RightsCheckName(k), status=v) for k, v in statuses.items()],
    )


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ({"undertrial_limit": RightsStatus.NOT_YET}, {"undertrial_limit": RightsStatus.ELIGIBLE}, ["undertrial_limit"]),
        ({"default_bail": RightsStatus.NOT_YET}, {"default_bail": RightsStatus.ELIGIBLE}, ["default_bail"]),
        ({"default_bail": RightsStatus.ELIGIBLE}, {"default_bail": RightsStatus.WINDOW_CLOSED}, ["default_bail"]),
        ({"undertrial_limit": RightsStatus.CHECK}, {"undertrial_limit": RightsStatus.CHECK}, []),
        ({"undertrial_limit": RightsStatus.ELIGIBLE}, {"undertrial_limit": RightsStatus.ELIGIBLE}, []),
        ({"production_24h": RightsStatus.CHECK}, {"production_24h": RightsStatus.CHECK}, []),
    ],
)
def test_clock_crossings(before, after, expected):
    """A threshold crossing (e.g. the s.479 date) between two runs creates a change; unchanged statuses do not."""
    prev, cur = _report("c", "2025-02-03", **before), _report("c", "2025-02-04", **after)
    assert RightsEngine().clock_crossings(prev, cur) == expected


def test_clock_crossing_at_the_sixty_day_boundary(timeline, dossier):
    """Real runs a day apart around day 60/61 of a case with no charge sheet cross 'default_bail' exactly once."""
    d = dossier.model_copy(deep=True)
    d.fields.charge_sheet.value = None  # no charge sheet filed yet
    tl = [e for e in timeline if e.label != "Charge sheet filed"]
    engine = RightsEngine()
    day60, day61, day62 = "2024-10-19", "2024-10-20", "2024-10-21"
    r60, r61, r62 = (engine.run(d, tl, x) for x in (day60, day61, day62))
    assert engine.clock_crossings(r60, r61) == ["default_bail"]
    assert engine.clock_crossings(r61, r62) == []


# ------------------------------------------------------------------ invariants over random inputs
@st.composite
def rule_inputs(draw):
    first = draw(st.dates(min_value=date(2022, 1, 1), max_value=date(2025, 6, 1)))
    as_of = first + timedelta(days=draw(st.integers(0, 1500)))
    cs = draw(st.one_of(st.none(), st.integers(1, 400)))
    return RuleInputs(
        as_of=as_of.isoformat(),
        first_remand=first.isoformat() if draw(st.booleans()) else None,
        charge_sheet_filed=None if cs is None else True,
        charge_sheet_date=None if cs is None else (first + timedelta(days=cs - 1)).isoformat(),
        arrest_date=(first - timedelta(days=1)).isoformat(),
        production_date=draw(st.one_of(st.none(), st.just(first.isoformat()))),
        max_punishment=draw(st.sampled_from(["7 years", "3 years", "life", "death", "may extend to ten years", "10 years"])),
        sections=draw(st.sampled_from([[], ["BNS 318(4)"], ["BNS 103"]])),
        custody_days=draw(st.one_of(st.none(), st.integers(0, 3000))),
        antecedents_known=draw(st.booleans()),
        first_time_offender=draw(st.sampled_from([None, True, False])),
        special_act=draw(st.sampled_from([None, "NDPS", "UAPA", "PMLA"])),
        arrest_memo_present=draw(st.sampled_from([None, True, False])),
        grounds_communicated=draw(st.sampled_from([None, True, False])),
    )


@pytest.mark.parametrize("cls", ALL_RULES, ids=lambda c: c.__name__)
@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(inputs=rule_inputs())
def test_property_status_always_in_allowed_set(cls, inputs):
    """Whatever the inputs, a rule returns one of its allowed statuses, names its own check, and carries its rule text."""
    rule = cls()
    res = rule.evaluate(inputs)
    assert res.status in rule.allowed_statuses
    assert res.check == rule.rule_id
    assert res.rule
    assert res.last_verified == rule.last_verified


@settings(max_examples=60)
@given(inputs=rule_inputs())
def test_property_no_false_eligible_when_law_is_unsettled(inputs):
    """'May extend to ten years' never yields ELIGIBLE for default bail (unsettled -> CHECK, plan §7.3)."""
    special = special_default_bail_limit(inputs)
    # RECONCILED: a certain special-act limit (UAPA s.43D(2), NDPS s.36A(4); rights-fixes.md) replaces the 60/90-day
    # choice, so the 'ten years' question is not reached and an accrued right is correctly ELIGIBLE.
    if inputs.max_punishment == "may extend to ten years" and not (special is not None and special.certain):
        assert DefaultBailRule().evaluate(inputs).status != RightsStatus.ELIGIBLE
