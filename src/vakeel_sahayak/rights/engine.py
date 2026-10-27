"""Rights Radar engine (plan §7.3, §7.4)."""

from __future__ import annotations

import re

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.day_count import DateRule, count_days
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import most_severe
from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent

_STATED = (FieldStatus.VERIFIED, FieldStatus.USER_STATED, FieldStatus.USER_EDITED, FieldStatus.COMPUTED)
_GENERAL_CODES = {"IPC", "BNS", "CRPC", "BNSS"}  # any other code is a special act


def default_rules() -> list[Rule]:
    """The seven rules of plan §7.3, with `last_verified` and parameters taken from configs/rights_rules.yaml."""
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.rights.rules.antil_category import AntilCategoryRule
    from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
    from vakeel_sahayak.rights.rules.grounds_of_arrest import GroundsOfArrestRule
    from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
    from vakeel_sahayak.rights.rules.production_24h import Production24hRule
    from vakeel_sahayak.rights.rules.statutory_bar import StatutoryBarRule
    from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule

    config = load_config().rights_rules
    rules: list[Rule] = [
        DefaultBailRule(),
        UndertrialLimitRule(),
        NoticeOfAppearanceRule(),
        GroundsOfArrestRule(),
        Production24hRule(),
        AntilCategoryRule(),
        StatutoryBarRule(),
    ]
    for rule in rules:
        section = config.get(rule.rule_id.value) or {}
        rule.last_verified = section.get("last_verified", rule.last_verified)
        rule.params = dict(section.get("params") or {})
    return rules


def _value(field: TrackedField, only_stated: bool = True):
    """Value of a tracked field, or None when it is missing or UNSUPPORTED."""
    if field.value is None or (only_stated and field.status not in _STATED + (FieldStatus.AMBIGUOUS,)):
        return None
    return field.value


_PENDING = re.compile(r"pending|under\s+(?:investigation|trial|inquiry)|trial\s+in\s+progress", re.IGNORECASE)


def _pending_cases(antecedents: list[str]) -> bool:
    """BNSS s.479(2): True if an antecedent entry says another case is pending. Only called when the antecedents are on record."""
    return any(_PENDING.search(str(entry)) for entry in antecedents)


class RightsEngine:
    """Runs all rules over the dossier and timeline; also runs on a clock because custody grows daily (plan §7.4)."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        """Create the engine.

        Args:
            rules: defaults to the seven rules in rights/rules
        """
        self.rules = rules if rules is not None else default_rules()

    def build_inputs(self, dossier: CaseDossier, timeline: list[TimelineEvent], as_of: str) -> RuleInputs:
        """Derive rule inputs from case state.

        The timeline is not read yet: no rule needs more than the dossier fields (an application date or times of day
        can be passed by building RuleInputs directly).

        Args:
            dossier: see behaviour
            timeline: see behaviour
            as_of: see behaviour

        Returns:
            RuleInputs.
        """
        f = dossier.fields
        sections = _value(f.sections) or []
        arrest_date = _value(f.arrest_date)
        first_remand = _value(f.first_remand)
        cs = _value(f.charge_sheet)
        custody = _value(f.custody_days)
        if arrest_date and as_of >= arrest_date:  # custody grows daily: always recount from the arrest (plan §7.4)
            custody = count_days(arrest_date, as_of, DateRule.CALENDAR_DAYS_BETWEEN)
        ante = _value(f.antecedents)
        known = ante is not None
        pending = _pending_cases(ante) if known else None
        fir = _value(f.fir)
        codes = [s.code.upper() for s in sections]
        special = next((s.code for s in sections if s.code.upper() not in _GENERAL_CODES), None)
        return RuleInputs(
            as_of=as_of,
            first_remand=first_remand,
            charge_sheet_date=cs.date if cs else None,
            charge_sheet_filed=cs.filed if cs else None,
            arrest_date=arrest_date,
            production_date=first_remand if arrest_date else None,  # the first remand is the first production
            max_punishment=most_severe([s.max_punishment for s in sections]) if sections else None,
            sections=[f"{s.code} {s.section}" for s in sections],
            custody_days=custody,
            antecedents_known=known,
            first_time_offender=(len(ante) == 0) if known else None,
            special_act=special if codes else None,
            other_pending_cases=pending,
            fir_date=fir.date if fir else None,
        )

    def run(self, dossier: CaseDossier, timeline: list[TimelineEvent], as_of: str) -> RightsReport:
        """Run every rule and assemble the RightsReport (plan §7.3).

        Args:
            dossier: see behaviour
            timeline: see behaviour
            as_of: see behaviour

        Returns:
            RightsReport.
        """
        inputs = self.build_inputs(dossier, timeline, as_of)
        return RightsReport(case_id=dossier.case_id, as_of=as_of, checks=[r.evaluate(inputs) for r in self.rules])

    def clock_crossings(self, previous: RightsReport, current: RightsReport) -> list[str]:
        """Detect threshold crossings (e.g. the s.479 date) that should create a change set (plan §7.4).

        Args:
            previous: see behaviour
            current: see behaviour

        Returns:
            Names of checks whose status changed between the two reports.
        """
        before = {c.check: c.status for c in previous.checks}
        return [c.check.value for c in current.checks if c.check in before and before[c.check] != c.status]
