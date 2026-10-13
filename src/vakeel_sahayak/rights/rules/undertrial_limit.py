"""Rights Radar rule 'undertrial_limit' (plan §7.3, Appendix C)."""

from __future__ import annotations

import math
from datetime import timedelta

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.day_count import format_dmy, parse_date
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class UndertrialLimitRule(Rule):
    """Rights Radar rule: undertrial_limit (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.UNDERTRIAL_LIMIT
    rule_text = "Release on bond after half the maximum sentence, or one-third for a first-time offender. Not for offences punishable with death or life imprisonment."
    sources = ["BNSS s.479 (CrPC s.436A)", "In Re Inhuman Conditions in 1382 Prisons (2024 statement)"]
    rule_cite = "BNSS s.479"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.ELIGIBLE, RightsStatus.NOT_YET, RightsStatus.NOT_APPLICABLE, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'undertrial_limit'. Allowed statuses: ELIGIBLE, NOT_YET, NOT_APPLICABLE, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["custody_days", "sections", "antecedents"]
        punishment = parse_punishment(inputs.max_punishment)
        if punishment.capital_or_life:
            return self.result(
                RightsStatus.NOT_APPLICABLE,
                f"Maximum punishment is {punishment.text}; the undertrial limit does not apply to death or life imprisonment.",
                uses,
            )
        if punishment.kind != PunishmentKind.YEARS or inputs.custody_days is None:
            missing = "Maximum punishment" if punishment.kind != PunishmentKind.YEARS else "Custody days"
            return self.result(
                RightsStatus.CHECK, f"{missing} not on record, so the threshold cannot be compared.", uses
            )
        years = punishment.years or 0.0
        third, half = math.ceil(years * 365 / 3), math.ceil(years * 365 / 2)
        stated = f"{_num(years)} years"
        base = (
            f"{inputs.custody_days} days in custody. The threshold is {third:,} days for a first-time offender "
            f"(1/3 of {stated}) and {half:,} days otherwise (1/2)."
        )
        dates = {"as_of": inputs.as_of, "arrest_date": inputs.arrest_date, "first_remand": inputs.first_remand}
        if not inputs.antecedents_known or inputs.first_time_offender is None:
            if inputs.custody_days >= half:  # both thresholds are met, so antecedents do not matter
                return self.result(
                    RightsStatus.ELIGIBLE,
                    f"{base} Antecedents unknown, but custody is past the higher threshold of {half:,} days, so the limit is reached either way.",
                    uses,
                    dates,
                )
            return self.result(RightsStatus.CHECK, f"{base} Antecedents unknown.", uses, dates)
        threshold, label = (third, "1/3, first-time offender") if inputs.first_time_offender else (half, "1/2")
        if inputs.custody_days >= threshold:
            return self.result(
                RightsStatus.ELIGIBLE,
                f"{base} The applicable threshold ({label}) of {threshold:,} days has been reached.",
                uses,
                dates,
            )
        reached = (parse_date(inputs.as_of) + timedelta(days=threshold - inputs.custody_days)).isoformat()
        dates["threshold_date"] = reached
        return self.result(
            RightsStatus.NOT_YET,
            f"{base} The applicable threshold ({label}) of {threshold:,} days is reached on {format_dmy(reached)}, {threshold - inputs.custody_days} day(s) from now.",
            uses,
            dates,
        )


def _num(value: float) -> str:
    """Print 7.0 as '7' and 2.5 as '2.5'."""
    return str(int(value)) if value == int(value) else f"{value:g}"
