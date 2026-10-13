"""Rights Radar rule 'antil_category' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult

# Sections that often carry an economic-offence argument (category D). Our reading, not in the plan: confirm in week 0.
ECONOMIC_SECTIONS = [
    "BNS 316", "BNS 318", "BNS 336", "BNS 338", "BNS 340",
    "IPC 406", "IPC 409", "IPC 420", "IPC 467", "IPC 468", "IPC 471",
]  # fmt: skip


class AntilCategoryRule(Rule):
    """Rights Radar rule: antil_category (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.ANTIL_CATEGORY
    rule_text = "A: up to 7 years (not B or D). B: death, life, or more than 7 years. C: special acts with strict bail conditions. D: economic offences not under special acts."
    sources = ["Satender Kumar Antil v. CBI (2022)"]
    rule_cite = "Satender Kumar Antil v. CBI (2022)"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.A, RightsStatus.B, RightsStatus.C, RightsStatus.D, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'antil_category'. Allowed statuses: A, B, C, D, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["sections", "special_act"]
        punishment = parse_punishment(inputs.max_punishment)
        dates: dict[str, str | None] = {}
        if inputs.special_act:
            return self.result(
                RightsStatus.C,
                f"Charged under a special act ({inputs.special_act}) with strict bail conditions: category C.",
                uses,
                dates,
            )
        if punishment.kind == PunishmentKind.UNKNOWN:
            return self.result(
                RightsStatus.CHECK, "Maximum punishment is not on record, so the category cannot be set.", uses, dates
            )
        if punishment.capital_or_life or (punishment.years or 0) > 7:
            return self.result(
                RightsStatus.B,
                f"Maximum punishment is {punishment.text}: category B (death, life or more than 7 years).",
                uses,
                dates,
            )
        hints = self.params.get("economic_sections", ECONOMIC_SECTIONS)
        if any(_normalise(s) in {_normalise(h) for h in hints} for s in inputs.sections):
            return self.result(
                RightsStatus.CHECK,
                f"Category A (up to {punishment.text}), unless treated as an economic offence (D).",
                uses,
                dates,
            )
        return self.result(
            RightsStatus.A, f"Maximum punishment is {punishment.text}: category A (up to 7 years).", uses, dates
        )


def _normalise(section: str) -> str:
    """Compare section references by act and main section, ignoring case, spacing and sub-clauses: 'BNS 318(4)' is 'BNS318'."""
    return "".join(section.upper().split()).split("(")[0]
