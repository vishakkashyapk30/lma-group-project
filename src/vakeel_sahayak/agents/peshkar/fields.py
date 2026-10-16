"""The dossier fields as Peshkar reads them (plan §7.1): what each one is, where to look, how a value is stated back.

`FIELD_SPECS` gives, for each field the extractor reads, a query, a cue pattern (the sentences worth showing the
model, and the way a new document is matched to the fields it touches in change detection), and a one-line
description. `claim_text` turns a value into the plain sentence the NLI span check tests against the quote.
`coerce_value` validates one value against the field's declared type, so a malformed reply never reaches the dossier.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_core import to_jsonable_python

from vakeel_sahayak.pipelines.text_utils import split_sentences
from vakeel_sahayak.rights.day_count import format_dmy, parse_date
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import (
    ChargeSheetValue,
    CoAccusedBail,
    DossierFields,
    FirValue,
    PreviousBail,
    SectionValue,
)
from vakeel_sahayak.schemas.enums import FieldStatus

ALL_FIELDS: tuple[str, ...] = tuple(DossierFields.model_fields)
COMPUTED_FIELDS = ("custody_days",)
# Order of extraction: the offence date comes before the sections (the concordance needs it) and the arrest date before custody.
EXTRACTION_ORDER: tuple[str, ...] = (
    "fir", "offence_date", "arrest_date", "first_remand", "charge_sheet", "trial_stage", "previous_bail",
    "co_accused_bail", "antecedents", "personal", "parties", "sections",
)  # fmt: skip
DATE_FIELDS = ("offence_date", "arrest_date", "first_remand")
USER_STATUSES = (FieldStatus.USER_STATED, FieldStatus.USER_EDITED)
STATED_STATUSES = (FieldStatus.VERIFIED, FieldStatus.COMPUTED, FieldStatus.USER_STATED, FieldStatus.USER_EDITED)
PARTY_RANK = {"Accused": 0, "Co-accused": 1, "Complainant": 2, "IO": 3, "Witness": 4, "Person": 5}


class ExtractedItem(BaseModel):
    """One value the extractor read, with the sentence it came from."""

    value: Any = None
    quote: str | None = None
    doc: str | None = None
    page: int | None = None


class FieldExtraction(BaseModel):
    """The extractor's reply for one field (the schema of `peshkar.extract_field`)."""

    field: str = ""
    items: list[ExtractedItem] = Field(default_factory=list)
    none_stated: bool = False  # the papers say there is none (for example no criminal antecedents)
    none_quote: str | None = None


@dataclass(frozen=True)
class FieldSpec:
    """How one dossier field is read."""

    name: str
    kind: str  # 'scalar' (one value; two different values are a conflict) or 'list' (the values are collected)
    queries: tuple[str, ...]
    cue: re.Pattern[str]
    describe: str


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


