"""Fixes after the check of the rule texts against the bare acts (docs/qa/rights-verification.md, HA-03): the five reproduced wrong inputs,
special-act limits, s.479(2), the Antil list, the narrowed statutory bar and the grounds-of-arrest CHECK."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from vakeel_sahayak.rights.acts import begun_after_bnss, parse_section, special_default_bail_limit
from vakeel_sahayak.rights.engine import default_rules
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.antil_category import AntilCategoryRule
from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
from vakeel_sahayak.rights.rules.grounds_of_arrest import GroundsOfArrestRule
from vakeel_sahayak.rights.rules.statutory_bar import StatutoryBarRule
from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule
from vakeel_sahayak.schemas.enums import RightsStatus as S

REMAND = date(2025, 3, 1)


def db(day: int, sections: list[str], punishment: str, cs_day: int | None = None, app_day: int | None = None, filed: bool | None = False):
    as_of = REMAND + timedelta(days=day - 1)
    return DefaultBailRule().evaluate(
        RuleInputs(
            as_of=as_of.isoformat(), first_remand=REMAND.isoformat(), max_punishment=punishment, sections=sections,
            charge_sheet_filed=bool(cs_day) if cs_day else filed,
            charge_sheet_date=(REMAND + timedelta(days=cs_day - 1)).isoformat() if cs_day else None,
            application_date=(REMAND + timedelta(days=app_day - 1)).isoformat() if app_day else None,
        )
    )


# 1. default bail: special-act limits -----------------------------------------------------------------------------
def test_uapa_day_62_is_not_eligible():
    assert db(62, ["UAPA 18"], "5 years").status == S.NOT_YET


def test_ndps_commercial_day_100_is_not_eligible():
    assert db(100, ["NDPS 21(c)"], "20 years").status == S.NOT_YET


@pytest.mark.parametrize(("sections", "punishment", "day", "want"), [
    (["UAPA 18"], "5 years", 90, S.NOT_YET),
    (["UAPA 18"], "5 years", 91, S.CHECK),  # the Court may extend to 180 days: was it extended?
    (["UAPA 18"], "5 years", 180, S.CHECK),
    (["UAPA 18"], "5 years", 181, S.ELIGIBLE),
    (["UAPA 18"], "may extend to ten years", 70, S.NOT_YET),  # the ten-year doubt does not arise: every UAPA offence takes 90 days
    (["NDPS 21(c)"], "20 years", 180, S.NOT_YET),
    (["NDPS 21(c)"], "20 years", 181, S.CHECK),
    (["NDPS 21(c)"], "20 years", 365, S.CHECK),
    (["NDPS 21(c)"], "20 years", 366, S.ELIGIBLE),
    (["NDPS 27A"], "10 years or more", 100, S.NOT_YET),  # s.27A takes 180 days whatever the quantity
    (["NDPS 20(b)(ii)(A)"], "1 year", 61, S.ELIGIBLE),  # small quantity: the ordinary 60 days
    (["NDPS 20(b)(ii)(A)"], "1 year", 60, S.NOT_YET),
    (["NDPS 21"], "10 years or more", 100, S.CHECK),  # quantity not on record: may be 180 days
    (["NDPS 21"], "10 years or more", 90, S.NOT_YET),
    (["IPC 420", "NDPS 21(c)"], "7 years", 100, S.NOT_YET),
    (["BNS 318(4)"], "7 years", 61, S.ELIGIBLE),  # IPC/BNS behaviour unchanged
    (["BNS 318(4)"], "7 years", 60, S.NOT_YET),
    (["BNS 103"], "life", 91, S.ELIGIBLE),
])
def test_special_act_limits(sections, punishment, day, want):
    assert db(day, sections, punishment).status == want


def test_special_limit_is_named_in_the_detail():
    d = db(62, ["UAPA 18"], "5 years").detail or ""
    assert "90-day" in d and "s.43D(2)" in d and "180" in d
    d = db(100, ["NDPS 21(c)"], "20 years").detail or ""
    assert "180-day" in d and "s.36A(4)" in d


def test_application_inside_the_extendable_period_is_check_not_eligible():
    res = db(120, ["UAPA 18"], "5 years", cs_day=121, app_day=100)
    assert res.status == S.CHECK
    assert db(120, ["BNS 318(4)"], "7 years", cs_day=121, app_day=100).status == S.ELIGIBLE  # ordinary limit as before


def test_special_act_without_punishment_still_has_a_limit():
    assert db(50, ["UAPA 18"], "").status == S.NOT_YET


def test_rule_text_says_before_the_accused_applies():
    text = DefaultBailRule.rule_text
    assert "before the accused applies" in text and "M. Ravindran" in text


# 2. undertrial limit: s.479(2) and pre-BNSS life --------------------------------------------------------------------
def ut(custody=1500, punishment="3 years", first_time=False, pending=None, known=True, **kw):
    return UndertrialLimitRule().evaluate(
        RuleInputs(as_of="2025-12-01", arrest_date="2024-08-20", custody_days=custody, max_punishment=punishment,
                   antecedents_known=known, first_time_offender=first_time, other_pending_cases=pending, **kw)
    )


def test_bns_303_with_pending_cases_is_check():
    res = ut(600, "3 years", first_time=False, pending=True)
    assert res.status == S.CHECK and "479(2)" in (res.detail or "")
    assert ut(600, "3 years", first_time=False, pending=None).status == S.ELIGIBLE
    assert ut(600, "3 years", first_time=False, pending=False).status == S.ELIGIBLE


def test_pending_cases_do_not_hide_not_yet():
    assert ut(10, "3 years", first_time=False, pending=True).status == S.NOT_YET


def test_unknown_antecedents_and_unknown_pending_is_check_even_past_half():
    assert ut(2000, "3 years", first_time=None, pending=None, known=False).status == S.CHECK
    assert ut(2000, "3 years", first_time=None, pending=False, known=False).status == S.ELIGIBLE


@pytest.mark.parametrize(("sections", "extra", "want"), [
    (["IPC 302"], {}, S.CHECK),  # CrPC s.436A covered life: unsettled for an older case
    (["BNS 103"], {"fir_date": "2023-01-01"}, S.CHECK),
    (["BNS 103"], {"arrest_date": "2024-08-20"}, S.NOT_APPLICABLE),
    ([], {"arrest_date": None, "first_remand": None}, S.CHECK),  # nothing shows the case is post-BNSS
])
def test_life_imprisonment_of_an_old_case_is_check(sections, extra, want):
    base = {"as_of": "2025-12-01", "arrest_date": "2024-08-20", "max_punishment": "life", "custody_days": 3000, "sections": sections}
    res = UndertrialLimitRule().evaluate(RuleInputs(**{**base, **extra}))
    assert res.status == want


def test_death_is_always_not_applicable():
    res = UndertrialLimitRule().evaluate(RuleInputs(as_of="2025-12-01", max_punishment="death", custody_days=9000, sections=["IPC 302"]))
    assert res.status == S.NOT_APPLICABLE


def test_begun_after_bnss():
    assert begun_after_bnss(RuleInputs(as_of="2025-01-01", sections=["IPC 420"])) is False
    assert begun_after_bnss(RuleInputs(as_of="2025-01-01", sections=["BNS 318"], arrest_date="2024-06-30")) is False
    assert begun_after_bnss(RuleInputs(as_of="2025-01-01", sections=["BNS 318"], arrest_date="2024-07-01")) is True
    assert begun_after_bnss(RuleInputs(as_of="2025-01-01")) is None


def test_rule_text_mentions_proviso_explanation_and_bail_bond_wording():
    text = UndertrialLimitRule.rule_text
    assert "Public Prosecutor" in text and "Explanation" in text and "on bail" in text and "on bond" in text and "479(2)" in text


# 3. Antil -------------------------------------------------------------------------------------------------------------
def antil(sections, punishment, special=None):
    return AntilCategoryRule().evaluate(RuleInputs(as_of="2025-01-01", sections=sections, max_punishment=punishment, special_act=special))


def test_arms_act_is_a_not_c():
    res = antil(["Arms Act 25"], "3 years", special="Arms Act")
    assert res.status == S.A and "not arrested during investigation" in (res.detail or "")


@pytest.mark.parametrize(("sections", "special"), [(["NDPS 20"], "NDPS"), (["UAPA 13"], "UAPA"), (["PMLA 4"], "PMLA"), (["Companies Act 447"], "Companies Act")])
def test_listed_acts_are_c(sections, special):
    assert antil(sections, "3 years", special).status == S.C


def test_other_special_act_falls_through_by_punishment():
    assert antil(["Excise Act 9"], "10 years", "Excise Act").status == S.B
    assert antil(["IT Act 66"], "3 years", "IT Act").status == S.A


def test_antil_scope_note_on_every_category():
    for res in (antil(["BNS 103"], "life"), antil(["BNS 115(2)"], "1 year"), antil(["BNS 318(4)"], "7 years")):
        assert "not arrested during investigation" in (res.detail or "")


# 4. statutory bar -------------------------------------------------------------------------------------------------------
def bar(sections, special=None, **params):
    rule = StatutoryBarRule()
    rule.params = params
    return rule.evaluate(RuleInputs(as_of="2025-01-01", sections=sections, special_act=special))


def test_ndps_small_quantity_is_not_reached():
    assert bar(["NDPS 20(b)(ii)(A)"], "NDPS").status == S.NOT_APPLICABLE


@pytest.mark.parametrize("section", ["NDPS 19", "NDPS 24", "NDPS 27A", "NDPS 21(c)", "NDPS 20(b)(ii)(C)"])
def test_ndps_covered_offences(section):
    assert bar([section], "NDPS").status == S.BAR_APPLIES


@pytest.mark.parametrize("section", ["NDPS 21", "NDPS 20(b)(ii)(B)", "NDPS 27"])
def test_ndps_unknown_quantity_is_check(section):
    assert bar([section], "NDPS").status == S.CHECK


def test_uapa_is_check_until_chapters_are_configured_and_never_says_twin_conditions():
    res = bar(["UAPA 18"], "UAPA")
    assert res.status == S.CHECK and "prima facie" in (res.detail or "") and "twin" not in (res.detail or "").lower()
    res = bar(["UAPA 18"], "UAPA", uapa_chapter_iv_vi_sections=["18"])
    assert res.status == S.BAR_APPLIES and "prima facie" in (res.detail or "") and "twin" in (res.detail or "").lower()  # "not the twin-conditions test"
    assert "not the twin-conditions test" in (res.detail or "")


def test_pmla_bar_names_the_proviso():
    res = bar(["PMLA 4"], "PMLA")
    assert res.status == S.BAR_APPLIES and "one crore" in (res.detail or "")


def test_no_special_act_is_not_applicable():
    assert bar(["BNS 318(4)"]).status == S.NOT_APPLICABLE


# 5. grounds of arrest ------------------------------------------------------------------------------------------------
def grounds(**kw):
    return GroundsOfArrestRule().evaluate(RuleInputs(as_of="2026-01-01", **kw))


@pytest.mark.parametrize("arrest", ["2025-11-05", "2025-11-06", None])
def test_oral_only_grounds_are_check(arrest):
    res = grounds(arrest_date=arrest, grounds_communicated=True, grounds_in_writing=False)
    assert res.status == S.CHECK and "2 hours" in (res.detail or "")


def test_earlier_arrest_detail_names_the_contest():
    d = grounds(arrest_date="2025-01-10", grounds_communicated=True, grounds_in_writing=False).detail or ""
    assert "contested" in d and "2025-11-06" in d


def test_other_grounds_outcomes_unchanged():
    assert grounds(grounds_communicated=True).status == S.OK
    assert grounds(grounds_communicated=True, grounds_in_writing=True, arrest_date="2025-01-01").status == S.OK
    assert grounds(grounds_communicated=False).status == S.FLAG
    assert grounds().status == S.UNKNOWN


# 9. these rules stay unverified ---------------------------------------------------------------------------------------
def test_the_four_corrected_rules_stay_unverified_until_re_checked():
    by_id = {r.rule_id.value: r for r in default_rules()}
    for rule in ("default_bail", "undertrial_limit", "antil_category", "statutory_bar"):
        assert by_id[rule].last_verified is None, rule
    for rule in ("notice_of_appearance", "grounds_of_arrest", "production_24h"):
        assert by_id[rule].last_verified == "2026-10-27", rule


def test_parse_section():
    s = parse_section("NDPS 20(b)(ii)(A)")
    assert (s.act, s.number, s.ndps_quantity) == ("NDPS", "20", "small")
    assert parse_section("Arms Act 25").act == "ARMS"
    assert special_default_bail_limit(RuleInputs(as_of="2025-01-01", sections=["BNS 318"])) is None
