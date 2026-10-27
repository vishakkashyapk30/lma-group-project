"""Rights Radar rule 'antil_category' (plan §7.3, Appendix C)."""

from __future__ import annotations

from vakeel_sahayak.rights.acts import special_acts
from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.rights.punishment import PunishmentKind, parse_punishment
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult

# Acts with stringent bail provisions, from the judgment's own list (Antil, category C: "NDPS (S.37), PMLA (S.45), UAPA (S.43D(5), Companies Act, 212(6), etc.")
# as reviewed in docs/qa/rights-verification.md. The judgment's list ends "etc.", so this short list is a reviewed minimum, not a closed set.
STRINGENT_BAIL_ACTS = {"NDPS": "NDPS s.37", "PMLA": "PMLA s.45", "UAPA": "UAPA s.43D(5)", "COMPANIES": "Companies Act s.212(6)"}
SCOPE_NOTE = (
    " Antil's categories decide how an accused who was not arrested during investigation and cooperated is treated after the charge sheet; "
    "for a client in custody this is context, not a bail entitlement."
)

# Sections that often carry an economic-offence argument (category D). Our reading, not in the plan: confirm in week 0.
ECONOMIC_SECTIONS = [
    "BNS 316", "BNS 318", "BNS 336", "BNS 338", "BNS 340",
    "IPC 406", "IPC 409", "IPC 420", "IPC 467", "IPC 468", "IPC 471",
]  # fmt: skip


class AntilCategoryRule(Rule):
    """Rights Radar rule: antil_category (plan §7.3, Appendix C)."""

    rule_id = RightsCheckName.ANTIL_CATEGORY
    rule_text = (
        "A: up to 7 years (not B or D). B: death, life, or more than 7 years. C: only special acts with stringent bail provisions (NDPS s.37, PMLA s.45, UAPA s.43D(5), Companies Act s.212(6)); "
        "any other special act falls through to A or B by punishment. D: economic offences not under special acts. "
        "The categories are Antil's for an accused not arrested during investigation; shown as context for a client in custody."
    )
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
        stringent = [STRINGENT_BAIL_ACTS[a] for a in special_acts(inputs) if a in STRINGENT_BAIL_ACTS]
        if stringent:
            return self.result(
                RightsStatus.C,
                f"Charged under a special act with stringent bail provisions ({', '.join(stringent)}): category C.{SCOPE_NOTE}",
                uses,
                dates,
            )
        others = [a for a in special_acts(inputs)]
        unlisted = (
            f" The {', '.join(others)} charge is under a special act that is not on the reviewed list of acts with stringent bail provisions "
            "(the judgment's list ends 'etc.'); confirm that it has none."
            if others
            else ""
        )
        if punishment.kind == PunishmentKind.UNKNOWN:
            return self.result(
                RightsStatus.CHECK, "Maximum punishment is not on record, so the category cannot be set." + unlisted + SCOPE_NOTE, uses, dates
            )
        if punishment.capital_or_life or (punishment.years or 0) > 7:
            return self.result(
                RightsStatus.B,
                f"Maximum punishment is {punishment.text}: category B (death, life or more than 7 years).{unlisted}{SCOPE_NOTE}",
                uses,
                dates,
            )
        hints = self.params.get("economic_sections", ECONOMIC_SECTIONS)
        if any(_normalise(s) in {_normalise(h) for h in hints} for s in inputs.sections):
            return self.result(
                RightsStatus.CHECK,
                f"Category A (up to {punishment.text}), unless treated as an economic offence (D).{unlisted}{SCOPE_NOTE}",
                uses,
                dates,
            )
        return self.result(
            RightsStatus.A,
            f"Maximum punishment is {punishment.text}: category A (up to 7 years).{unlisted}{SCOPE_NOTE}",
            uses,
            dates,
        )


def _normalise(section: str) -> str:
    """Compare section references by act and main section, ignoring case, spacing and sub-clauses: 'BNS 318(4)' is 'BNS318'."""
    return "".join(section.upper().split()).split("(")[0]