FIELD_SPECS: dict[str, FieldSpec] = {
    s.name: s
    for s in (
        FieldSpec("fir", "scalar", ("FIR number police station date registered", "First Information Report"),
                  _c(r"\bF\.?I\.?R\.?\b|first\s+information\s+report|प्राथमिकी|police\s+station|\bP\.?S\.?\b"),
                  "A value is an object with number (like 112/2024), police_station and date (YYYY-MM-DD); use null for a part the quote does not state."),  # fmt: skip
        FieldSpec("offence_date", "scalar", ("date of the incident offence occurred", "alleged offence committed on"),
                  _c(r"incident|offence|occurrence|occurred|alleged\s+to\s+have|committed|घटना"),
                  "A value is the date of the alleged offence, as YYYY-MM-DD."),
        FieldSpec("arrest_date", "scalar", ("arrested on date of arrest", "arrest memo"),
                  _c(r"\barrest|गिरफ्?तार"),
                  "A value is the date the accused was arrested, as YYYY-MM-DD. Not the co-accused's arrest."),
        FieldSpec("first_remand", "scalar", ("first remand judicial custody produced before magistrate", "remand order"),
                  _c(r"remand|रिमांड|produced\s+before"),
                  "A value is the date of the first remand order, as YYYY-MM-DD."),
        FieldSpec("charge_sheet", "scalar", ("charge sheet filed final report investigation", "charge sheet not filed"),
                  _c(r"charge[\s-]?sheet|final\s+report|आरोपपत्र"),
                  "A value is an object with filed (true or false) and date (YYYY-MM-DD, or null when none is stated)."),
        FieldSpec("trial_stage", "scalar", ("charges framed trial stage evidence", "charges not framed investigation pending"),
                  _c(r"charges?\s+(?:have\s+|has\s+|were\s+|was\s+)?(?:not\s+|yet\s+|been\s+)*(?:framed|to\s+be\s+framed)|\btrial\b|evidence|investigation"),
                  "A value is a short phrase for the stage of the case, such as 'charges not framed'."),
        FieldSpec("previous_bail", "list", ("earlier bail application rejected granted", "bail rejected by sessions court"),
                  _c(r"\bbail\b|जमानत"),
                  "Each value is an object with court, date (YYYY-MM-DD) and outcome ('rejected' or 'granted') of an earlier bail decision for the accused."),
        FieldSpec("co_accused_bail", "list", ("co-accused granted bail", "co-accused bail rejected"),
                  _c(r"co[\s-]?accused"),
                  "Each value is an object with id (like Co-accused-1), outcome ('granted' or 'rejected') and date (YYYY-MM-DD or null)."),
        FieldSpec("antecedents", "list", ("criminal antecedents other pending cases", "no other case pending against the accused"),
                  _c(r"antecedent|criminal\s+history|other\s+(?:criminal\s+)?cases?|previous\s+cases?|prior\s+cases?|not\s+involved|clean\s+record"),
                  "Each value is one other case against the accused, as a short string. If the papers say there are none, set none_stated."),
        FieldSpec("personal", "list", ("family earning member health age dependents", "personal circumstances of the accused"),
                  _c(r"earning|family|\bwife\b|\bhusband\b|children|\baged?\b|\bsole\b|dependent|health|medical|illness|surgery|disabled|student|employed|resident"),
                  "Each value is one sentence about the accused's family, health, age or work, copied from the papers."),
        FieldSpec("parties", "list", ("accused complainant investigating officer witness", "co-accused"),
                  _c(r"\b(?:Accused|Co-accused|Complainant|IO|Witness|Person)-\d+\b"),
                  "Each value is a party alias such as Accused-1 or IO-1, exactly as written."),
        FieldSpec("sections", "list", ("sections charged IPC BNS offence", "registered under section"),
                  _c(r"\bsections?\b|\bu/s\b|\bs\.\s*\d|\b(?:IPC|BNSS?|CrPC|NDPS|UAPA|PMLA|POCSO)\b"),
                  "Each value is an object with as_written (like 'BNS 318(4)'), code (IPC, BNS, ...) and section ('318(4)')."),
    )
}
# Fields whose absence is put to counsel, in the order the questions are worth asking (the Rights Radar needs them most).
QUESTION_PRIORITY: tuple[str, ...] = ("antecedents", "arrest_date", "first_remand", "charge_sheet", "sections", "offence_date")


# ---------------------------------------------------------------------------------------------- text helpers

_WRAP = re.compile(r"<<<(?:END_)?UNTRUSTED_DOCUMENT_DATA [0-9a-f]+>>>\n?|^\[doc=[^\]]*\] The text between these markers[^\n]*\n", re.M)


def unwrap(text: str) -> str:
    """Document text out of a `wrap_untrusted` block (offline handlers read the data, never the markers)."""
    return _WRAP.sub("", text or "").strip()


def flat(text: str) -> str:
    """Whitespace collapsed to single spaces."""
    return " ".join((text or "").split())


def norm_key(text: str) -> str:
    """A comparison form of a quote or a passage: lower case, punctuation and spacing removed."""
    return " ".join(re.sub(r"[^\w]+", " ", text or "").lower().split())


def sentences(text: str) -> list[str]:
    """Sentences of a passage (whitespace flattened first)."""
    return split_sentences(flat(text))


def snippet(text: str, cue: re.Pattern[str], width: int = 1, limit: int = 1500) -> str:
    """The sentences of a passage that match the cue, with `width` sentences either side (what is shown to the model).

    Sentences that follow each other stay together; separate runs are divided by a blank line, so a quote taken from
    one run is always a verbatim stretch of the page.
    """
    sents = sentences(text)
    hits = [i for i, s in enumerate(sents) if cue.search(s)]
    if not hits:
        return flat(text)[:500]
    keep = sorted({j for i in hits for j in range(max(0, i - width), min(len(sents), i + width + 1))})
    runs: list[list[str]] = []
    last = -2
    for j in keep:
        if j != last + 1:
            runs.append([])
        runs[-1].append(sents[j])
        last = j
    return "\n\n".join(" ".join(run) for run in runs)[:limit]


