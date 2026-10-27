"""Rights Radar rule 'statutory_bar' (plan §7.3, Appendix C; narrowed by docs/qa/rights-verification.md, open question 7)."""

from __future__ import annotations

from vakeel_sahayak.rights.acts import NDPS_ALWAYS, ChargedSection, charged_sections
from vakeel_sahayak.rights.base import Rule
from vakeel_sahayak.rights.inputs import RuleInputs
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult

BARRING_ACTS = ["NDPS", "UAPA", "PMLA"]  # plan §7.3 / Appendix C

_BAR, _UNSURE, _NONE = "bar", "check", "none"


class StatutoryBarRule(Rule):
    """Rights Radar rule: statutory_bar (plan §7.3, Appendix C).

    Three different provisions, not one "twin conditions" test (docs/qa/rights-verification.md):

    * NDPS s.37(1)(b): twin conditions for an offence under s.19, s.24 or s.27A and for offences involving commercial quantity only. Clause (c) of a
      charged section is read as commercial quantity, clause (A) as small quantity (not reached); anything else is CHECK.
    * UAPA s.43D(5): applies to offences under Chapters IV and VI only, and the test is "prima facie true", not twin conditions. The sections of those
      chapters come from the `uapa_chapter_iv_vi_sections` parameter (configs/rights_rules.yaml); the store holds only s.43D, so until a person fills it
      in every UAPA charge is CHECK.
    * PMLA s.45(1): twin conditions for an offence under the Act; the proviso exempts a person under sixteen, a woman, the sick or infirm, and
      money-laundering of less than one crore rupees, if the Special Court so directs.
    """

    rule_id = RightsCheckName.STATUTORY_BAR
    rule_text = (
        "NDPS s.37(1)(b): twin conditions (Public Prosecutor heard; reasonable grounds to believe not guilty and not likely to offend on bail) for s.19, s.24, s.27A and offences involving commercial quantity only. "
        "UAPA s.43D(5): for offences under Chapters IV and VI only; no bail if the Court finds the accusation prima facie true (not the twin-conditions test). "
        "PMLA s.45(1): twin conditions for an offence under the Act; the proviso lets the Special Court exempt a person under sixteen, a woman, the sick or infirm, and money-laundering under one crore rupees. "
        "Where the section, quantity or chapter is not known the answer is CHECK."
    )
    sources = ["NDPS s.37", "UAPA s.43D(5)", "PMLA s.45"]
    rule_cite = "NDPS s.37; UAPA s.43D(5); PMLA s.45"
    last_verified = None  # reviewed against docs/qa/rights-verification.md; stays unverified until a person re-checks the corrected rule
    allowed_statuses = [RightsStatus.BAR_APPLIES, RightsStatus.NOT_APPLICABLE, RightsStatus.CHECK]

    def evaluate(self, inputs: RuleInputs) -> RightsCheckResult:
        """Evaluate 'statutory_bar'. Allowed statuses: BAR_APPLIES, NOT_APPLICABLE, CHECK. Output must include the rule text, source and dates used.

        Args:
            inputs: see behaviour

        Returns:
            RightsCheckResult.
        """
        uses = ["sections", "special_act"]
        chapters = {str(x).upper() for x in self.params.get("uapa_chapter_iv_vi_sections", [])}
        bars: list[str] = []
        unsure: list[str] = []
        for sec in charged_sections(inputs):
            if sec.act not in BARRING_ACTS:
                continue
            verdict, note = _judge(sec, chapters)
            (bars if verdict == _BAR else unsure if verdict == _UNSURE else []).append(note)
        if bars:
            extra = f" Also to check: {' '.join(unsure)}" if unsure else ""
            return self.result(
                RightsStatus.BAR_APPLIES,
                f"{' '.join(bars)} If the arrest breached Art. 22(1), see the grounds_of_arrest check (Vihaan Kumar).{extra}",
                uses,
            )
        if unsure:
            return self.result(RightsStatus.CHECK, " ".join(unsure), uses)
        if any(sec.act in BARRING_ACTS for sec in charged_sections(inputs)):
            return self.result(
                RightsStatus.NOT_APPLICABLE,
                "The NDPS section charged is a small-quantity clause, which NDPS s.37(1)(b) does not reach.",
                uses,
            )
        return self.result(RightsStatus.NOT_APPLICABLE, "No NDPS, UAPA or PMLA section is charged.", uses)


def _judge(sec: ChargedSection, uapa_chapters: set[str]) -> tuple[str, str]:
    """(bar | check | none, explanation) for one charged section of NDPS, UAPA or PMLA."""
    label = f"{sec.act} {sec.number or ''}{sec.clause}".strip()
    if sec.act == "PMLA":
        return _BAR, (
            f"{label}: PMLA s.45(1) twin conditions apply to an offence under the Act; the proviso lets the Special Court exempt a person under sixteen, "
            "a woman, the sick or infirm, and money-laundering under one crore rupees."
        )
    if sec.act == "UAPA":
        in_chapter = sec.number is not None and (sec.number in uapa_chapters)
        if in_chapter:
            return _BAR, (
                f"{label}: UAPA s.43D(5) applies (Chapters IV and VI): no bail if, on the case diary or the s.173 report, the accusation is prima facie true. "
                "This is not the twin-conditions test."
            )
        return _UNSURE, (
            f"{label}: UAPA s.43D(5) applies only to offences under Chapters IV and VI, and the test is whether the accusation is prima facie true. "
            "Check which chapter the section charged falls in."
        )
    if sec.number in NDPS_ALWAYS or sec.ndps_quantity == "commercial":
        return _BAR, (
            f"{label}: NDPS s.37(1)(b) twin conditions apply (s.19, s.24, s.27A, or commercial quantity): the Public Prosecutor must be heard and the court "
            "must find reasonable grounds to believe the accused is not guilty and not likely to offend on bail."
        )
    if sec.ndps_quantity == "small":
        return _NONE, ""
    return _UNSURE, (
        f"{label}: NDPS s.37(1)(b) reaches only s.19, s.24, s.27A and commercial quantity; the quantity involved is not on record, so check it."
    )
