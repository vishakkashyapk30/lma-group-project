"""Offline handler for Peshkar's extractor task (`peshkar.extract_field`): rules over the passages, no language model.

The fine-tuned 4B reads passages and returns values with quotes; offline, `OfflineLLM` calls this handler instead
(registered at import, plan §3.3). It is deliberately the same shape of answer: every item carries the sentence it was
read from, so the span check, the quote location and the re-extraction run exactly as they do with a model. Values are
copied or normalised from the text, never invented; a part a sentence does not state stays null.

On a re-extraction (`retry` > 0) the windows around a match are wider, so a value whose date or station sat in the
next sentence is found the second time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.peshkar.fields import PARTY_RANK, TASK_FIELD_NAMES, flat, merge_subsumed, sentences, unwrap
from vakeel_sahayak.agents.peshkar.prompts import TASK_EXTRACT_FIELD
from vakeel_sahayak.ingestion.classify import tag_paragraph
from vakeel_sahayak.ingestion.events import extract_events, field_of_label
from vakeel_sahayak.ingestion.filing import _PROCEDURAL_EXTRA
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.pipelines.concordance.refs import split_ref
from vakeel_sahayak.pipelines.order_facts import DATE_RE, charge_sheet_status, co_accused_outcome
from vakeel_sahayak.pipelines.section_extract import charged_sections, extract_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date
from vakeel_sahayak.schemas.enums import DocumentType, InfoKind

_FIR_NO = re.compile(
    r"(?:F\.?\s?I\.?\s?R\.?|(?:First\s+)?Information\s+Report|प्रथम\s+सूचना\s+रिपोर्ट|प्राथमिकी)\s*(?:No\.?|Number|Nos\.?|सं\.?|संख्या)?\s*[:\-]?\s*(?:No\.?\s*)?"
    r"(\d{1,6})\s*(?:/|of)\s*((?:19|20)\d{2})",
    re.IGNORECASE,
)
_PS = re.compile(r"\b(PS-\d+)\b|(?:\bP\.?\s?S\.?|(?i:police\s+station)|थाना)\s*[:\-]?\s*([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){0,2})")
_ALIAS = re.compile(r"\b(?:Accused|Co-accused|Complainant|IO|Witness|Person)-\d+\b")
_CO_ID = re.compile(r"\bCo-accused-\d+\b")
_NO_ANTECEDENTS = re.compile(
    r"\bno\s+(?:other\s+|previous\s+|prior\s+|criminal\s+)*(?:antecedents?|cases?|criminal\s+history|criminal\s+record)\b"
    r"|not\s+involved\s+in\s+any\s+other|clean\s+(?:criminal\s+)?record|first[\s-]time\s+offender",
    re.IGNORECASE,
)
_ANTECEDENTS = re.compile(
    r"\b(?:other|another|previous|prior|earlier)\s+(?:criminal\s+)?(?:cases?|FIRs?)\b[^.]*?(?:pending|registered|against)"
    r"|involved\s+in\s+(?:\w+\s+)?other\s+(?:criminal\s+)?cases?|antecedents?\s*[:\-]\s*\S+",
    re.IGNORECASE,
)
_CO_ACCUSED = re.compile(r"co[\s-]?accused", re.IGNORECASE)
_STAGES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("trial commenced", re.compile(r"trial\s+(?:has\s+)?(?:commenced|begun|started)|evidence\s+(?:has\s+)?(?:commenced|begun)|witnesses?\s+(?:have\s+been\s+)?examined", re.I)),
    ("charges framed", re.compile(r"charges?\s+(?:have\s+been\s+|were\s+|has\s+been\s+|was\s+)framed", re.I)),
    ("charges not framed", re.compile(r"charges?\s+(?:have\s+|has\s+)?(?:not\s+(?:yet\s+)?been\s+framed|yet\s+to\s+be\s+framed|not\s+(?:yet\s+)?framed)", re.I)),
    ("investigation pending", re.compile(r"investigation\s+(?:is\s+)?(?:still\s+)?(?:pending|going\s+on|in\s+progress|ongoing)", re.I)),
)  # fmt: skip
_BAIL_LABEL = re.compile(r"Bail (rejected|granted)(?: \((.+)\))?")
MAX_PERSONAL = 5


@dataclass
class _Passage:
    doc: str | None
    page: int | None
    doc_type: DocumentType | None
    view: str  # the text the rules read: the English view of a Hindi page, else the page text
    sents: list[str] = field(default_factory=list)


def _passages(case: dict[str, Any]) -> list[_Passage]:
    """One passage per block of the shown text (blocks are runs of consecutive sentences, so windows never jump)."""
    out = []
    for p in case.get("passages") or []:
        shown = unwrap(p.get("text_en") or "") or unwrap(p.get("text") or "")
        try:
            doc_type = DocumentType(p.get("doc_type")) if p.get("doc_type") else None
        except ValueError:
            doc_type = None
        for block in re.split(r"\n\s*\n", shown):
            view = flat(block)
            if view:
                out.append(_Passage(p.get("doc"), p.get("page"), doc_type, view, sentences(view)))
    return out


def _iso(sentence: str) -> str | None:
    for m in DATE_RE.finditer(sentence):
        iso = normalise_date(m.group(0).replace(",", ", ").strip())
        if iso:
            return iso
    return None


def _events(passages: list[_Passage], timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dated events: the filed timeline rows first (they carry their source), then what the passages say."""
    found: list[dict[str, Any]] = []
    for row in timeline:
        f = field_of_label(row.get("label", ""))
        quote = row.get("quote")
        if f and quote and row.get("date"):
            found.append({"field": f, "label": row["label"], "date": row["date"], "quote": quote, "doc": row.get("doc"), "page": row.get("page")})
    for p in passages:
        for e in extract_events(p.view, p.doc_type):
            found.append({"field": e.field, "label": e.label, "date": e.date, "quote": e.sentence, "doc": p.doc, "page": p.page})
    seen: set[tuple[str, str, str]] = set()
    unique = []
    for e in found:
        key = (e["field"], e["label"], e["date"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _item(value: Any, quote: str | None, doc: str | None, page: int | None) -> dict[str, Any]:
    return {"value": value, "quote": (quote or "")[:600] or None, "doc": doc, "page": page}


def _by_date(events: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in events:
        if e["field"] == field_name:
            out.setdefault(e["date"], e)
    return list(out.values())


# ---------------------------------------------------------------------------------------------- the fields


def _parse_fir(text: str, date_hint: str | None = None) -> dict[str, Any] | None:
    number = None
    if m := _FIR_NO.search(text):
        number = f"{m.group(1)}/{m.group(2)}"
    ps = None
    if m := _PS.search(text):
        ps = m.group(1) or m.group(2)
    # a bare date counts only when it sits right after the FIR number ("FIR No. 112/2024 dated 14.08.2024"); a date elsewhere in the
    # window (an arrest or a remand) is another event, not the date of the FIR
    after_number = _iso(text[m.end() : m.end() + 25]) if (m := _FIR_NO.search(text)) else None
    fir_date = next((e.date for e in extract_events(text) if e.field == "fir_date"), None) or date_hint or after_number
    if number is None and ps is None and fir_date is None:
        return None
    return {"number": number, "police_station": ps, "date": fir_date}


def _fir(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    found: list[dict[str, Any]] = []
    for p in sorted(passages, key=lambda p: p.doc_type != DocumentType.FIR):  # the FIR itself first: when readings tie it is the one kept
        for i, s in enumerate(p.sents):
            # "सं." or "No." can end a sentence, so the number may open the next one; the station and the date often sit in the next sentence too
            if _FIR_NO.search(s) or _FIR_NO.search(" ".join(p.sents[i : i + 2])):
                window = " ".join(p.sents[max(0, i - retry) : i + 2 + retry])
                if (value := _parse_fir(window)) is not None:
                    found.append(_item(value, window, p.doc, p.page))
    for e in _by_date(events, "fir_date"):
        value = _parse_fir(e["quote"], e["date"])
        if value is not None:
            found.append(_item({**value, "date": e["date"]}, e["quote"], e["doc"], e["page"]))
    return _dedupe_dicts(found), False, None


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop an item whose parts are all repeated by a fuller item (the same FIR read from a second sentence)."""
    values = merge_subsumed([i["value"] for i in items])
    kept: list[dict[str, Any]] = []
    for v in values:
        kept.append(next(i for i in items if i["value"] == v))
    return kept


def _date_field(name: str) -> Any:
    def read(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
        picked = _by_date(events, name)
        if name == "first_remand" and not picked:
            remands = sorted(_by_date(events, "remand"), key=lambda e: e["date"])
            picked = remands[:1]
        return [_item(e["date"], e["quote"], e["doc"], e["page"]) for e in picked], False, None

    return read


def _charge_sheet(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    filed_at: list[tuple[str, str | None, int | None]] = []
    not_filed: tuple[str, str | None, int | None] | None = None
    for p in passages:
        for s in p.sents:
            status = charge_sheet_status(s)
            if status == "filed":
                filed_at.append((s, p.doc, p.page))
            elif status == "not_filed" and not_filed is None:
                not_filed = (s, p.doc, p.page)
    dated = _by_date(events, "charge_sheet_date")
    if dated:
        return [_item({"filed": True, "date": e["date"]}, e["quote"], e["doc"], e["page"]) for e in dated], False, None
    if filed_at:
        s, doc, page = filed_at[0]
        return [_item({"filed": True, "date": None}, s, doc, page)], False, None
    if not_filed:
        s, doc, page = not_filed
        return [_item({"filed": False, "date": None}, s, doc, page)], False, None
    return [], False, None


def _trial_stage(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    best: tuple[int, str, str, str | None, int | None] | None = None
    for rank, (value, pattern) in enumerate(reversed(_STAGES)):  # later stages rank higher
        for p in passages:
            for s in p.sents:
                if pattern.search(s) and (best is None or rank > best[0]):
                    best = (rank, value, s, p.doc, p.page)
    return ([_item(best[1], best[2], best[3], best[4])] if best else []), False, None


def _previous_bail(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for e in events:
        if e["field"] != "bail_outcome" or not (m := _BAIL_LABEL.match(e["label"])):
            continue
        value = {"court": m.group(2) or "court not stated", "date": e["date"], "outcome": m.group(1)}
        out.setdefault((value["court"], value["date"], value["outcome"]), _item(value, e["quote"], e["doc"], e["page"]))
    return list(out.values()), False, None


def _co_accused_bail(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    out: list[dict[str, Any]] = []
    for p in passages:
        for s in p.sents:
            outcome = co_accused_outcome(s)
            if outcome:
                m = _CO_ID.search(s)
                out.append(_item({"id": m.group(0) if m else "Co-accused-1", "outcome": outcome, "date": _iso(s)}, s, p.doc, p.page))
    seen: set[tuple[str, str]] = set()
    unique = []
    for i in out:
        key = (i["value"]["id"], i["value"]["outcome"])
        if key not in seen:
            seen.add(key)
            unique.append(i)
    return unique, False, None


def _antecedents(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    pos: list[dict[str, Any]] = []
    none: tuple[str, str | None, int | None] | None = None
    for p in passages:
        for s in p.sents:
            if _CO_ACCUSED.search(s):
                continue
            if _NO_ANTECEDENTS.search(s):
                none = none or (s, p.doc, p.page)
            elif _ANTECEDENTS.search(s):
                pos.append(_item(s[:240], s, p.doc, p.page))
    if pos:
        return pos, False, None
    return [], none is not None, none[0] if none else None


def _personal(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    out: list[dict[str, Any]] = []
    for p in passages:
        for s in p.sents:
            if len(s) > 15 and InfoKind.PERSONAL in tag_paragraph(s) and not _CO_ACCUSED.search(s):
                out.append(_item(s[:240], s, p.doc, p.page))
    return out[:MAX_PERSONAL], False, None


def _parties(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    first: dict[str, dict[str, Any]] = {}
    for p in passages:
        for s in p.sents:
            for alias in _ALIAS.findall(s):
                first.setdefault(alias, _item(alias, s, p.doc, p.page))

    def rank(alias: str) -> tuple[int, int]:
        kind, _, n = alias.rpartition("-")
        return PARTY_RANK.get(kind, 9), int(n)

    return [first[a] for a in sorted(first, key=rank)], False, None


def _sections(passages: list[_Passage], events: list[dict[str, Any]], retry: int) -> tuple[list[dict[str, Any]], bool, str | None]:
    first: dict[str, dict[str, Any]] = {}
    for p in passages:
        for s in p.sents:
            for ref in charged_sections(extract_sections(s)):
                if ref.split("(")[0] in _PROCEDURAL_EXTRA or ref in first:
                    continue
                try:
                    code, section = split_ref(ref)
                except ValueError:
                    continue
                first[ref] = _item({"as_written": ref, "code": code, "section": section}, s, p.doc, p.page)
    return list(first.values()), False, None


_READERS = {
    "fir": _fir, "offence_date": _date_field("offence_date"), "arrest_date": _date_field("arrest_date"),
    "first_remand": _date_field("first_remand"), "charge_sheet": _charge_sheet, "trial_stage": _trial_stage,
    "previous_bail": _previous_bail, "co_accused_bail": _co_accused_bail, "antecedents": _antecedents,
    "personal": _personal, "parties": _parties, "sections": _sections,
}  # fmt: skip
assert set(_READERS) == set(TASK_FIELD_NAMES)


def extract_field_offline(req: OfflineRequest) -> dict[str, Any]:
    """The rule-based reading of one field: items with quotes, from the passages and the filed timeline rows."""
    case = req.case
    name = str(case.get("field") or "")
    reader = _READERS.get(name)
    if reader is None:
        return {"field": name, "items": [], "none_stated": False, "none_quote": None}
    passages = _passages(case)
    events = _events(passages, [r for r in case.get("timeline") or [] if isinstance(r, dict)])
    items, none_stated, none_quote = reader(passages, events, int(case.get("retry") or 0))
    return {"field": name, "items": items, "none_stated": none_stated, "none_quote": none_quote}


def register() -> None:
    """Register the handler with the offline client (the agent module does this at import)."""
    register_offline_handler(TASK_EXTRACT_FIELD, extract_field_offline)


register()
