"""Gap handling: re-read, search remaining pages, or ask counsel (plan §4.3 step 4).

For a checklist item that is still missing after filing, Munshi tries, in this order:

1. re-read a likely page with a stronger route (a page of the expected document type that OCR read with low confidence);
2. search the remaining pages (pages that belong to no typed document, or were never read) for the item;
3. ask counsel for the document.

Each step is a callback so the agent can wire them to its own state; without callbacks only the search over the saved
page index and the question to counsel run. The returned `Gap` says what was done, for example
'searched pages 6-14; not found; asked counsel'.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from vakeel_sahayak.ingestion.checklist import ITEM_NAMES, ITEM_QUESTIONS
from vakeel_sahayak.ingestion.pageindex import IndexedPage, PageIndex, index_path
from vakeel_sahayak.ingestion.questions import page_ranges
from vakeel_sahayak.ingestion.thresholds import threshold
from vakeel_sahayak.schemas.enums import DocumentType
from vakeel_sahayak.schemas.ingestion_report import Gap

MAX_REREAD_PAGES = 3

# What the missing item looks like in text.
GAP_CUES: dict[str, re.Pattern[str]] = {
    "fir": re.compile(r"first\s+information\s+report|\bF\.?I\.?R\.?\s+No|प्राथमिकी", re.I),
    "arrest_date": re.compile(r"arrest(?:ed)?\b|गिरफ्?तार", re.I),
    "first_remand": re.compile(r"remand(?:ed)?\b|रिमांड", re.I),
    "earlier_bail_orders": re.compile(r"bail\s+(?:application|order)|bail[^.]{0,50}(?:rejected|granted|dismissed)|जमानत", re.I),
    "charge_sheet_status": re.compile(r"charge[\s-]?sheet|final\s+report|आरोप\s*पत्र", re.I),
    "custody_certificate": re.compile(r"custody\s+certificate|nominal\s+roll|jail\s+superintendent|period\s+of\s+custody", re.I),
    "co_accused_orders": re.compile(r"co[\s-]?accused", re.I),
}
# Document types where the item is expected; a weak page of such a document is the likely page to re-read.
LIKELY_TYPES: dict[str, set[str]] = {
    "fir": {DocumentType.FIR.value},
    "arrest_date": {DocumentType.ARREST_MEMO.value, DocumentType.REMAND_ORDER.value, DocumentType.FIR.value},
    "first_remand": {DocumentType.REMAND_ORDER.value},
    "earlier_bail_orders": {DocumentType.BAIL_ORDER.value},
    "charge_sheet_status": {DocumentType.CHARGE_SHEET_COVER.value, DocumentType.BAIL_ORDER.value},
    "custody_certificate": {DocumentType.CUSTODY_CERTIFICATE.value},
    "co_accused_orders": {DocumentType.BAIL_ORDER.value},
}
# A document of type OTHER that holds the item is taken to be that document.
ADOPT_AS: dict[str, DocumentType] = {
    "fir": DocumentType.FIR,
    "first_remand": DocumentType.REMAND_ORDER,
    "charge_sheet_status": DocumentType.CHARGE_SHEET_COVER,
    "custody_certificate": DocumentType.CUSTODY_CERTIFICATE,
}


def _where(pages: list[IndexedPage]) -> str:
    """'pages 6-14' for one file; 'bundle_1.pdf pages 6-14, other.pdf page 2' for several."""
    by_file: dict[str, list[int]] = {}
    for p in pages:
        by_file.setdefault(p.file, []).append(p.page)
    parts = [(f"{name} " if len(by_file) > 1 else "") + ("page " if len(nums) == 1 else "pages ") + page_ranges(nums) for name, nums in by_file.items()]
    return ", ".join(parts)


def is_weak(page: IndexedPage, thresholds: dict[str, float] | None = None) -> bool:
    """A page a stronger route could still improve: read by OCR (not vision) at a confidence below the escalation bar."""
    return (
        page.status != "UNREADABLE"
        and page.route == "ocr"
        and page.ocr_conf is not None
        and page.ocr_conf < threshold(thresholds, "vision_escalation_conf")
    )


def remaining_pages(index: PageIndex) -> list[IndexedPage]:
    """Pages that belong to no typed document (type OTHER or none), the ones a gap search looks through."""
    return [p for p in index.pages if p.doc_type in (None, DocumentType.OTHER.value)]


def resolve_gap(
    item: str,
    case_id: str,
    *,
    index: PageIndex | None = None,
    reread: Callable[[IndexedPage], str | None] | None = None,
    adopt: Callable[[IndexedPage, str], bool] | None = None,
    ask: Callable[[str, str], bool] | None = None,
    thresholds: dict[str, float] | None = None,
    cases_dir: str | None = None,
) -> Gap:
    """Decide whether to re-read a likely page with a stronger route, search remaining pages, or ask counsel; return the action taken.

    Args:
        item: a checklist item ('charge_sheet_status', ...)
        case_id: see behaviour
        index: the case's page index (default: the saved one)
        reread: re-reads a page with a stronger route, files what it finds and returns the new pseudonymised text, or
            None when no stronger route exists
        adopt: files a page found by the search as the item's document (re-labels it); True when it did
        ask: puts the item's question to counsel; takes (item, question) and returns True when it fits this round
        thresholds: dev-tuned values
        cases_dir: where the saved index lives

    Returns:
        Gap record: the item's name and what was done.
    """
    item = checklist_key(item)
    name, cue = ITEM_NAMES[item], GAP_CUES[item]
    steps: list[str] = []
    if index is None and cases_dir is None:  # no page index at hand: use the `search_pages` tool over the saved one
        return _resolve_with_tools(item, case_id)
    idx = index if index is not None else PageIndex.load(index_path(case_id, cases_dir))

    likely = [p for p in idx.pages if p.doc_type in LIKELY_TYPES[item] and is_weak(p, thresholds)][:MAX_REREAD_PAGES]
    if reread is not None and likely:
        for page in likely:
            text = reread(page)
            if text is not None and cue.search(text):
                steps.append(f"re-read {_where([page])} with a stronger route; found")
                return Gap(item=name, action="; ".join(steps))
        steps.append(f"re-read {_where(likely)} with a stronger route; not found")

    remaining = remaining_pages(idx)
    if remaining:
        hits = [p for p in remaining if cue.search(p.text)]
        if hits and adopt is not None and item in ADOPT_AS and adopt(hits[0], item):
            steps.append(f"searched {_where(remaining)}; found on {_where(hits[:1])}")
            return Gap(item=name, action="; ".join(steps))
        steps.append(f"searched {_where(remaining)}; " + (f"mentioned on {_where(hits[:3])} but not filed" if hits else "not found"))
    else:
        steps.append("searched all pages; not found")

    question = ITEM_QUESTIONS[item]
    asked = ask(item, question) if ask is not None else _ask_through_tool(question, case_id)
    steps.append("asked counsel" if asked else "queued a question for the next round (question limit)")
    return Gap(item=name, action="; ".join(steps))


def checklist_key(item: str) -> str:
    """A checklist key from either the key ('charge_sheet_status') or its name ('charge-sheet status').

    Raises:
        ValueError: for an item that is on neither list.
    """
    if item in GAP_CUES:
        return item
    wanted = re.sub(r"[\s_-]+", " ", item.strip().lower())
    for key, name in ITEM_NAMES.items():
        if wanted in (re.sub(r"[\s_-]+", " ", key), re.sub(r"[\s_-]+", " ", name.lower())):
            return key
    raise ValueError(f"unknown checklist item {item!r}")


def _resolve_with_tools(item: str, case_id: str) -> Gap:
    """Gap handling through the tools alone: `search_pages` over the remaining pages, then `ask_user`."""
    from vakeel_sahayak.tools.base import ToolError
    from vakeel_sahayak.tools.intake import documents

    name, cue = ITEM_NAMES[item], GAP_CUES[item]
    hits = documents.search_pages(case_id, name, 5)
    found = [] if isinstance(hits, ToolError) else [h for h in hits if cue.search(str(h.get("text") or h.get("snippet") or ""))]
    if found:
        return Gap(item=name, action=f"searched remaining pages; found on page {found[0]['page']}")
    asked = _ask_through_tool(ITEM_QUESTIONS[item], case_id)
    return Gap(
        item=name,
        action="searched remaining pages; not found; "
        + ("asked counsel" if asked else "queued a question for the next round (question limit)"),
    )


def _ask_through_tool(question: str, case_id: str) -> bool:
    """Default asker: the shared `ask_user` tool (it enforces the per-round limit)."""
    from vakeel_sahayak.tools.base import ToolError
    from vakeel_sahayak.tools.interaction import ask_user

    return not isinstance(ask_user([question], case_id), ToolError)
