"""Which act a charged section belongs to, and the special-act facts the Rights Radar rules need.

Everything here is taken from docs/qa/rights-verification.md (HA-03) and the statute store; nothing is added from memory:

* UAPA s.43D(2): every offence takes the 90-day limit of CrPC s.167(2) (BNSS s.187(3)); the Court may extend it to 180 days on the Public
  Prosecutor's report.
* NDPS s.36A(4): the limit is 180 days for an offence under s.19, s.24 or s.27A and for offences involving commercial quantity; the Special
  Court may extend it to one year.
* NDPS s.37(1)(b): the twin conditions reach s.19, s.24, s.27A and offences involving commercial quantity.
* The quantity clause of an NDPS section is read from the charged-section text: clause (c) is commercial quantity (the doc's NDPS s.21(c)
  example), clause (A) small quantity (the doc's NDPS s.20(b)(ii)(A) example), clause (b) is not stated by the doc and counts as unknown for the
  bar and as an ordinary-limit case for default bail (the Kerala NDPS s.22(b) ruling in the doc takes 60 days). Whether this mapping holds for
  every NDPS section is a person task (docs/handoff/rights-fixes.md).
* UAPA s.43D(5) reaches only Chapters IV and VI; the store holds only s.43D, so which UAPA sections fall in those chapters is read from the
  optional `uapa_chapter_iv_vi_sections` parameter of configs/rights_rules.yaml (empty until a person fills it from the bare act).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vakeel_sahayak.rights.inputs import RuleInputs

GENERAL_ACTS = frozenset({"IPC", "BNS", "CRPC", "BNSS"})
PRE_BNSS_ACTS = frozenset({"IPC", "CRPC"})
BNSS_DATE = "2024-07-01"  # BNSS, BNS and BSA came into force on 1 July 2024

_ALIASES = {
    "UA(P)A": "UAPA", "UAP": "UAPA", "UNLAWFULACTIVITIES": "UAPA",
    "NDPSACT": "NDPS", "PMLAACT": "PMLA", "PMLA2002": "PMLA",
    "COMPANIES": "COMPANIES", "COMPANIESACT": "COMPANIES",
}  # fmt: skip
_SECTION = re.compile(r"^\s*(?P<act>.*?)\s*(?:s\.|sec\.|section)?\s*(?P<number>\d+[A-Za-z]{0,2})\s*(?P<clause>(?:\([^)]*\)\s*)*)\s*$", re.IGNORECASE)

NDPS_ALWAYS = frozenset({"19", "24", "27A"})  # NDPS s.36A(4) and s.37(1)(b)
ORDINARY_DAYS_AFTER_EXTENSION = {"UAPA": 180, "NDPS": 365}


@dataclass(frozen=True)
class ChargedSection:
    """A charged section split into act key, main section number and sub-clauses, e.g. NDPS / 20 / '(b)(ii)(A)'."""

    act: str
    number: str | None
    clause: str = ""

    @property
    def ndps_quantity(self) -> str | None:
        """'small', 'intermediate', 'commercial' or None when the section text carries no quantity clause (see the module docstring)."""
        groups = [g.strip().lower() for g in re.findall(r"\(([^)]*)\)", self.clause)]
        if self.act != "NDPS" or not groups:
            return None
        last = groups[-1]
        if last not in ("a", "b", "c"):
            return None
        if self.number == "20" and len(groups) < 3:  # s.20(a) and s.20(b)(i) are not quantity clauses
            return None
        return {"a": "small", "b": "intermediate", "c": "commercial"}[last]


def normalise_act(code: str) -> str:
    """Upper-case act key without spaces and the word Act: 'Arms Act' -> 'ARMS', 'ndps' -> 'NDPS'."""
    key = re.sub(r"\bact\b", "", code, flags=re.IGNORECASE)
    key = "".join(key.upper().split()).strip(".,")
    return _ALIASES.get(key, key)


def parse_section(text: str) -> ChargedSection:
    """Split a charged-section string such as 'NDPS 21(c)', 'UAPA 43D' or 'Arms Act 25'."""
    m = _SECTION.match(text or "")
    if not m:
        return ChargedSection(normalise_act(text or ""), None)
    return ChargedSection(normalise_act(m.group("act")), m.group("number").upper(), "".join(m.group("clause").split()))


def charged_sections(inputs: RuleInputs) -> list[ChargedSection]:
    """Every charged section, plus the special act on its own when the section list does not name it."""
    parsed = [parse_section(s) for s in inputs.sections]
    if inputs.special_act and normalise_act(inputs.special_act) not in {p.act for p in parsed}:
        parsed.append(ChargedSection(normalise_act(inputs.special_act), None))
    return parsed


def special_acts(inputs: RuleInputs) -> list[str]:
    """Act keys charged other than IPC, BNS, CrPC and BNSS, in order, without repeats."""
    seen: list[str] = []
    for s in charged_sections(inputs):
        if s.act and s.act not in GENERAL_ACTS and s.act not in seen:
            seen.append(s.act)
    return seen


@dataclass(frozen=True)
class SpecialLimit:
    """A special-act default-bail limit: `base` days, extendable by the Court to `extended_max` days."""

    base: int
    extended_max: int
    label: str
    certain: bool  # False: the charged NDPS section may or may not involve commercial quantity


def special_default_bail_limit(inputs: RuleInputs) -> SpecialLimit | None:
    """The longest special-act default-bail limit that applies, or may apply, to the charged sections (None for IPC/BNS-only cases)."""
    found: list[SpecialLimit] = []
    for s in charged_sections(inputs):
        if s.act == "UAPA":
            found.append(SpecialLimit(90, 180, "UAPA s.43D(2)", True))
        elif s.act == "NDPS":
            if s.number in NDPS_ALWAYS or s.ndps_quantity == "commercial":
                found.append(SpecialLimit(180, 365, "NDPS s.36A(4)", True))
            elif s.ndps_quantity in ("small", "intermediate"):
                continue  # the ordinary 60 or 90 days (doc: NDPS s.22(b) in the Kerala ruling)
            else:
                found.append(SpecialLimit(180, 365, "NDPS s.36A(4)", False))
    if not found:
        return None
    certain = [f for f in found if f.certain]
    return max(certain or found, key=lambda f: f.base)


def begun_after_bnss(inputs: RuleInputs) -> bool | None:
    """True if the case clearly began on or after 1 July 2024, False if before (an IPC/CrPC section or an earlier FIR, arrest or remand), None if unknown."""
    sections = charged_sections(inputs)
    if any(s.act in PRE_BNSS_ACTS for s in sections):
        return False
    dates = [d for d in (inputs.fir_date, inputs.arrest_date, inputs.first_remand) if d]
    if any(d < BNSS_DATE for d in dates):
        return False
    if any(s.act in ("BNS", "BNSS") for s in sections) or dates:
        return True
    return None
