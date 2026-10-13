"""Rights Radar rule 'statutory_bar' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult

BARRING_ACTS = ["NDPS", "UAPA", "PMLA"]  # plan §7.3 / Appendix C


class StatutoryBarRule(Rule):
    """Rights Radar rule: statutory_bar (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.STATUTORY_BAR
    rule_text = "The twin conditions apply under NDPS s.37, UAPA s.43D(5) or PMLA s.45."
    sources = ["NDPS s.37", "UAPA s.43D(5)", "PMLA s.45"]
    rule_cite = "NDPS s.37; UAPA s.43D(5); PMLA s.45"
    last_verified = None  # TODO: date of week-0 check against the bare act
    allowed_statuses = [RightsStatus.BAR_APPLIES, RightsStatus.NOT_APPLICABLE]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'statutory_bar'. Allowed statuses: BAR_APPLIES, NOT_APPLICABLE. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["sections", "special_act"]
        found = [bar for bar in BARRING_ACTS if _mentions(bar, inputs)]
        if found:
            return self.result(
                RightsStatus.BAR_APPLIES,
                f"Charged under {', '.join(found)}: the twin conditions apply (NDPS s.37, UAPA s.43D(5) or PMLA s.45). Check that the specific section charged attracts the bar.",
                uses,
            )
        return self.result(RightsStatus.NOT_APPLICABLE, "No NDPS, UAPA or PMLA section is charged.", uses)


def _mentions(act: str, inputs: RuleInputs) -> bool:
    """True if the special act or any charged section names the act."""
    haystack = [inputs.special_act or "", *inputs.sections]
    return any(act in text.upper() for text in haystack)
