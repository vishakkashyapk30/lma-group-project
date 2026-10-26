"""An s.479 BNSS (s.436A CrPC) threshold that is days away is a legal deadline (plan §11, found by feature run F4 on T5).

The wording comes from the real rule (`UndertrialLimitRule`), so the test breaks if the rule's sentence and the urgency parser drift apart.
Deadlines coming up are ordered nearest first whichever right they concern; on the same day the default-bail window goes first.
"""

from __future__ import annotations

from tests.unit.batch._helpers import DEFAULT_NONE, DEFAULT_OPEN, S479_CROSSED_5, S479_NONE, card, rights
from vakeel_sahayak.batch.urgency import CODE_S479_SOON, assess, has_deadline, rank
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule
from vakeel_sahayak.schemas.rights_report import RightsReport


def s479_ahead(days_left: int):
    """The real rule's NOT_YET result: 7 years, first-time offender, threshold 852 days, `days_left` days to go."""
    inputs = RuleInputs(as_of="2026-11-02", max_punishment="may extend to seven years", custody_days=852 - days_left, arrest_date="2024-07-01",
                        antecedents_known=True, first_time_offender=True)
    res = UndertrialLimitRule().evaluate(inputs)
    assert res.status.value == "NOT_YET"
    return res.status.value, res.detail


def test_threshold_a_few_days_away_is_a_deadline_with_its_reason():
    u = assess(rights(DEFAULT_NONE, s479_ahead(3)), 850, [])
    assert u.legal_deadline and CODE_S479_SOON in u.codes() and "s.479 threshold reached in 3 day(s)" in u.texts()[0]


def test_threshold_far_away_is_not_a_deadline():
    assert not assess(rights(DEFAULT_NONE, s479_ahead(30)), 820, []).legal_deadline


def test_nearest_deadline_first_across_the_two_rights_and_default_bail_wins_a_tie():
    from tests.unit.batch._helpers import DEFAULT_SOON  # 3 days

    cards = [card("far", DEFAULT_NONE, s479_ahead(30), 820), card("no-flag", DEFAULT_NONE, S479_NONE, 3000), card("479-in-5", DEFAULT_NONE, s479_ahead(5), 848),
             card("479-in-3", DEFAULT_NONE, s479_ahead(3), 850), card("db-in-3", DEFAULT_SOON, S479_NONE, 40), card("479-in-1", DEFAULT_NONE, s479_ahead(1), 852)]
    order = [c.case_id for c in rank(cards)]
    assert order[:4] == ["479-in-1", "db-in-3", "479-in-3", "479-in-5"]
    assert set(order[4:]) == {"far", "no-flag"} and order == [c.case_id for c in rank(rank(cards))]
    assert has_deadline(next(c for c in cards if c.case_id == "479-in-5")) and not has_deadline(next(c for c in cards if c.case_id == "far"))


def test_open_default_bail_and_crossed_s479_keep_their_places():
    cards = [card("crossed", DEFAULT_NONE, S479_CROSSED_5, 857), card("soon", DEFAULT_NONE, s479_ahead(2), 851), card("open", DEFAULT_OPEN, S479_NONE, 70)]
    assert [c.case_id for c in rank(cards)] == ["open", "soon", "crossed"]


def test_threshold_dates_are_read_from_the_check_when_present():
    base = rights(DEFAULT_NONE, s479_ahead(4))
    check = base.checks[[c.check.value for c in base.checks].index("undertrial_limit")]
    dated = check.model_copy(update={"dates": {"as_of": "2026-11-02", "threshold_date": "2026-11-06"}, "detail": "no wording here"})
    report = RightsReport(case_id=base.case_id, as_of="2026-11-02", checks=[dated if c.check == check.check else c for c in base.checks])
    assert assess(report, 849, []).codes().count(CODE_S479_SOON) == 1
