"""Rights Radar rule 'default_bail' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.day_count import add_days, count_days, format_dmy
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class DefaultBailRule(Rule):
    """Rights Radar rule: default_bail (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.DEFAULT_BAIL
    rule_text = "Release if no charge sheet within 90 days (death, life or 10+ years) or 60 days (other offences), counted from first remand as day 1. Right lapses if the charge sheet is filed before an application. 'May extend to ten years' returns CHECK."
    sources = ["BNSS s.187(3) (CrPC s.167(2))", "ED v. Kapil Wadhawan (2023)", "M. Ravindran v. DRI (2020)"]
    rule_cite = "BNSS s.187(3)"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.ELIGIBLE, RightsStatus.NOT_YET, RightsStatus.WINDOW_CLOSED, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'default_bail'. Allowed statuses: ELIGIBLE, NOT_YET, WINDOW_CLOSED, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["first_remand", "charge_sheet", "sections"]
        if not inputs.first_remand:
            return self.result(
                RightsStatus.CHECK, "First remand date is not on record, so days cannot be counted.", uses
            )
        punishment = parse_punishment(inputs.max_punishment)
        if punishment.kind == PunishmentKind.UNKNOWN:
            return self.result(
                RightsStatus.CHECK, "Maximum punishment is not on record, so the 60 or 90 day limit is unknown.", uses
            )
        if punishment.is_ten_years:
            return self.result(
                RightsStatus.CHECK,
                f"Maximum punishment is {punishment.text}. Whether 'may extend to ten years' takes the 90-day or the 60-day limit is unsettled.",
                uses,
                {"first_remand": inputs.first_remand},
            )
        limit = 90 if punishment.ninety_day else 60
        try:
            as_of_day = count_days(inputs.first_remand, inputs.as_of)
        except ValueError:
            return self.result(RightsStatus.CHECK, "The as-of date is before the first remand.", uses)
        head = f"{limit}-day limit (maximum {punishment.text}). Day 1 is the first remand, {format_dmy(inputs.first_remand)}."
        dates = {
            "first_remand": inputs.first_remand,
            "as_of": inputs.as_of,
            "window_opens": add_days(inputs.first_remand, limit + 1),
            "charge_sheet": inputs.charge_sheet_date,
            "application": inputs.application_date,
        }
        if inputs.charge_sheet_filed and not inputs.charge_sheet_date:
            return self.result(
                RightsStatus.CHECK, f"{head} A charge sheet is recorded as filed but its date is missing.", uses, dates
            )
        cs_date = inputs.charge_sheet_date
        if cs_date and cs_date > inputs.as_of:
            cs_date = None  # not yet filed as of the as-of date
        if cs_date:
            return self._with_charge_sheet(inputs, head, limit, cs_date, uses, dates)
        return self._without_charge_sheet(inputs, head, limit, as_of_day, uses, dates)

    def _with_charge_sheet(
        self, inputs: RuleInputs, head: str, limit: int, cs_date: str, uses: list[str], dates: dict[str, str | None]
    ) -> RightsCheckResult:
        """Status when a charge sheet was filed on or before the as-of date."""
        assert inputs.first_remand
        cs_day = count_days(inputs.first_remand, cs_date)
        filed = f"The charge sheet was filed on day {cs_day} ({format_dmy(cs_date)})."
        if (
            inputs.application_date
            and inputs.application_date <= cs_date
            and count_days(inputs.first_remand, inputs.application_date) > limit
        ):
            app_day = count_days(inputs.first_remand, inputs.application_date)
            detail = f"{head} {filed} A default-bail application was made on day {app_day}, before the charge sheet, so the right was exercised in time."
            return self.result(RightsStatus.ELIGIBLE, detail, uses + ["application_date"], dates)
        if cs_day <= limit:
            detail = f"{head} {filed} It came within the limit, so the right to default bail never arose."
            return self.result(RightsStatus.WINDOW_CLOSED, detail, uses, dates)
        if cs_day == limit + 1:
            window = f"The right arose on day {limit + 1}, the day the charge sheet was filed; check whether an application was made that day."
        else:
            window = f"Default bail was available on days {limit + 1}-{cs_day - 1} if an application was made; check whether one was."
        return self.result(RightsStatus.WINDOW_CLOSED, f"{head} {filed} {window}", uses, dates)

    def _without_charge_sheet(
        self, inputs: RuleInputs, head: str, limit: int, as_of_day: int, uses: list[str], dates: dict[str, str | None]
    ) -> RightsCheckResult:
        """Status when no charge sheet is on record as of the as-of date."""
        assert inputs.first_remand
        opens = format_dmy(add_days(inputs.first_remand, limit + 1))
        if as_of_day <= limit:
            left = limit + 1 - as_of_day
            return self.result(
                RightsStatus.NOT_YET,
                f"{head} As of {format_dmy(inputs.as_of)} it is day {as_of_day}. The right arises on day {limit + 1} ({opens}), {left} day(s) from now, if no charge sheet is filed.",
                uses,
                dates,
            )
        if inputs.charge_sheet_filed is None:
            return self.result(
                RightsStatus.CHECK,
                f"{head} It is day {as_of_day} and the file does not say whether a charge sheet was filed; confirm before relying on this.",
                uses,
                dates,
            )
        return self.result(
            RightsStatus.ELIGIBLE,
            f"{head} It is day {as_of_day} and no charge sheet is on record. The right arose on day {limit + 1} ({opens}); an application must be made before a charge sheet is filed.",
            uses,
            dates,
        )
