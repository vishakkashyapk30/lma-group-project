"""T4 cross-check (new tests): the designed answers are derived independently of the Rights Radar (`rights_spec_writer`); here, and only here,
the Radar is run on the same scenarios to see where the two readings differ. A disagreement is a finding to report, not something to hide."""

from __future__ import annotations

import collections
from datetime import date, timedelta

import pytest

from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
from vakeel_sahayak.rights.rules.production_24h import Production24hRule
from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule
from vakeel_sahayak.testsets import rights_spec_writer as writer
from vakeel_sahayak.testsets.t4_rights_scenarios import load_scenario_specs

RULES = {"default_bail": DefaultBailRule, "undertrial_limit": UndertrialLimitRule, "notice_of_appearance": NoticeOfAppearanceRule,
         "production_24h": Production24hRule}


def radar_inputs(spec: dict) -> RuleInputs:
    i, rule = spec["inputs"], spec["rule"]
    if rule == "default_bail":
        as_of = (date.fromisoformat(i["first_remand"]) + timedelta(days=i["day"] - 1)).isoformat()
        return RuleInputs(as_of=as_of, first_remand=i["first_remand"], max_punishment=i["max_punishment"],
                          charge_sheet_date=i["charge_sheet"], charge_sheet_filed=bool(i["charge_sheet"]))
    if rule == "undertrial_limit":
        return RuleInputs(as_of=i["as_of"], max_punishment=i["max_punishment"], custody_days=i["custody_days"], arrest_date=i["arrest_date"],
                          antecedents_known=i["first_time"] is not None, first_time_offender=i["first_time"])
    if rule == "notice_of_appearance":
        return RuleInputs(as_of=i["arrest_date"], max_punishment=i["max_punishment"], arrest_memo_present=i["arrest_memo"], arrest_date=i["arrest_date"])
    return RuleInputs(as_of=i["production_date"], arrest_date=i["arrest_date"], arrest_time=i["arrest_time"], production_date=i["production_date"],
                      production_time=i["production_time"])


def test_the_checked_in_spec_is_what_the_spec_writer_derives():
    """The YAML is generated, not hand-edited: regenerating it gives the same designed answers."""
    specs = load_scenario_specs(str(writer.SPEC_PATH))
    fresh = writer.write_scenarios()
    assert [(s["id"], s["designed_answer"], s["inputs"]) for s in specs] == [(s["id"], s["designed_answer"], s["inputs"]) for s in fresh]


def test_the_independent_derivation_agrees_with_the_radar_on_almost_every_scenario():
    """Two readings of the same rule text: they agree on the overwhelming majority; the Radar is never more permissive (no false ELIGIBLE)."""
    specs = load_scenario_specs(str(writer.SPEC_PATH))
    diffs = []
    for s in specs:
        got = RULES[s["rule"]]().evaluate(radar_inputs(s)).status.value
        if got != s["designed_answer"]:
            diffs.append((s["id"], s["designed_answer"], got))
    rate = len(diffs) / len(specs)
    assert not [d for d in diffs if d[2] == "ELIGIBLE"], diffs
    assert rate <= 0.02, collections.Counter((d[1], d[2]) for d in diffs)


def test_boundary_days_of_the_default_bail_window():
    spec = {"id": "x", "rule": "default_bail"}
    base = {"first_remand": "2024-08-21", "max_punishment": "7 years", "charge_sheet": None}
    answers = [writer.designed_default_bail({**base, "day": d}) for d in (59, 60, 61)]
    assert answers == ["NOT_YET", "NOT_YET", "ELIGIBLE"] and spec
    assert [writer.designed_default_bail({**base, "max_punishment": "life", "day": d}) for d in (90, 91)] == ["NOT_YET", "ELIGIBLE"]
    assert writer.designed_default_bail({**base, "max_punishment": "may extend to ten years", "day": 61}) == "CHECK"


@pytest.mark.parametrize(("first", "days", "want"), [(True, 851, "NOT_YET"), (True, 852, "ELIGIBLE"), (False, 1277, "NOT_YET"), (False, 1278, "ELIGIBLE")])
def test_undertrial_thresholds_for_seven_years(first, days, want):
    assert writer.undertrial_thresholds(7) == (852, 1278)
    assert writer.designed_undertrial({"custody_days": days, "max_punishment": "7 years", "first_time": first}) == want
