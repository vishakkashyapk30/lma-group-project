"""Rights Radar rule 'undertrial_limit' (plan §7.3, Appendix C)."""

from __future__ import annotations

import math
from datetime import timedelta

from vakeel_sahayak.rights.acts import begun_after_bnss
from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.day_count import format_dmy, parse_date
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class UndertrialLimitRule(Rule):
    """Rights Radar rule: undertrial_limit (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.UNDERTRIAL_LIMIT
    rule_text = (
        "Release on bail after half the maximum sentence, or on bond after one-third for a first-time offender (a person never convicted of any offence). "
        "Not for offences punishable with death or life imprisonment; for a life-imprisonment case begun before 1 July 2024 (CrPC s.436A applied) the answer is CHECK. "
        "Where an investigation, inquiry or trial in more than one offence or multiple cases is pending against the person, s.479(2) says he shall not be released on bail by the Court; "
        "courts treat this as a restriction on the court's discretion, so the answer is CHECK, never ELIGIBLE. "
        "The second proviso lets the Court order continued detention after hearing the Public Prosecutor, and delay caused by the accused is excluded (Explanation)."
    )
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
        if punishment.kind == PunishmentKind.DEATH or (punishment.capital_or_life and begun_after_bnss(inputs) is True):
            return self.result(
                RightsStatus.NOT_APPLICABLE,
                f"Maximum punishment is {punishment.text}; BNSS s.479(1) does not apply to death or life imprisonment.",
                uses,
            )
        if punishment.capital_or_life:
            return self.result(
                RightsStatus.CHECK,
                f"Maximum punishment is {punishment.text}. BNSS s.479 excludes life imprisonment, but CrPC s.436A did not, and the case is not clearly one begun on or after 1 July 2024; "
                "whether an older life-imprisonment case keeps the s.436A benefit is unsettled (no reading found). Check with counsel.",
                uses,
                {"arrest_date": inputs.arrest_date, "first_remand": inputs.first_remand},
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
            f"(1/3 of {stated}, on bond) and {half:,} days otherwise (1/2, on bail)."
        )
        dates = {"as_of": inputs.as_of, "arrest_date": inputs.arrest_date, "first_remand": inputs.first_remand}
        if not inputs.antecedents_known or inputs.first_time_offender is None:
            if inputs.custody_days >= half:  # both thresholds are met, but s.479(2) (other pending cases) is unknown too
                if inputs.other_pending_cases is False:
                    return self.result(
                        RightsStatus.ELIGIBLE,
                        f"{base} Antecedents unknown, but custody is past the higher threshold of {half:,} days, so the limit is reached either way. {_PENDING_NO}",
                        uses,
                        dates,
                    )
                return self.result(
                    RightsStatus.CHECK,
                    f"{base} Antecedents unknown and custody is past the higher threshold of {half:,} days. {_PENDING_UNKNOWN if inputs.other_pending_cases is None else _PENDING_YES}",
                    uses,
                    dates,
                )
            return self.result(RightsStatus.CHECK, f"{base} Antecedents unknown.", uses, dates)
        threshold, label = (third, "1/3, first-time offender") if inputs.first_time_offender else (half, "1/2")
        if inputs.custody_days >= threshold:
            if inputs.other_pending_cases:
                return self.result(
                    RightsStatus.CHECK,
                    f"{base} The applicable threshold ({label}) of {threshold:,} days has been reached. {_PENDING_YES}",
                    uses + ["other_pending_cases"],
                    dates,
                )
            note = f" {_PENDING_NO}" if inputs.other_pending_cases is False else f" {_PENDING_CONFIRM}"
            return self.result(
                RightsStatus.ELIGIBLE,
                f"{base} The applicable threshold ({label}) of {threshold:,} days has been reached.{note}",
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


_PENDING_YES = (
    "Another case is pending against the person: BNSS s.479(2) says he shall not be released on bail by the Court, and bail is then in the court's discretion "
    "(Delhi High Court, BAIL APPLN. 4657/2024). Check, do not treat as an entitlement."
)
_PENDING_NO = "The record shows no other pending case (BNSS s.479(2))."
_PENDING_UNKNOWN = "Whether other cases are pending is not on record, and BNSS s.479(2) restricts release if they are; confirm before relying on this."
_PENDING_CONFIRM = "Confirm that no other case is pending against the person (BNSS s.479(2))."


def _num(value: float) -> str:
    """Print 7.0 as '7' and 2.5 as '2.5'."""
    return str(int(value)) if value == int(value) else f"{value:g}"