def value_key(value: Any) -> str:
    """A stable key for a value (dicts, lists and pydantic models alike), to tell two readings of a field apart."""
    return json.dumps(to_jsonable_python(value, fallback=str), sort_keys=True, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------------------------- values


def _date(value: Any) -> str:
    parse_date(str(value))
    return str(value)


def coerce_value(name: str, value: Any) -> Any:
    """One value of a field as its declared type (JSON-able), or ValueError when the reply does not fit.

    Args:
        name: the field
        value: one item's value (for a list field, one element)

    Returns:
        The validated value.
    """
    try:
        if name in DATE_FIELDS:
            return _date(value)
        if name == "fir":
            v = FirValue.model_validate(value)
            if v.date:
                _date(v.date)
            return v.model_dump(mode="json")
        if name == "charge_sheet":
            v = ChargeSheetValue.model_validate(value)
            if v.date:
                _date(v.date)
            return v.model_dump(mode="json")
        if name == "sections":
            return SectionValue.model_validate(value).model_dump(mode="json")
        if name == "previous_bail":
            v = PreviousBail.model_validate(value)
            _date(v.date)
            return v.model_dump(mode="json")
        if name == "co_accused_bail":
            v = CoAccusedBail.model_validate(value)
            if v.date:
                _date(v.date)
            return v.model_dump(mode="json")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name}: {str(exc).splitlines()[0]}") from exc
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected a non-empty string")
    return value.strip()


def claim_text(name: str, value: Any, quote: str = "") -> str:
    """The value as a plain sentence, for the NLI span check against its quote (plan §7.1 `span_check`).

    Only what the value says goes in; a part the value leaves null is left out. A party alias is named only when the
    quote names it.
    """
    if name in DATE_FIELDS:
        return {"arrest_date": "Arrest on", "offence_date": "Offence on", "first_remand": "Remand on"}[name] + f" {value}"
    if name == "fir":
        parts = ["FIR"]
        if value.get("number"):
            parts.append(f"No. {value['number']}")
        if value.get("date"):
            parts.append(f"dated {value['date']}")
        if value.get("police_station"):
            parts.append(f"at {value['police_station']}")
        return " ".join(parts)
    if name == "charge_sheet":
        if not value.get("filed"):
            return "Charge sheet not filed"
        return "Charge sheet filed" + (f" on {value['date']}" if value.get("date") else "")
    if name == "sections":
        return f"Section {value['section']} of the {value['code']}"
    if name == "previous_bail":
        court = "" if value["court"].lower().startswith("court not stated") else f" by {value['court']}"
        return f"Bail {value['outcome']}{court} on {value['date']}"
    if name == "co_accused_bail":
        who = value["id"] if value["id"] and value["id"].lower() in (quote or "").lower() else "Co-accused"
        return f"{who} bail {value['outcome']}" + (f" on {value['date']}" if value.get("date") else "")
    return str(value)


def describe_value(name: str, value: Any) -> str:
    """A value for counsel: dates as dd.mm.yyyy, the rest as a short phrase (used in questions)."""
    if name in DATE_FIELDS:
        return format_dmy(value)
    if isinstance(value, dict):
        bits = []
        for k, v in value.items():
            if v in (None, ""):
                continue
            bits.append(format_dmy(v) if k == "date" and isinstance(v, str) and len(v) == 10 else str(v))
        return ", ".join(bits)
    return str(value)


def build_tracked(name: str, value: Any, source: SourceRef | None, status: FieldStatus) -> TrackedField[Any]:
    """A TrackedField holding the value as plain JSON (the models validate the status against the evidence).

    Values were checked by `coerce_value`; they stay dicts and lists here, and are typed when the log is folded.
    """
    return TrackedField[Any].model_validate(
        {"value": value, "source": source.model_dump() if source else None, "status": status.value}
    )


def merge_subsumed(values: list[Any]) -> list[Any]:
    """Drop an object value whose stated parts are all repeated by a fuller one (the same FIR or charge sheet read twice).

    Two readings that disagree on a part both state are different values, and both stay (a conflict for counsel).
    An exact duplicate keeps its first copy; non-object values pass through unchanged.
    """
    kept: list[Any] = []
    for i, v in enumerate(values):
        if isinstance(v, dict) and any(
            j != i and isinstance(w, dict) and _covers(w, v) and (w != v or j < i) for j, w in enumerate(values)
        ):
            continue
        kept.append(v)
    return kept


def _covers(big: dict[str, Any], small: dict[str, Any]) -> bool:
    """`big` states everything `small` states (and is equal to it or states more)."""
    return all(big.get(k) == val for k, val in small.items() if val not in (None, ""))


TASK_FIELD_NAMES: tuple[str, ...] = EXTRACTION_ORDER
