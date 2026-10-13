"""Rights Radar rule 'grounds_of_arrest' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult


class GroundsOfArrestRule(Rule):
    """Rights Radar rule: grounds_of_arrest (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.GROUNDS_OF_ARREST
    rule_text = "Grounds must be communicated; since Mihir Rajesh Shah, in writing, in a language the arrested person understands, at least 2 hours before production. Application to earlier arrests is contested, so CHECK."
    sources = [
        "Art. 22(1)",
        "BNSS s.47 (CrPC s.50)",
        "Vihaan Kumar v. State of Haryana (2025)",
        "Mihir Rajesh Shah v. State of Maharashtra (2025)",
    ]
    rule_cite = "Art. 22(1); BNSS s.47; Vihaan Kumar (2025)"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.FLAG, RightsStatus.OK, RightsStatus.UNKNOWN, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'grounds_of_arrest'. Allowed statuses: FLAG, OK, UNKNOWN, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["arrest_date", "arrest_memo"]
        dates = {"arrest_date": inputs.arrest_date, "production_date": inputs.production_date}
        if inputs.grounds_communicated is None:
            return self.result(
                RightsStatus.UNKNOWN, "No record that the grounds of arrest were communicated.", uses, dates
            )
        if inputs.grounds_communicated:
            return self.result(
                RightsStatus.OK,
                "The record shows the grounds were communicated; check they were in writing, in a language the arrested person understands, at least 2 hours before production.",
                uses,
                dates,
            )
        return self.result(
            RightsStatus.FLAG,
            "The record says the grounds of arrest were not communicated (Art. 22(1), BNSS s.47). Written grounds at least 2 hours before production are required since Mihir Rajesh Shah; whether that applies to an arrest of this date is contested, but communication itself is required either way.",
            uses,
            dates,
        )
