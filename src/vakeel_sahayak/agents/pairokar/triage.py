"""Per-case triage card construction (plan §11).

`make_card` turns a case's Rights Radar report, dossier and missing documents into the card §11 shows: the urgency
reasons (from the fixed rule in `batch.urgency`), flags for counsel, the missing documents. The card carries no
other data. `urgency_rank` is set when the cards of a batch are ranked together and `next_step` when Pairokar decides.
"""

from __future__ import annotations

from vakeel_sahayak.batch.urgency import assess
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.triage import TriageCard

BAR_FLAG = "BAR: statutory bar applies (twin conditions)"  # prefix 'BAR:' is what re-prioritising looks for
OPEN_QUESTIONS_FLAG = "OPEN: {n} question(s) still open for counsel"
_LABELS = {
    RightsCheckName.DEFAULT_BAIL: "default-bail days cannot be counted",
    RightsCheckName.UNDERTRIAL_LIMIT: "s.479 threshold cannot be compared",
    RightsCheckName.NOTICE_OF_APPEARANCE: "notice of appearance",
    RightsCheckName.GROUNDS_OF_ARREST: "grounds of arrest",
    RightsCheckName.PRODUCTION_24H: "production within 24 hours",
    RightsCheckName.ANTIL_CATEGORY: "Antil category",
    RightsCheckName.STATUTORY_BAR: "statutory bar",
}
_CHECK_WORTHY = (RightsCheckName.DEFAULT_BAIL, RightsCheckName.UNDERTRIAL_LIMIT)  # a CHECK here changes urgency, so counsel sees it


def custody_days_of(dossier: CaseDossier | None, rights: RightsReport | None = None) -> int | None:
    """Days in custody as the dossier states or computes them (None when unknown)."""
    value = dossier.fields.custody_days.value if dossier is not None else None
    return int(value) if value is not None else None


def flags_for(rights: RightsReport | None, dossier: CaseDossier | None) -> list[str]:
    """Flags for counsel, in a fixed order: statutory bar, rights FLAGs, unknowns, open questions."""
    flags: list[str] = []
    if rights is not None:
        if (bar := rights.get(RightsCheckName.STATUTORY_BAR)) is not None and bar.status == RightsStatus.BAR_APPLIES:
            flags.append(BAR_FLAG)
        for check in rights.checks:
            if check.status == RightsStatus.FLAG:
                flags.append(f"FLAG: {_LABELS.get(check.check, check.check.value)}")
    if dossier is not None and dossier.fields.antecedents.value is None:
        flags.append("CHECK: antecedents unknown")
    if rights is not None:
        for check in rights.checks:
            if check.status == RightsStatus.CHECK and check.check in _CHECK_WORTHY:
                flags.append(f"CHECK: {_LABELS[check.check]}")
    if dossier is not None and dossier.open_questions:
        flags.append(OPEN_QUESTIONS_FLAG.format(n=len(dossier.open_questions)))
    return flags


def make_card(case_id: str, rights: RightsReport, dossier: CaseDossier, missing_docs: list[str]) -> TriageCard:
    """Build the card: urgency reasons, flags, missing documents.

    Args:
        case_id: the case
        rights: its Rights Radar report
        dossier: its dossier
        missing_docs: documents still missing (Munshi's gaps)

    Returns:
        TriageCard with urgency_rank 0 (set by ranking) and no next_step yet (set by Pairokar's decision).
    """
    missing = list(dict.fromkeys(missing_docs))
    urgency = assess(rights, custody_days_of(dossier, rights), missing)
    return TriageCard(
        case_id=case_id,
        urgency_rank=0,
        reasons=urgency.texts(),
        flags=flags_for(rights, dossier),
        missing_docs=missing,
        next_step=None,
    )
