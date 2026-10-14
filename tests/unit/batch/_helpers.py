"""Builders for the batch-desk tests: hand-made RightsReports, dossiers with a custody length, and spec -> TriageCard."""

from __future__ import annotations

from tests.fakes.data import load_dossier, load_rights_report
from vakeel_sahayak.agents.pairokar.triage import make_card
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport
from vakeel_sahayak.schemas.triage import TriageCard

# Rights Radar texts. ASSUMPTION (the skeleton has no structured field): days-left / days-past are read from the
# RightsCheckResult.detail text, as "opens in N days" and "N days past".
DEFAULT_OPEN = ("ELIGIBLE", "No charge sheet by day 61 (60-day limit). The default-bail window is open: 12 days past the limit.")
DEFAULT_SOON = ("NOT_YET", "Default-bail window opens in 3 days.")
DEFAULT_CLOSED = (
    "WINDOW_CLOSED",
    "60-day limit (maximum 7 years). The charge sheet was filed on day 74 (02.11.2024). Default bail was available on days 61-73.",
)
DEFAULT_NONE = ("CHECK", "Dates not on record.")
S479_CROSSED_48 = ("ELIGIBLE", "Custody has crossed the s.479 threshold of 852 days: 48 days past the threshold.")
S479_CROSSED_5 = ("ELIGIBLE", "Custody has crossed the s.479 threshold of 852 days: 5 days past the threshold.")
S479_NONE = ("CHECK", "Antecedents unknown.")


def rights(default_bail=DEFAULT_NONE, undertrial=S479_NONE, bar: bool = False, case_id: str = "case-X") -> RightsReport:
    """A RightsReport with the given default-bail / undertrial results; other checks neutral (as in case-0007)."""
    base = load_rights_report()
    checks = []
    for c in base.checks:
        if c.check is RightsCheckName.DEFAULT_BAIL:
            c = RightsCheckResult(check=c.check, status=RightsStatus(default_bail[0]), detail=default_bail[1], rule="BNSS s.187(3)")
        elif c.check is RightsCheckName.UNDERTRIAL_LIMIT:
            c = RightsCheckResult(check=c.check, status=RightsStatus(undertrial[0]), detail=undertrial[1], rule="BNSS s.479")
        elif c.check is RightsCheckName.STATUTORY_BAR:
            c = RightsCheckResult(
                check=c.check,
                status=RightsStatus.BAR_APPLIES if bar else RightsStatus.NOT_APPLICABLE,
                rule="NDPS s.37; UAPA s.43D(5); PMLA s.45",
            )
        checks.append(c)
    return RightsReport(case_id=case_id, as_of=base.as_of, checks=checks)


def dossier_with(custody_days: int | None, case_id: str = "case-X") -> CaseDossier:
    """case-0007's dossier with another case id and custody length."""
    d = load_dossier().model_copy(deep=True)
    d.case_id = case_id
    d.fields.custody_days.value = custody_days
    return d


def card(case_id, default_bail=DEFAULT_NONE, undertrial=S479_NONE, custody=100, missing=(), bar=False) -> TriageCard:
    """A card built the real way (Pairokar.make_card from a RightsReport and a dossier)."""
    return make_card(case_id, rights(default_bail, undertrial, bar, case_id), dossier_with(custody, case_id), list(missing))


def hand_card(case_id, rank=0, reasons=(), flags=(), missing=()) -> TriageCard:
    """A hand-written card (independent of make_card), for scheduler tests."""
    return TriageCard(case_id=case_id, urgency_rank=rank, reasons=list(reasons), flags=list(flags), missing_docs=list(missing))
