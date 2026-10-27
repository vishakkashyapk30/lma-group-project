"""Rights Radar: notice of appearance, grounds of arrest, 24-hour production, Antil category, statutory bar
(plan §7.3 rows 3-7, Appendix C rows 3-7).

Case-0007 expectations from the plan's RightsReport: notice_of_appearance UNKNOWN (no arrest memo or notice in the file),
grounds_of_arrest UNKNOWN, production_24h CHECK (produced the next day; times not on record), antil_category CHECK
(Category A, unless treated as an economic offence D), statutory_bar NOT_APPLICABLE.
"""

import pytest

from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.antil_category import AntilCategoryRule
from vakeel_sahayak.rights.rules.grounds_of_arrest import GroundsOfArrestRule
from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
from vakeel_sahayak.rights.rules.production_24h import Production24hRule
from vakeel_sahayak.rights.rules.statutory_bar import StatutoryBarRule
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus

S = RightsStatus


# ------------------------------------------------------------------ notice of appearance, BNSS s.35(3) / CrPC s.41A
class TestNoticeOfAppearance:
    rule = NoticeOfAppearanceRule()

    def test_metadata(self):
        """Statuses FLAG/OK/UNKNOWN and the Arnesh Kumar / Antil sources."""
        assert self.rule.rule_id == RightsCheckName.NOTICE_OF_APPEARANCE
        assert set(self.rule.allowed_statuses) == {S.FLAG, S.OK, S.UNKNOWN}
        assert "Arnesh Kumar" in " ".join(self.rule.sources)

    def test_case_0007_unknown(self, rule_inputs_0007):
        """No arrest memo or notice in the file -> UNKNOWN, detail says up to 7 years."""
        res = self.rule.evaluate(rule_inputs_0007)
        assert res.status == S.UNKNOWN
        assert "7 years" in (res.detail or "")

    def test_memo_on_file_is_ok(self, make_rule_inputs):
        """A notice/arrest memo on file -> OK."""
        assert self.rule.evaluate(make_rule_inputs(arrest_memo_present=True)).status == S.OK

    def test_memo_reviewed_and_absent_is_flag(self, make_rule_inputs):
        """ASSUMPTION: arrest_memo_present=False (file reviewed, no notice/reasons) for a <=7-year offence -> FLAG."""
        assert self.rule.evaluate(make_rule_inputs(arrest_memo_present=False)).status == S.FLAG

    def test_serious_offence_is_not_flagged(self, make_rule_inputs):
        """The 7-year norm does not apply to offences above 7 years: never FLAG."""
        res = self.rule.evaluate(make_rule_inputs(max_punishment="10 years", arrest_memo_present=False))
        assert res.status != S.FLAG


# ------------------------------------------------------------------ grounds of arrest, Art. 22(1), BNSS s.47
class TestGroundsOfArrest:
    rule = GroundsOfArrestRule()

    def test_metadata(self):
        """Statuses FLAG/OK/UNKNOWN/CHECK; Vihaan Kumar and Mihir Rajesh Shah sources."""
        assert self.rule.rule_id == RightsCheckName.GROUNDS_OF_ARREST
        assert set(self.rule.allowed_statuses) == {S.FLAG, S.OK, S.UNKNOWN, S.CHECK}
        joined = " ".join(self.rule.sources)
        assert "Vihaan Kumar" in joined and "Mihir Rajesh Shah" in joined

    def test_case_0007_unknown(self, rule_inputs_0007):
        """No record that the grounds were communicated -> UNKNOWN."""
        res = self.rule.evaluate(rule_inputs_0007)
        assert res.status == S.UNKNOWN
        assert "grounds" in (res.detail or "").lower()

    def test_recorded_as_not_communicated_is_flag(self, make_rule_inputs):
        """ASSUMPTION: grounds_communicated=False (recorded as not given) -> FLAG."""
        assert self.rule.evaluate(make_rule_inputs(grounds_communicated=False)).status == S.FLAG

    def test_communicated_is_ok_or_check(self, make_rule_inputs):
        """ASSUMPTION: communicated for an arrest before the Mihir Rajesh Shah rule: the written-form requirement is
        contested for earlier arrests (Appendix C), so OK or CHECK, never FLAG/UNKNOWN."""
        assert self.rule.evaluate(make_rule_inputs(grounds_communicated=True)).status in {S.OK, S.CHECK}


# ------------------------------------------------------------------ 24-hour production, Art. 22(2), BNSS s.58
class TestProduction24h:
    rule = Production24hRule()

    def test_metadata(self):
        """Statuses FLAG/OK/CHECK."""
        assert self.rule.rule_id == RightsCheckName.PRODUCTION_24H
        assert set(self.rule.allowed_statuses) == {S.FLAG, S.OK, S.CHECK}
        assert "58" in " ".join(self.rule.sources)

    def test_case_0007_next_day_without_times_is_check(self, rule_inputs_0007):
        """Plan §7.3: arrest 2024-08-20, produced 2024-08-21, times not on record -> CHECK."""
        res = self.rule.evaluate(rule_inputs_0007)
        assert res.status == S.CHECK
        assert "times" in (res.detail or "").lower()

    @pytest.mark.parametrize(
        ("arrest", "production", "expected"),
        [
            (("2024-08-20", "10:00"), ("2024-08-21", "09:00"), S.OK),  # 23 h
            (("2024-08-20", "10:00"), ("2024-08-21", "10:00"), S.OK),  # exactly 24 h is within 24 hours
            (("2024-08-20", "10:00"), ("2024-08-21", "11:00"), S.FLAG),  # 25 h
            (("2024-08-20", "23:30"), ("2024-08-21", "00:30"), S.OK),  # 1 h across midnight
            (("2024-08-20", "10:00"), ("2024-08-20", "18:00"), S.OK),  # same day
        ],
    )
    def test_with_times(self, make_rule_inputs, arrest, production, expected):
        """With arrest and production times the 24-hour test is exact (ASSUMPTION: HH:MM strings, travel time ignored)."""
        res = self.rule.evaluate(
            make_rule_inputs(arrest_date=arrest[0], arrest_time=arrest[1], production_date=production[0],
                             production_time=production[1])
        )
        assert res.status == expected

    def test_same_day_without_times_is_ok(self, make_rule_inputs):
        """Same calendar day needs no times: within 24 hours whatever they were."""
        assert self.rule.evaluate(make_rule_inputs(production_date="2024-08-20")).status == S.OK

    def test_missing_dates_is_check(self, make_rule_inputs):
        """No production date on record -> CHECK."""
        assert self.rule.evaluate(make_rule_inputs(production_date=None)).status == S.CHECK


