"""Rights Radar rule 'grounds_of_arrest' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult

MIHIR_DATE = "2025-11-06"  # Mihir Rajesh Shah v. State of Maharashtra, judgment of 6 November 2025 (docs/qa/rights-verification.md)


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
        if inputs.grounds_communicated and inputs.grounds_in_writing is False:
            return self._oral_only(inputs, uses, dates)
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

    def _oral_only(self, inputs: RuleInputs, uses: list[str], dates: dict[str, str | None]) -> RightsCheckResult:
        """Grounds were communicated, but only orally: CHECK, because the written-grounds rule and its reach to earlier arrests are contested."""
        uses = [*uses, "grounds_in_writing"]
        earlier = inputs.arrest_date is not None and inputs.arrest_date < MIHIR_DATE
        if earlier:
            when = (
                f"The arrest was on {inputs.arrest_date}, before {MIHIR_DATE} when Mihir Rajesh Shah was decided. Whether the written-grounds requirement reaches earlier arrests is contested "
                "(Delhi High Court: prospective; Orissa High Court: the duty flows from Art. 22 itself)."
            )
        elif inputs.arrest_date is None:
            when = f"The arrest date is not on record, so it cannot be placed before or after {MIHIR_DATE}, when Mihir Rajesh Shah required written grounds."
        else:
            when = f"The arrest was on {inputs.arrest_date}, after Mihir Rajesh Shah ({MIHIR_DATE}); written grounds are required unless supplied at least 2 hours before production for remand."
        return self.result(
            RightsStatus.CHECK,
            f"The record shows the grounds were communicated orally only. {when} Check whether written grounds in a language the arrested person understands were supplied at least 2 hours before production.",
            uses,
            dates,
        )
