"""Step 1 of the loop: mark each of the 12 factors favourable, adverse or not applicable, with a reason (plan §6.2).

The decision is read off the approved dossier and the RightsReport by rules, so it is reproducible and every reason
names the field or Radar check it rests on. A factor is *favourable* when the case gives counsel something to argue,
*adverse* when the State is likely to raise it and counsel must answer it, and *not applicable* when the contract's
`applies_if` does not hold or the dossier does not say. Under A1 (no dossier) the same rules read the raw facts text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import Factor, FactorStance, FieldStatus, RightsCheckName
from vakeel_sahayak.schemas.rights_report import RightsReport

FAV, ADV, NA = FactorStance.FAVOURABLE, FactorStance.ADVERSE, FactorStance.NOT_APPLICABLE
_STATED = (FieldStatus.VERIFIED, FieldStatus.USER_STATED, FieldStatus.USER_EDITED, FieldStatus.COMPUTED)
SPECIAL_BAR = {"NDPS": "NDPS s.37", "UAPA": "UAPA s.43D(5)", "PMLA": "PMLA s.45"}
LONG_CUSTODY_DAYS = 60  # custody counted as long enough to argue (the shortest default-bail limit, plan §7.3)
LONG_TRIAL_CUSTODY_DAYS = 90
_YEARS = re.compile(r"(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)
_ROOTS = re.compile(r"\b(?:family|wife|husband|mother|father|son|daughter|parents?|children|resident|resides?|lives?|address|employ|job|work|business|shop|student|farmer|native|settled)", re.IGNORECASE)
_HEALTH = re.compile(r"\b(?:medical|ill|illness|disease|diabet|cancer|surgery|hospital|disab|pregnan|age|aged|elderly|senior|woman|women|female|minor|dependent|cardiac|tb\b|treatment)", re.IGNORECASE)
_NO_ANTECEDENTS = re.compile(r"\b(?:no|nil|none|clean|first[\s-]time)\b", re.IGNORECASE)
_WITNESS = re.compile(r"witness(?:es)?\s+(?:have\s+been\s+|were\s+|are\s+)?examined|evidence\s+(?:has\s+)?(?:commenced|begun)|trial\s+(?:has\s+)?(?:commenced|begun|started)", re.IGNORECASE)
_NOT_PROGRESSED = re.compile(r"not\s+(?:yet\s+)?(?:been\s+)?framed|yet\s+to\s+be\s+framed|pending|not\s+commenced|not\s+begun|investigation", re.IGNORECASE)


@dataclass
class CaseSignals:
    """What the picker reads off the case (fields the papers do not state stay None)."""

    sections: list[dict[str, Any]] = field(default_factory=list)  # {ref, equivalent, code, bailable, max_punishment}
    custody_days: int | None = None
    arrest_date: str | None = None
    charge_sheet_filed: bool | None = None
    charge_sheet_date: str | None = None
    trial_stage: str | None = None
    co_accused: list[dict[str, Any]] = field(default_factory=list)
    antecedents: list[str] | None = None
    antecedents_stated: bool = False
    personal: list[str] = field(default_factory=list)
    fir_known: bool = False
    rights: dict[str, tuple[str, str]] = field(default_factory=dict)  # check -> (status, detail)
    source: str = "dossier"
    as_of: str | None = None  # the date the dossier (and the Rights Radar) was counted to

    @property
    def refs(self) -> list[str]:
        """Section references of the case in both codes: the section family of a search ('BNS 318(4)', 'IPC 420')."""
        out: list[str] = []
        for s in self.sections:
            for r in (s.get("ref"), s.get("equivalent")):
                if r and r not in out:
                    out.append(r)
        return out

    @property
    def codes(self) -> set[str]:
        return {str(s.get("code") or "").upper() for s in self.sections}


def _stated(tracked: Any) -> Any:
    """The value of a TrackedField when counsel or the papers state it (VERIFIED, COMPUTED, USER_*), else None."""
    if tracked is None or tracked.value is None or tracked.status not in _STATED:
        return None
    return tracked.value


def _ref(code: str | None, section: str | None) -> str | None:
    if not code or not section:
        return None
    try:
        from vakeel_sahayak.pipelines.concordance.refs import make_ref

        return make_ref(code, section)
    except ValueError:
        return f"{code} {section}"


def signals_from_dossier(dossier: CaseDossier | None, rights: RightsReport | None) -> CaseSignals:
    """Case signals from the approved dossier and the RightsReport."""
    sig = CaseSignals()
    if dossier is not None:
        sig.as_of = dossier.as_of or (rights.as_of if rights is not None else None)  # a dossier folded from the log carries no date; the Rights Radar was counted to one
        f = dossier.fields
        for s in (f.sections.value or []) if f.sections.status != FieldStatus.UNSUPPORTED else []:
            sig.sections.append(
                {
                    "ref": _ref(s.code, s.section) or s.as_written,
                    "equivalent": s.equivalent,
                    "code": s.code,
                    "bailable": s.bailable,
                    "max_punishment": s.max_punishment,
                }
            )
        days, cs = _stated(f.custody_days), _stated(f.charge_sheet)
        sig.custody_days = int(days) if days is not None else None
        sig.arrest_date = _stated(f.arrest_date)
        if cs is not None:
            sig.charge_sheet_filed, sig.charge_sheet_date = bool(cs.filed), cs.date
        sig.trial_stage = _stated(f.trial_stage)
        sig.co_accused = [c.model_dump() for c in (_stated(f.co_accused_bail) or [])]
        ante = _stated(f.antecedents)
        sig.antecedents, sig.antecedents_stated = (list(ante) if ante is not None else None), ante is not None
        sig.personal = [str(p) for p in (_stated(f.personal) or [])]
        sig.fir_known = _stated(f.fir) is not None
    if rights is not None:
        for c in rights.checks:
            sig.rights[c.check.value] = (str(getattr(c.status, "value", c.status)), c.detail or "")
    return sig


def signals_from_text(text: str | None, before: str | None, rights: RightsReport | None) -> CaseSignals:
    """Case signals from the raw facts text (A1: no dossier); only what the order-facts rules can read."""
    sig = signals_from_dossier(None, rights)
    sig.source = "facts_text"
    if not text:
        return sig
    from vakeel_sahayak.pipelines.order_facts import charge_sheet_status, co_accused_outcome, custody_days
    from vakeel_sahayak.pipelines.section_extract import charged_sections, extract_sections

    for ref in charged_sections(extract_sections(text)):
        sig.sections.append({"ref": ref, "equivalent": None, "code": ref.split()[0], "bailable": None, "max_punishment": None})
    status, outcome = charge_sheet_status(text), co_accused_outcome(text)
    sig.charge_sheet_filed = None if status is None else status == "filed"
    if outcome:
        sig.co_accused = [{"id": "co-accused", "outcome": outcome, "date": None}]
    sig.custody_days = custody_days(text, before)
    sig.fir_known = bool(re.search(r"\bFIR\b", text))
    sig.personal = [m.group(0) for m in re.finditer(r"[^.]*\b(?:family|wife|mother|medical|illness|aged?)\b[^.]*\.", text, re.IGNORECASE)][:3]
    return sig


def max_years(sig: CaseSignals) -> int | None:
    """Longest maximum punishment of the charged sections in years (life or death count as 99 and 100)."""
    best: int | None = None
    for s in sig.sections:
        text = str(s.get("max_punishment") or "")
        years = [int(m) for m in _YEARS.findall(text)]
        value = 100 if re.search(r"death", text, re.I) else 99 if re.search(r"life", text, re.I) else (max(years) if years else None)
        if value is not None:
            best = value if best is None else max(best, value)
    return best


def _right(sig: CaseSignals, name: RightsCheckName) -> tuple[str, str] | None:
    return sig.rights.get(name.value)


def pick_stances(sig: CaseSignals) -> list[tuple[Factor, FactorStance, str]]:
    """Stance and reason for every factor, in Appendix A order (rules over `CaseSignals`)."""
    out: dict[Factor, tuple[FactorStance, str]] = {}
    where = "the facts text" if sig.source == "facts_text" else "the dossier"

    # 1 gravity and punishment: always applies
    years = max_years(sig)
    if sig.sections and all(s.get("bailable") for s in sig.sections):
        out[Factor.GRAVITY_AND_PUNISHMENT] = (FAV, "every charged section is bailable (dossier: sections)")
    elif years is not None and years <= 7:
        out[Factor.GRAVITY_AND_PUNISHMENT] = (FAV, f"maximum punishment up to {years} years: the Antil / Arnesh Kumar category (dossier: sections)")
    elif years is not None:
        out[Factor.GRAVITY_AND_PUNISHMENT] = (ADV, f"maximum punishment above 7 years ({years}): the State will rely on gravity (dossier: sections)")
    else:
        out[Factor.GRAVITY_AND_PUNISHMENT] = (ADV, f"gravity applies to every bail application and {where} gives no maximum punishment: to be answered")

    # 2 custody period
    days = sig.custody_days
    if days is None:
        out[Factor.CUSTODY_PERIOD] = (NA, "custody days are not established")
    elif days >= LONG_CUSTODY_DAYS:
        out[Factor.CUSTODY_PERIOD] = (FAV, f"{days} days in custody (dossier: custody_days)")
    else:
        out[Factor.CUSTODY_PERIOD] = (NA, f"custody of {days} days is short")

    # 3 charge sheet
    if sig.charge_sheet_filed:
        when = f" on {sig.charge_sheet_date}" if sig.charge_sheet_date else ""
        out[Factor.CHARGE_SHEET_FILED] = (FAV, f"charge sheet filed{when}: investigation is complete (dossier: charge_sheet)")
    else:
        out[Factor.CHARGE_SHEET_FILED] = (NA, "no charge sheet is stated as filed" if sig.charge_sheet_filed is None else "charge sheet not filed yet")

    # 4 trial delay
    stage = sig.trial_stage or ""
    if sig.charge_sheet_filed and stage and _NOT_PROGRESSED.search(stage) and (days or 0) >= LONG_TRIAL_CUSTODY_DAYS:
        out[Factor.TRIAL_DELAY] = (FAV, f"trial stage '{stage}' after {days} days in custody (dossier: trial_stage)")
    else:
        out[Factor.TRIAL_DELAY] = (NA, "trial stage is not stated or the trial is progressing" if stage else "trial stage is not stated")

    # 5 parity
    granted = [c for c in sig.co_accused if "grant" in str(c.get("outcome", "")).lower()]
    if granted:
        out[Factor.PARITY_WITH_CO_ACCUSED] = (FAV, f"{granted[0].get('id', 'a co-accused')} was granted bail (dossier: co_accused_bail)")
    else:
        out[Factor.PARITY_WITH_CO_ACCUSED] = (NA, "no co-accused is stated as granted bail")

    # 6 antecedents: always applies
    ante = sig.antecedents
    if ante is not None and (not ante or all(_NO_ANTECEDENTS.search(a) for a in ante)):
        out[Factor.ANTECEDENTS] = (FAV, "no antecedents stated (dossier: antecedents)")
    elif ante:
        out[Factor.ANTECEDENTS] = (ADV, "other cases are stated against the accused: the State will raise them (dossier: antecedents)")
    else:
        out[Factor.ANTECEDENTS] = (ADV, "antecedents are not established: ask counsel; the State will raise them")

    # 7 flight risk: always applies
    roots = [p for p in sig.personal if _ROOTS.search(p)]
    if roots:
        out[Factor.FLIGHT_RISK] = (FAV, "roots in the community are stated (dossier: personal)")
    else:
        out[Factor.FLIGHT_RISK] = (ADV, "no roots in the community are stated and the State is likely to allege flight risk")

    # 8 witness tampering
    if _WITNESS.search(stage):
        out[Factor.WITNESS_TAMPERING] = (FAV, "key witnesses have been examined, so tampering is less open (dossier: trial_stage)")
    elif sig.charge_sheet_filed is False or (sig.charge_sheet_filed is None and sig.sections):
        out[Factor.WITNESS_TAMPERING] = (ADV, "the investigation or trial is at an early stage: the State may allege tampering")
    else:
        out[Factor.WITNESS_TAMPERING] = (NA, "no tampering risk arises from the stage stated")

    # 9 weak prima facie: needs the FIR and the sections side by side
    if sig.fir_known and sig.sections:
        out[Factor.WEAK_PRIMA_FACIE] = (FAV, "the FIR allegations can be read against the sections charged (dossier: fir, sections)")
    else:
        out[Factor.WEAK_PRIMA_FACIE] = (NA, "the FIR or the sections are not established")

    # 10 health, age, gender, family
    papers = [p for p in sig.personal if _HEALTH.search(p)]
    if papers:
        out[Factor.HEALTH_AGE_FAMILY] = (FAV, "medical, age, gender or family circumstances are stated (dossier: personal)")
    else:
        out[Factor.HEALTH_AGE_FAMILY] = (NA, "no medical or personal papers are on file")

    # 11 statutory bar
    bar = _right(sig, RightsCheckName.STATUTORY_BAR)
    special = [SPECIAL_BAR[c] for c in sig.codes if c in SPECIAL_BAR]
    if special or (bar and bar[0] == "FLAG"):
        named = ", ".join(special) if special else "a special-act bar"
        out[Factor.STATUTORY_BAR] = (ADV, f"{named} is charged: the twin conditions must be answered (RightsReport: statutory_bar)")
    else:
        out[Factor.STATUTORY_BAR] = (NA, "no special-act bar section is charged")

    # 12 BNSS s.479 / CrPC s.436A
    ut = _right(sig, RightsCheckName.UNDERTRIAL_LIMIT)
    if ut and ut[0] == "ELIGIBLE":
        out[Factor.UNDERTRIAL_PERIOD] = (FAV, f"the s.479 / s.436A threshold is reached (RightsReport: undertrial_limit). {ut[1]}".strip())
    elif ut and ut[0] == "NOT_YET":
        out[Factor.UNDERTRIAL_PERIOD] = (NA, f"the s.479 / s.436A threshold is not reached yet (RightsReport: undertrial_limit). {ut[1]}".strip())
    else:
        out[Factor.UNDERTRIAL_PERIOD] = (NA, "the Rights Radar has not judged the undertrial limit")
    return [(f, *out[f]) for f in Factor]
