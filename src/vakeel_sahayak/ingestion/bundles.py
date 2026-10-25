"""Bundle splitting: document type changes, new headers, page numbers restarting (plan §4.1 K8, §4.3)."""

from __future__ import annotations

import re

from vakeel_sahayak.ingestion.classify import opening_lines, page_type_hint
from vakeel_sahayak.ingestion.events import document_date
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.ingestion.thresholds import threshold
from vakeel_sahayak.schemas.enums import DocumentType

_PAGE_OF = re.compile(r"(?:page|pg\.?|पृष्ठ)?\s*(\d{1,3})\s*(?:of|/|में से)\s*(\d{1,3})", re.IGNORECASE)
_PAGE_WORD = re.compile(r"^\W*(?:page|pg\.?|पृष्ठ)\s*(?:no\.?)?\s*[:\-]?\s*(\d{1,3})\W*$", re.IGNORECASE)
_PAGE_BARE = re.compile(r"^\W{0,3}(\d{1,3})\W{0,3}$")


def page_number(text: str) -> int | None:
    """The printed page number in a page's first or last lines ('Page 2 of 5', '- 3 -', '2/5'), or None.

    Args:
        text: page text

    Returns:
        The number as printed.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    for line in [*reversed(lines[-2:]), *lines[:2]]:
        if m := _PAGE_OF.fullmatch(line) or _PAGE_WORD.match(line) or _PAGE_BARE.match(line):
            return int(m.group(1))
        if m := _PAGE_OF.search(line):
            if len(line) <= 30:
                return int(m.group(1))
    return None


def split_into_documents(
    page_texts: list[str], page_signals: list[PageSignals], thresholds: dict[str, float] | None = None
) -> list[tuple[int, int]]:
    """Return inclusive (first, last) page ranges, one per document.

    A new document starts at a page when:
    - its printed page number restarts at 1 after a higher number;
    - its opening lines carry a document title of a different type than the document so far (confidence at least
      `boundary_sensitivity`); or
    - it opens with a court heading while the previous page did not, or with a different date (two orders of the same
      type back to back);
    - it has a title and the pages before it in the document had none (an untitled court order, then a certificate); or
    - it opens with a court heading and no title after a document with a title that is not a bail order (a High Court
      order following an FIR, a remand order or a certificate).

    A page with no readable text joins the document before it. Page numbers in the result start at 1.

    Args:
        page_texts: text of each page, in order (an unreadable page is '')
        page_signals: the signals of each page (the split reads the text; a page with no text stays with its document)
        thresholds: dev-tuned values

    Returns:
        Ranges covering every page once, in order.
    """
    n = len(page_texts)
    if n == 0:
        return []
    min_conf = threshold(thresholds, "boundary_sensitivity")
    ranges: list[tuple[int, int]] = []
    start, cur_type, prev_no, prev_heading, prev_date = 1, None, None, False, None
    for i, text in enumerate(page_texts, start=1):
        if not text.strip():
            if prev_no is not None:
                prev_no += 1
            continue  # unreadable or blank: stays with the current document
        ptype, pconf, heading = page_type_hint(text)
        number = page_number(text)
        date = document_date(opening_lines(text, 6, 400))
        if i > start or ranges:
            restart = number == 1 and prev_no is not None and prev_no >= 1
            new_type = ptype is not None and pconf >= min_conf and cur_type is not None and ptype != cur_type
            new_header = (
                heading and ptype is not None and ptype == cur_type and pconf >= min_conf
                and (not prev_heading or (date is not None and prev_date is not None and date != prev_date))
            )  # fmt: skip
            # a titled page after pages that never had a title: the untitled pages were a court order or letter of their own
            untitled_before = ptype is not None and pconf >= min_conf and cur_type is None
            # an untitled page that opens with a court heading, after a titled document that is not itself an order: a court
            # order starts here (High Court orders carry the court's name and a case number, not a document title)
            new_court_order = heading and ptype is None and cur_type is not None and cur_type != DocumentType.BAIL_ORDER
            if (restart or new_type or new_header or untitled_before or new_court_order) and i > start:
                ranges.append((start, i - 1))
                start, cur_type = i, None
        if cur_type is None:
            cur_type = ptype
        prev_no = number if number is not None else (prev_no + 1 if prev_no is not None else None)
        prev_heading, prev_date = heading, date or prev_date
    ranges.append((start, n))
    return ranges
