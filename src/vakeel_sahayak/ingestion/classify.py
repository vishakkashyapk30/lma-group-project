"""Document labelling and paragraph information tagging (plan §4.3 step 2).

Documents are labelled by rules over header cues (strong) and body cues (weak). A language-model classifier is a
pluggable fallback only: `LlmClassifier` is the interface and `label_document` calls it when the rules are not
confident enough (`doc_type_conf_min`). Paragraph tags are rules over the same regexes the order pipelines use.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from vakeel_sahayak.ingestion.hindi import normalise_for_extraction
from vakeel_sahayak.ingestion.thresholds import threshold
from vakeel_sahayak.pipelines.order_facts import extract_dates
from vakeel_sahayak.pipelines.section_extract import extract_sections
from vakeel_sahayak.schemas.enums import DocumentType, InfoKind

HEADER_CHARS = 320  # the title area: the first four lines of a document's first page, at most this many characters


class LlmClassifier(Protocol):
    """Fallback classifier interface (plan §4.3 step 2): given a document's opening text, return (type, confidence) or None."""

    def __call__(self, text: str) -> tuple[DocumentType, float] | None:
        """Classify, or return None when it cannot."""
        ...


def _c(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# (pattern, weight). A cue of weight 3 or more is a title-grade cue: it counts in full when it is in the document's
# header and at a third of its weight when it only appears in the body (an order that mentions "the charge sheet" is not
# a charge sheet). Weaker cues count once, and again when they are in the header.
_CUES: dict[DocumentType, list[tuple[re.Pattern[str], float]]] = {
    DocumentType.FIR: [
        (_c(r"first\s+information\s+report|प्रथम\s+सूचना\s+रिपोर्ट"), 4),
        (_c(r"information\s+received\s+at\s+(?:p\.?s|police\s+station)|section\s+154|173\s*(?:\(1\))?\s*BNSS|प्राथमिकी\s+संख्या"), 2),
        (_c(r"\bF\.?I\.?R\.?\b|प्राथमिकी|\bcomplainant\b|\binformant\b|शिकायतकर्ता"), 0.5),
    ],
    DocumentType.ARREST_MEMO: [
        (_c(r"memo\s+of\s+arrest|arrest\s+memo|arrest/?surrender\s+memo|गिरफ्?तारी\s+(?:मेमो|पत्र)"), 5),
        (_c(r"grounds\s+of\s+arrest|arrested\s+by|person\s+arrested|informed\s+of\s+the\s+grounds"), 1.5),
    ],
    DocumentType.REMAND_ORDER: [
        (_c(r"remand\s+(?:order|application|report)|order\s+on\s+remand|रिमांड\s+आदेश"), 4),
        (_c(r"remanded\s+to\s+(?:judicial|police|magisterial)\s+custody|produced\s+before|judicial\s+custody\s+(?:till|upto|up\s+to)|u/s\s*167|section\s+167|section\s+187\s+BNSS"), 1.5),
        (_c(r"\bremand\b|रिमांड"), 0.8),
    ],
    DocumentType.BAIL_ORDER: [
        (_c(r"bail\s+application|application\s+(?:for|u/s|under)[^.\n]{0,40}bail|regular\s+bail|anticipatory\s+bail|bail\s+order|जमानत\s+(?:आवेदन|प्रार्थना)"), 3),
        (_c(r"bail\s+(?:is\s+|stands\s+|hereby\s+)?(?:granted|rejected|allowed|dismissed|declined|refused)|(?:granted|released|enlarged)\s+(?:on|to)\s+bail|application\s+is\s+(?:rejected|dismissed|allowed)"), 3),
        (_c(r"\bbail\b|जमानत"), 0.7),
        (_c(r"section\s+(?:439|483|480|482|437|438)\b|\b(?:439|483)\s+(?:cr\.?p\.?c|bnss)"), 1.5),
    ],
    DocumentType.ORDER_SHEET: [
        (_c(r"order[\s-]*sheet|daily\s+order|proceedings\s+of\s+the\s+day|zimni|ज़िमनी|आदेश\s+पत्रिका"), 5),
        (_c(r"next\s+date\s+of\s+hearing|case\s+called\s+(?:up|on)|put\s+up\s+(?:on|for)"), 1.5),
    ],
    DocumentType.CHARGE_SHEET_COVER: [
        (_c(r"charge[\s-]*sheet|final\s+report\s+(?:under|u/s)|police\s+report\s+(?:under|u/s)|आरोप\s*पत्र|अंतिम\s+रिपोर्ट"), 4),
        (_c(r"section\s+173|section\s+193\s+BNSS|173\s*\(2\)|list\s+of\s+witnesses|column\s+no"), 1.5),
    ],
    DocumentType.CUSTODY_CERTIFICATE: [
        (_c(r"custody\s+certificate|certificate\s+of\s+custody|nominal\s+roll|पेशी\s+वारंट|अभिरक्षा\s+प्रमाण"), 5),
        (_c(r"jail\s+(?:superintendent|custody\s+report)|period\s+of\s+(?:detention|custody)|date\s+of\s+admission\s+to\s+(?:jail|prison)|lodged\s+in\s+(?:\w+\s+)?jail|undertrial\s+prisoner|convict\s+number"), 2),
    ],
    DocumentType.MEDICAL_RECORD: [
        (_c(r"medico[\s-]*legal|medical\s+(?:examination|certificate|report|record)|discharge\s+summary|prescription|चिकित्सा\s+(?:प्रमाण|रिपोर्ट)|मेडिकल"), 4),
        (_c(r"diagnos(?:is|ed)|patient|hospital|\bOPD\b|treatment|blood\s+pressure|admitted\s+on"), 1.2),
    ],
    DocumentType.AFFIDAVIT: [
        (_c(r"\baffidavit\b|शपथ\s*पत्र|हलफ़?नामा"), 5),
        (_c(r"solemnly\s+(?:affirm|declare|state)|deponent|verified\s+at|on\s+oath"), 2),
    ],
}
# Court-style titles that open an order but do not say which kind it is.
COURT_HEADING = _c(r"in\s+the\s+(?:hon'?ble\s+)?(?:court|high\s+court|supreme\s+court)|न्यायालय")


def score_document(text: str, first_page_text: str | None = None) -> dict[DocumentType, float]:
    """Cue score per document type: title-grade cues in the header in full, elsewhere at a third; weaker cues once or twice. Pure."""
    text = normalise_for_extraction(text)
    header = normalise_for_extraction(opening_lines(first_page_text if first_page_text is not None else text, 4, HEADER_CHARS))
    scores: dict[DocumentType, float] = {}
    for doc_type, cues in _CUES.items():
        total = 0.0
        for pattern, weight in cues:
            in_header, in_body = bool(pattern.search(header)), bool(pattern.search(text))
            if weight >= 3:
                total += weight if in_header else (weight / 3 if in_body else 0.0)
            else:
                total += weight * (in_body + in_header)
        if total:
            scores[doc_type] = round(total, 3)
    return scores


def label_document(
    text: str,
    first_page_text: str | None = None,
    *,
    fallback: LlmClassifier | Callable[[str], tuple[DocumentType, float] | None] | None = None,
    thresholds: dict[str, float] | None = None,
) -> tuple[DocumentType, float]:
    """Label as FIR, arrest memo, remand order, bail order, order sheet, charge-sheet cover, custody certificate, medical record, affidavit or other.

    Args:
        text: whole document text
        first_page_text: its first page (the header cues are read from here; default: the start of `text`)
        fallback: a language-model classifier used when the rule confidence is under `doc_type_conf_min`; its answer
            is taken only when it is more confident than the rules
        thresholds: dev-tuned values

    Returns:
        (type, confidence). Confidence is the winner's share of the score mass with a small prior; 0.3 for OTHER.
    """
    scores = score_document(text, first_page_text)
    if scores:
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_type, top = ranked[0]
        rest = sum(s for _, s in ranked[1:])
        confidence = round(min(0.99, top / (top + rest + 1.0)), 2)
        result = (top_type, confidence) if top >= 2.5 else (DocumentType.OTHER, 0.3)
    else:
        result = (DocumentType.OTHER, 0.3)
    if fallback is not None and result[1] < threshold(thresholds, "doc_type_conf_min"):
        guess = fallback((first_page_text if first_page_text is not None else text)[:2000])
        if guess is not None and guess[1] > result[1]:
            return DocumentType(guess[0]), float(guess[1])
    return result


def opening_lines(text: str, n: int = 3, limit: int = 260) -> str:
    """The first `n` non-empty lines of a page (at most `limit` characters): where a document's title sits."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()][:n]
    return "\n".join(lines)[:limit]


# Title phrases, the only cues a page's opening lines are read for when splitting a bundle.
_TITLES: dict[DocumentType, re.Pattern[str]] = {
    DocumentType.FIR: _c(r"first\s+information\s+report|प्रथम\s+सूचना\s+रिपोर्ट|^\W*FIR\b"),
    DocumentType.ARREST_MEMO: _c(r"memo\s+of\s+arrest|arrest\s+memo|arrest/?surrender\s+memo|गिरफ्?तारी\s+(?:मेमो|पत्र)"),
    DocumentType.REMAND_ORDER: _c(r"remand\s+(?:order|application|report)|order\s+on\s+remand|रिमांड\s+आदेश"),
    DocumentType.BAIL_ORDER: _c(r"bail\s+application|application\s+for[^.\n]{0,30}bail|bail\s+order|order\s+on\s+bail|जमानत\s+(?:आवेदन|प्रार्थना)"),
    DocumentType.ORDER_SHEET: _c(r"order[\s-]*sheet|daily\s+order|zimni|आदेश\s+पत्रिका"),
    DocumentType.CHARGE_SHEET_COVER: _c(r"charge[\s-]*sheet|final\s+report|आरोप\s*पत्र"),
    DocumentType.CUSTODY_CERTIFICATE: _c(r"custody\s+certificate|certificate\s+of\s+custody|nominal\s+roll"),
    DocumentType.MEDICAL_RECORD: _c(r"medico[\s-]*legal|medical\s+(?:examination|certificate|report)|discharge\s+summary"),
    DocumentType.AFFIDAVIT: _c(r"^\W*affidavit\b|शपथ\s*पत्र|हलफ़?नामा"),
}


def page_type_hint(text: str) -> tuple[DocumentType | None, float, bool]:
    """A single page's type from the title in its opening lines alone, for bundle splitting.

    Returns:
        (type or None, confidence, has_court_heading). The type is the title that matches; None when the page has no
        title. Confidence is 0.9 for a single title and lower when several types match.
    """
    header = normalise_for_extraction(opening_lines(text))
    first = next((ln for ln in text.split("\n") if ln.strip()), "")
    title = normalise_for_extraction(first)
    # the document's own title line wins over words in the lines under it ('ORDER SHEET' then 'charge sheet filed')
    hits = [t for t, pattern in _TITLES.items() if pattern.search(title)] or [
        t for t, pattern in _TITLES.items() if pattern.search(header)
    ]
    heading = bool(COURT_HEADING.search(header))
    if not hits:
        return None, 0.0, heading
    return hits[0], round(0.9 / len(hits), 2), heading


_PARTY = _c(r"\b(?:accused|co-?accused|complainant|informant|applicant|petitioner|respondent|victim|witness|I\.?O\.?|investigating\s+officer|surety)\b|\bState\s+(?:v\.?|vs\.?|versus)\b|\bv(?:s)?\.\s+State\b|अभियुक्त|आरोपी|शिकायतकर्ता|गवाह|प्रार्थी")
_OUTCOME = _c(r"bail\s+(?:application\s+)?(?:was\s+|is\s+|has\s+been\s+|stands\s+)?(?:rejected|dismissed|granted|allowed|declined|refused|denied)|(?:rejected|dismissed|allowed)\s+the\s+(?:bail|application)|(?:earlier|previous|first|second|prior)\s+(?:regular\s+)?(?:bail\s+)?(?:application|petition)|released\s+on\s+bail|जमानत\s+(?:खारिज|मंजूर|स्वीकार)")
_CUSTODY = _c(r"judicial\s+custody|police\s+custody|\bremand(?:ed)?\b|in\s+custody|\bjail\b|incarcerat|न्यायिक\s+अभिरक्षा|पुलिस\s+रिमांड|हिरासत|कारागार|जेल")
_PERSONAL = _c(r"\baged?\b|years?\s+old|\bwife\b|\bchildren\b|\bfamily\b|sole\s+(?:bread|earning)|\bstudent\b|\bhealth\b|\billness\b|\bdiabet|\bheart\b|\bsurgery\b|\bpregnan|\bdisabled\b|\bemployed\b|\bresident\s+of\b|permanent\s+address|आयु|उम्र|पत्नी|बच्चे|परिवार|बीमार|स्वास्थ्य")


def tag_paragraph(text: str) -> list[InfoKind]:
    """Tag by information kind: dated event, party, section, earlier outcome, custody, personal circumstance.

    Args:
        text: see behaviour

    Returns:
        InfoKinds.
    """
    norm = normalise_for_extraction(text)
    tags: list[InfoKind] = []
    if extract_dates(norm):
        tags.append(InfoKind.DATED_EVENT)
    if _PARTY.search(norm):
        tags.append(InfoKind.PARTY)
    if extract_sections(norm):
        tags.append(InfoKind.SECTION)
    if _OUTCOME.search(norm):
        tags.append(InfoKind.EARLIER_OUTCOME)
    if _CUSTODY.search(norm):
        tags.append(InfoKind.CUSTODY)
    if _PERSONAL.search(norm):
        tags.append(InfoKind.PERSONAL)
    return tags
