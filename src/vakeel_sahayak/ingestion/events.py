"""Dated events read from document text, with the field each one speaks to (plan §4.3 step 3, §4.4, §5.1).

An event has a `field`, the thing it dates, such as `arrest_date`. Conflict detection compares events of the same
single-valued field. Several remands or bail outcomes are normal, so `remand` and `bail_outcome` are multi-valued.
Dates come from `pipelines.order_facts.DATE_RE` and `normalise_date`; Devanagari digits and Hindi month names are
normalised first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vakeel_sahayak.ingestion.hindi import normalise_for_extraction
from vakeel_sahayak.pipelines.order_facts import DATE_RE
from vakeel_sahayak.pipelines.text_utils import normalise_date, split_sentences
from vakeel_sahayak.schemas.enums import DocumentType

SINGLE_VALUED_FIELDS = {
    "arrest_date": "Arrest",
    "fir_date": "FIR registered",
    "charge_sheet_date": "Charge sheet filed",
    "offence_date": "Offence occurred",
    "first_remand": "First remand",
}
MULTI_VALUED_FIELDS = {"remand": "Remand", "bail_outcome": "Bail"}
# The label prefix identifies the field again later (conflict detection reads labels back from the timeline store).
_LABEL_TO_FIELD = {label: field for field, label in {**SINGLE_VALUED_FIELDS, **MULTI_VALUED_FIELDS}.items()}


@dataclass(frozen=True)
class ExtractedEvent:
    """A dated event found in text: what it dates, its label, the ISO date and the sentence it came from."""

    field: str
    label: str
    date: str
    sentence: str


def field_of_label(label: str) -> str | None:
    """The field a timeline label dates ('Arrest' or 'Arrest (as stated in the FIR)' gives 'arrest_date'), or None."""
    text = label.strip().lower()
    for prefix, field in _LABEL_TO_FIELD.items():
        prefix = prefix.lower()
        if text == prefix or text.startswith(prefix + " ") or text.startswith(prefix + ":"):
            return field
    return None


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_OTHER_ACCUSED = _c(r"co-?accused|accused\s+no\.?\s*[2-9]|other\s+accused|another\s+accused")
_NO_ARREST = _c(r"anticipatory|apprehen\w+\s+of\s+arrest|not\s+(?:been\s+)?arrested|pre[\s-]?arrest")
_END_CUE = _c(r"(?:till|until|upto|up\s+to|next\s+date(?:\s+of\s+hearing)?|further\s+hearing|adjourned\s+to|listed\s+on|return(?:able)?|put\s+up)\W{0,12}(?:on\W{0,3})?$")
_COURT = _c(r"sessions?\s+(?:court|judge)|additional\s+sessions|high\s+court|supreme\s+court|(?:chief\s+judicial\s+|metropolitan\s+|judicial\s+)?magistrate|special\s+court|सत्र\s+न्यायालय|उच्च\s+न्यायालय")
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("first_remand", _c(r"first\s+remand|initial\s+remand|remanded\s+(?:for\s+the\s+first\s+time|first)")),
    ("fir_date", _c(r"\bF\.?I\.?R\.?\b[^;]{0,80}?\b(?:registered|lodged|dated|came\s+to\s+be\s+registered)|(?:registered|lodged)[^.]{0,60}?\bF\.?I\.?R|प्राथमिकी[^.।]{0,80}दर्ज|एफ\.?आई\.?आर[^.।]{0,60}दर्ज")),
    ("charge_sheet_date", _c(r"charge[\s-]?sheet[^.]{0,60}?\b(?:filed|submitted|laid|presented)|(?:filed|submitted|laid)[^.]{0,40}?charge[\s-]?sheet|final\s+report[^.]{0,40}?(?:filed|submitted)")),
    ("offence_date", _c(r"(?:date\s+of\s+(?:the\s+)?(?:incident|occurrence|offence|alleged\s+offence))|(?:incident|offence|occurrence)[^.]{0,40}?(?:occurred|took\s+place|happened|committed)|alleged\s+to\s+have\s+(?:been\s+)?committed|घटना\s+(?:दिनांक|घटित)")),
    ("arrest_date", _c(r"\barrest(?:ed)?\b|गिरफ्?तार")),
    ("remand", _c(r"remand(?:ed)?\b|रिमांड")),
    ("bail_outcome", _c(r"bail[^.]{0,60}?(?:rejected|dismissed|granted|allowed|declined|refused|denied)|(?:rejected|dismissed|allowed|granted)[^.]{0,40}?bail|जमानत[^.।]{0,40}(?:खारिज|मंजूर|स्वीकार)")),
]
_REJECT = _c(r"reject|dismiss|declin|refus|den(?:y|ied)|खारिज")
_DOC_DATE = _c(rf"(?:dated?|दिनांक|announced|pronounced|signed)\s*(?:on|:|-|this)?\s*[:\-]?\s*(?P<d>{DATE_RE.pattern})")


def document_date(text: str) -> str | None:
    """The date a document carries itself ('Dated: 21.08.2024', 'दिनांक 21/08/2024'), as ISO; None when it has none."""
    for m in _DOC_DATE.finditer(normalise_for_extraction(text)):
        iso = normalise_date(m.group("d").replace(",", ", ").strip())
        if iso:
            return iso
    return None


def _label(field: str, sentence: str) -> str:
    if field == "bail_outcome":
        outcome = "rejected" if _REJECT.search(sentence) else "granted"
        court = _COURT.search(sentence)
        return f"Bail {outcome}" + (f" ({_normalise_court(court.group(0))})" if court else "")
    return SINGLE_VALUED_FIELDS.get(field) or MULTI_VALUED_FIELDS[field]


def _normalise_court(raw: str) -> str:
    low = raw.lower()
    for key, name in (("sessions", "Sessions Court"), ("सत्र", "Sessions Court"), ("high", "High Court"), ("उच्च", "High Court"),
                      ("supreme", "Supreme Court"), ("special", "Special Court"), ("magistrate", "Magistrate")):  # fmt: skip
        if key in low:
            return name
    return raw.strip()


def _dated(sentence: str) -> list[tuple[int, str]]:
    """(position, ISO date) of each date in a sentence, leaving out dates that follow 'till', 'next date' and the like."""
    out: list[tuple[int, str]] = []
    for m in DATE_RE.finditer(sentence):
        if _END_CUE.search(sentence[max(0, m.start() - 30) : m.start()]):
            continue
        iso = normalise_date(m.group(0).replace(",", ", ").strip())
        if iso:
            out.append((m.start(), iso))
    return out


def _triggers(sentence: str) -> list[tuple[int, int, str]]:
    """(start, end, field) of each event cue in a sentence; a cue overlapping an earlier, more specific one is dropped."""
    taken: list[tuple[int, int, str]] = []
    for field, pattern in _PATTERNS:
        for m in pattern.finditer(sentence):
            if not any(m.start() < e and s < m.end() for s, e, _ in taken):
                taken.append((m.start(), m.end(), field))
    return sorted(taken)


def _assign(dates: list[tuple[int, str]], triggers: list[tuple[int, int, str]]) -> list[tuple[str, str]]:
    """(field, ISO date) pairs: each date goes to the nearest unused cue before it, else the nearest unused cue after it.

    A cue serves one date, so 'FIR dated 18.08.2024 ... on 17.08.2024' gives the FIR only the first date.
    """
    unused = list(triggers)
    out: list[tuple[str, str]] = []
    for position, iso in dates:
        before = [t for t in unused if t[1] <= position]
        pick = max(before, key=lambda t: t[1]) if before else min((t for t in unused if t[0] >= position), key=lambda t: t[0], default=None)
        if pick is not None:
            unused.remove(pick)
            out.append((pick[2], iso))
    return out


def _segments(text: str) -> list[str]:
    """Sentences, also cut after short heading lines ('Dated: 21.08.2024') that do not end in punctuation.

    A short line that ends in a lower-case word is taken to be a wrapped sentence and kept joined to the next line.
    """
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
    parts: list[str] = []
    current = ""
    for i, line in enumerate(lines):
        if not line:
            if current:
                parts.append(current)
                current = ""
            continue
        current = f"{current} {line}".strip()
        last = line.split()[-1]
        nxt = next((ln for ln in lines[i + 1 :] if ln), "")
        starts_new = nxt[:1].isupper() or bool(re.match(r"[\u0900-\u097F]", nxt))
        heading_end = len(line) <= 70 and starts_new and (
            (not re.search(r"[.,;:\-]$", line) and not last[:1].islower()) or bool(re.search(r"\d$", line))
        )
        if heading_end:
            parts.append(current)
            current = ""
    if current:
        parts.append(current)
    return [sent for part in parts for sent in split_sentences(part)]


def _sentence_with_date(text: str, iso: str) -> str:
    """The sentence or heading line of a text that states the given date (the evidence for a document's own event)."""
    for segment in _segments(text):
        if any(d == iso for _, d in _dated(segment)):
            return segment.strip()[:300]
    return ""


def extract_events(text: str, doc_type: DocumentType | None = None, doc_date: str | None = None) -> list[ExtractedEvent]:
    """Dated events stated in a document, found sentence by sentence, plus the document's own event.

    Sentences about co-accused are skipped for the applicant's arrest, and anticipatory-bail sentences give no arrest.
    The document's own event (a remand order dates a remand, an FIR dates the FIR) is added at its date when the
    sentences did not already give one on that date.

    Args:
        text: document text (names may already be pseudonymised)
        doc_type: the document's label
        doc_date: the document's own date (default: found in the text)

    Returns:
        Events in text order, without duplicates.
    """
    norm = normalise_for_extraction(text)
    found: list[ExtractedEvent] = []
    for sentence in _segments(norm):
        dates = _dated(sentence)
        triggers = _triggers(sentence) if dates else []
        for field, iso in _assign(dates, triggers):
            if field == "arrest_date" and (_OTHER_ACCUSED.search(sentence) or _NO_ARREST.search(sentence)):
                continue
            if field == "bail_outcome" and _OTHER_ACCUSED.search(sentence):
                continue
            found.append(ExtractedEvent(field, _label(field, sentence), iso, sentence.strip()[:300]))
    own = doc_date or document_date(norm)
    own_sentence = _sentence_with_date(norm, own) if own else ""
    own_field = {
        DocumentType.REMAND_ORDER: "remand",
        DocumentType.FIR: "fir_date",
        DocumentType.CHARGE_SHEET_COVER: "charge_sheet_date",
        DocumentType.ARREST_MEMO: "arrest_date",
        DocumentType.BAIL_ORDER: "bail_outcome",
    }.get(doc_type) if doc_type else None
    if own and own_field and not any(e.field == own_field and e.date == own for e in found):
        if own_field == "bail_outcome":
            outcome = "rejected" if re.search(r"(?:application|bail)[^.]{0,150}?(?:rejected|dismissed|declined|refused)|खारिज", norm, re.I) else (
                "granted" if re.search(r"(?:bail|application)[^.]{0,150}?(?:granted|allowed)|मंजूर|स्वीकार", norm, re.I) else None
            )
            court = _COURT.search(norm[:600])
            if outcome:
                label = f"Bail {outcome}" + (f" ({_normalise_court(court.group(0))})" if court else "")
                found.append(ExtractedEvent("bail_outcome", label, own, own_sentence or f"Order dated {own}"))
        elif not (own_field in SINGLE_VALUED_FIELDS and any(e.field == own_field for e in found)):
            found.append(ExtractedEvent(own_field, _label(own_field, ""), own, own_sentence or f"Document dated {own}"))
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for e in found:
        key = (e.field, e.label, e.date)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique
