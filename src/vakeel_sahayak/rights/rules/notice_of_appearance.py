"""Rights Radar rule 'notice_of_appearance' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class NoticeOfAppearanceRule(Rule):
    """Rights Radar rule: notice_of_appearance (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.NOTICE_OF_APPEARANCE
    rule_text = (
        "For offences punishable up to 7 years a notice of appearance is the norm and arrest needs recorded reasons."
    )
    sources = [
        "BNSS s.35(3) (CrPC s.41A)",
        "Arnesh Kumar v. State of Bihar (2014)",
        "Satender Kumar Antil v. CBI (2022)",
    ]
    rule_cite = "BNSS s.35(3); Arnesh Kumar (2014)"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.FLAG, RightsStatus.OK, RightsStatus.UNKNOWN]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'notice_of_appearance'. Allowed statuses: FLAG, OK, UNKNOWN. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["sections"]
        punishment = parse_punishment(inputs.max_punishment)
        if punishment.kind == PunishmentKind.UNKNOWN:
            return self.result(RightsStatus.UNKNOWN, "Maximum punishment is not on record.", uses)
        if punishment.capital_or_life or (punishment.years or 0) > 7:
            return self.result(
                RightsStatus.OK,
                f"Maximum punishment is {punishment.text}, above 7 years, so the notice-of-appearance norm is not engaged.",
                uses,
            )
        base = "Offence punishable up to 7 years."
        if inputs.arrest_memo_present is None:
            return self.result(
                RightsStatus.UNKNOWN,
                f"{base} No arrest memo or notice in the file.",
                uses,
                {"arrest_date": inputs.arrest_date},
            )
        if inputs.arrest_memo_present:
            return self.result(
                RightsStatus.OK,
                f"{base} An arrest memo or notice is in the file; confirm that it records the reasons for arrest.",
                uses + ["arrest_memo"],
                {"arrest_date": inputs.arrest_date},
            )
        return self.result(
            RightsStatus.FLAG,
            f"{base} The file shows no notice of appearance and no recorded reasons for arrest.",
            uses + ["arrest_memo"],
            {"arrest_date": inputs.arrest_date},
        )
