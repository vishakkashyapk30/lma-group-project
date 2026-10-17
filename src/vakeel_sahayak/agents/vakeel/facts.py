"""What Vakeel may say about the case: the approved dossier (or, under A1, the raw facts text) as citable facts (plan §8.1, §7.1).

Every fact has a dossier field name, a plain sentence read off the field's value, its status and the hash of its value
(the hash Peshkar's change detection uses, so a claim's `depends_on` lines up with a ChangeSet). A field the papers do not
state (UNSUPPORTED, no value) is not offered as a fact at all. A USER_STATED fact carries the fixed label
`PER_COUNSEL`: counsel told the system, the record does not show it (plan §7.1, §8.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.rights_report import RightsReport

PER_COUNSEL = "per counsel, not on record"  # the label on a USER_STATED fact
FACTS_TEXT_FIELD = "facts_text"  # the pseudo-field A1 cites: the raw facts text, there being no dossier
CITABLE = (FieldStatus.VERIFIED, FieldStatus.COMPUTED, FieldStatus.USER_STATED, FieldStatus.USER_EDITED)  # an AMBIGUOUS field waits for counsel
FACT_FIELDS = (
    "fir", "offence_date", "sections", "arrest_date", "first_remand", "custody_days", "charge_sheet", "trial_stage",
    "previous_bail", "co_accused_bail", "antecedents", "personal",
)  # fmt: skip
# Dossier fields a factor's ground reads (also what the factor's argument is allowed to mention).
FACTOR_FIELDS: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("sections", "fir"),
    "custody_period": ("custody_days", "arrest_date", "first_remand", "sections"),
    "charge_sheet_filed": ("charge_sheet", "custody_days", "sections"),
    "trial_delay": ("trial_stage", "charge_sheet", "custody_days"),
    "parity_with_co_accused": ("co_accused_bail", "sections"),
    "antecedents": ("antecedents",),  # an earlier bail application is disclosed in the application, not argued here
    "flight_risk": ("personal",),
    "witness_tampering": ("trial_stage", "charge_sheet"),
    "weak_prima_facie": ("fir", "sections", "offence_date"),
    "health_age_family": ("personal",),
    "statutory_bar": ("sections",),
    "undertrial_period": ("custody_days", "arrest_date", "sections"),
}
# The timeline label-field (ingestion.events.field_of_label) behind each dossier field: which events a fact rests on.
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "fir": ("fir_date",),
    "offence_date": ("offence_date",),
    "arrest_date": ("arrest_date",),
    "first_remand": ("first_remand", "remand"),
    "custody_days": ("arrest_date", "first_remand"),
    "charge_sheet": ("charge_sheet_date",),
    "previous_bail": ("bail_outcome",),
    "co_accused_bail": ("bail_outcome",),
}
# Rights Radar checks a factor's ground reads.
FACTOR_RIGHTS: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("antil_category",),
    "custody_period": ("default_bail", "undertrial_limit"),
    "charge_sheet_filed": ("default_bail",),
    "trial_delay": ("undertrial_limit",),
    "statutory_bar": ("statutory_bar",),
    "undertrial_period": ("undertrial_limit",),
}


_HASH_IMPL: list[Any] = []


def hash_value(value: Any) -> str:
    """Stable short hash 'h:3f2a' of a dossier value (plan §10): truth_maintenance's own once it is built, else the same format here."""
    if not _HASH_IMPL:
        try:
            from vakeel_sahayak.truth_maintenance.dependencies import hash_value as theirs

            theirs(None)
            _HASH_IMPL.append(theirs)
        except NotImplementedError:
            import hashlib
            import json

            _HASH_IMPL.append(lambda v: "h:" + hashlib.sha256(json.dumps(v, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()[:4])
    return _HASH_IMPL[0](value)


def value_hashes(fields: list[str], dossier: CaseDossier | None, facts_text: str | None = None) -> dict[str, str]:
    """`depends_on.facts`: each cited field with the hash of its dossier value (the JSON-mode value of the tracked field)."""
    out: dict[str, str] = {}
    dumped = dossier.fields.model_dump(mode="json") if dossier is not None else {}
    for f in fields:
        if f in out:
            continue
        if f == FACTS_TEXT_FIELD:
            out[f] = hash_value(re.sub(r"\s+", " ", facts_text or "").strip())
        elif f in dumped:
            out[f] = hash_value(dumped[f].get("value"))
    return out


@dataclass
class Fact:
    """One citable fact: `[F:field]` in a sentence points here."""

    field: str
    text: str  # one plain sentence (no capital-letter names that the value does not hold)
    status: str  # a FieldStatus value, or 'facts_text'
    hash: str
    per_counsel: bool = False  # USER_STATED: not on record, counsel's word

    def payload(self) -> dict[str, Any]:
        """What a model call sees of the fact."""
        return {"field": self.field, "text": self.text, "status": self.status, "per_counsel": self.per_counsel}


def ddmmyyyy(iso: str | None) -> str:
    """'2024-12-05' as '05.12.2024' (anything else as it is)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso or "").strip())
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else str(iso or "")


def section_ref(sv: Any) -> str:
    """'BNS 318(4)' (with ' (equivalent to IPC 420)' when the concordance gave one) for a SectionValue."""
    base = f"{sv.code} {sv.section}".strip() if sv.code and sv.section else sv.as_written
    return f"{base} (equivalent to {sv.equivalent})" if sv.equivalent else base


def _list(items: list[str]) -> str:
    items = [str(i).strip().rstrip(".") for i in items if str(i).strip()]
    return items[0] if len(items) == 1 else "; ".join(items)


def phrase(field: str, value: Any) -> str | None:
    """The sentence a dossier value reads as (None when the value says nothing)."""
    if value is None:
        return None
    if field == "fir":
        parts = [f"FIR number {value.number}" if value.number else "", f"police station {value.police_station}" if value.police_station else "",
                 f"dated {ddmmyyyy(value.date)}" if value.date else ""]  # fmt: skip
        body = ", ".join(p for p in parts if p)
        return f"The FIR is registered: {body}" if body else None
    if field == "offence_date":
        return f"The offence is alleged to have taken place on {ddmmyyyy(value)}"
    if field == "sections":
        rows = []
        for sv in value:
            bail = "bailable" if sv.bailable else "not bailable" if sv.bailable is False else None
            extra = ", ".join(x for x in (bail, f"maximum punishment {sv.max_punishment}" if sv.max_punishment else None) if x)
            rows.append(f"{section_ref(sv)}" + (f" ({extra})" if extra else ""))
        return ("The applicant is charged under " + "; ".join(rows)) if rows else None
    if field == "arrest_date":
        return f"The applicant was arrested on {ddmmyyyy(value)}"
    if field == "first_remand":
        return f"The applicant was first remanded to custody on {ddmmyyyy(value)}"
    if field == "custody_days":
        return f"The applicant has been in custody for {int(value)} days"
    if field == "charge_sheet":
        if value.filed:
            return "The charge sheet has been filed" + (f" on {ddmmyyyy(value.date)}" if value.date else "")
        return "The charge sheet has not been filed"
    if field == "trial_stage":
        return f"The stage of the case is: {value}"
    if field == "previous_bail":
        rows = [f"{b.court}, {ddmmyyyy(b.date)}: {b.outcome}" for b in value]
        return ("An earlier bail application was decided: " + "; ".join(rows)) if rows else "No earlier bail application is on record"
    if field == "co_accused_bail":
        rows = [f"{c.id} bail {c.outcome}" + (f" on {ddmmyyyy(c.date)}" if c.date else "") for c in value]
        return "; ".join(rows) if rows else None
    if field == "antecedents":
        return f"Antecedents: {_list(value)}" if value else "No antecedents are stated"
    if field == "personal":
        return f"Personal circumstances: {_list(value)}" if value else None
    return None


def facts_of(dossier: CaseDossier | None) -> dict[str, Fact]:
    """Citable facts of the approved dossier, by field name (fields the papers do not state are left out)."""
    out: dict[str, Fact] = {}
    if dossier is None:
        return out
    hashes = value_hashes(list(FACT_FIELDS), dossier)
    for name in FACT_FIELDS:
        tracked = getattr(dossier.fields, name)
        if tracked.value is None or tracked.status not in CITABLE:
            continue
        text = phrase(name, tracked.value)
        if text:
            out[name] = Fact(name, text, tracked.status.value, hashes[name], per_counsel=tracked.status == FieldStatus.USER_STATED)
    return out


def text_fact(facts_text: str | None) -> dict[str, Fact]:
    """A1: the raw facts text as the one citable fact `facts_text`."""
    body = re.sub(r"\s+", " ", facts_text or "").strip()
    return {FACTS_TEXT_FIELD: Fact(FACTS_TEXT_FIELD, body, FACTS_TEXT_FIELD, hash_value(body))} if body else {}


def quote_of(dossier: CaseDossier | None, field: str) -> str:
    """The source quote the dossier holds for a field (English for a Hindi quote), '' when there is none."""
    if dossier is None or field not in FACT_FIELDS:
        return ""
    src = getattr(dossier.fields, field).source
    return (src.quote_en or src.quote or "") if src is not None else ""


def rights_lines(rights: RightsReport | None, checks: tuple[str, ...] | None = None) -> list[dict[str, str]]:
    """Radar entries as plain rows (check, status, detail, rule); `checks` narrows to some of them."""
    rows = []
    for c in (rights.checks if rights is not None else []):
        if checks is not None and c.check.value not in checks:
            continue
        rows.append({"check": c.check.value, "status": c.status.value, "detail": c.detail or "", "rule": c.rule or ""})
    return rows