# ------------------------------------------------------------------ Antil category, Satender Kumar Antil v. CBI (2022)
class TestAntilCategory:
    rule = AntilCategoryRule()

    def inputs(self, max_punishment, sections, special_act=None):
        return RuleInputs(as_of="2025-02-03", max_punishment=max_punishment, sections=sections, special_act=special_act)

    def test_metadata(self):
        """Statuses A, B, C, D and CHECK."""
        assert self.rule.rule_id == RightsCheckName.ANTIL_CATEGORY
        assert set(self.rule.allowed_statuses) == {S.A, S.B, S.C, S.D, S.CHECK}
        assert "Antil" in " ".join(self.rule.sources)

    def test_case_0007_cheating_is_check_between_a_and_d(self, rule_inputs_0007):
        """Plan §7.3: BNS 318(4), up to 7 years -> CHECK: Category A unless treated as an economic offence (D)."""
        res = self.rule.evaluate(rule_inputs_0007)
        assert res.status == S.CHECK
        d = res.detail or ""
        assert "A" in d and "D" in d and "economic" in d.lower()

    @pytest.mark.parametrize(
        ("max_punishment", "sections", "special_act", "expected"),
        [
            ("1 year", ["BNS 115(2)"], None, S.A),  # up to 7 years, not economic
            ("7 years", ["BNS 137(2)"], None, S.A),  # exactly 7 years is still A  (ASSUMPTION: section is not economic)
            ("life", ["BNS 103"], None, S.B),  # death or life
            ("death", ["BNS 103"], None, S.B),
            ("10 years", ["BNS 124(1)"], None, S.B),  # more than 7 years
            ("3 years", ["NDPS 20"], "NDPS", S.C),  # special acts with strict bail conditions
            ("10 years", ["UAPA 13"], "UAPA", S.C),
            ("7 years", ["PMLA 4"], "PMLA", S.C),
        ],
    )
    def test_categories(self, max_punishment, sections, special_act, expected):
        """Category table of Appendix C: A up to 7 years; B death/life/more than 7; C special acts."""
        assert self.rule.evaluate(self.inputs(max_punishment, sections, special_act)).status == expected

    def test_category_d_is_a_possible_output(self):
        """D (economic offences not under special acts) is part of the output set (plan §7.3 'A-D, CHECK')."""
        assert S.D in self.rule.allowed_statuses


# ------------------------------------------------------------------ statutory bar: NDPS s.37, UAPA s.43D(5), PMLA s.45
class TestStatutoryBar:
    rule = StatutoryBarRule()

    def test_metadata(self):
        """Statuses BAR_APPLIES / NOT_APPLICABLE only; the three provisions are the sources."""
        assert self.rule.rule_id == RightsCheckName.STATUTORY_BAR
        assert set(self.rule.allowed_statuses) == {S.BAR_APPLIES, S.NOT_APPLICABLE, S.CHECK}  # RECONCILED: CHECK added (rights-verification.md, open question 7)
        joined = " ".join(self.rule.sources)
        assert "NDPS" in joined and "43D(5)" in joined and "PMLA" in joined

    def test_case_0007_not_applicable(self, rule_inputs_0007):
        """Plan §7.3: BNS 318(4) is under no special act -> NOT_APPLICABLE, rule names all three bars."""
        res = self.rule.evaluate(rule_inputs_0007)
        assert res.status == S.NOT_APPLICABLE
        rule_text = res.rule or ""
        assert "NDPS s.37" in rule_text and "UAPA s.43D(5)" in rule_text and "PMLA s.45" in rule_text

    @pytest.mark.parametrize(("act", "section", "expected"), [
        ("PMLA", "PMLA 4", S.BAR_APPLIES),  # PMLA s.45(1): any offence under the Act
        ("NDPS", "NDPS 27A", S.BAR_APPLIES),  # RECONCILED: NDPS s.37(1)(b) reaches s.19, 24, 27A and commercial quantity only
        ("NDPS", "NDPS 1", S.CHECK),  # RECONCILED: section and quantity unknown -> CHECK, not BAR_APPLIES
        ("UAPA", "UAPA 1", S.CHECK),  # RECONCILED: s.43D(5) reaches Chapters IV and VI only; chapter unknown -> CHECK
    ])
    def test_bar_applies(self, make_rule_inputs, act, section, expected):
        """PMLA s.45 applies to any offence under the Act; NDPS and UAPA need the section, quantity or chapter."""
        res = self.rule.evaluate(make_rule_inputs(special_act=act, sections=[section]))
        assert res.status == expected

    def test_no_special_act(self, make_rule_inputs):
        """No special act -> NOT_APPLICABLE."""
        assert self.rule.evaluate(make_rule_inputs(special_act=None)).status == S.NOT_APPLICABLE
