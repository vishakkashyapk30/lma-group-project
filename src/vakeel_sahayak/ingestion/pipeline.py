"""Reading and categorising files: the survey and categorise steps of Munshi's loop without any agent state (plan §4.3 steps 1-2).

`read_file` routes every page of a file through the ladder. `split_and_label` splits the pages into documents and
labels each one. Raw page text lives in these objects only while a run lasts: it is never written anywhere before it
has been pseudonymised.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from vakeel_sahayak.ingestion.bundles import split_into_documents
from vakeel_sahayak.ingestion.classify import LlmClassifier, label_document
from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.kinds import file_kind, kind_label
from vakeel_sahayak.ingestion.ladder import RouteOutcome, route_page_from
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.ingestion.source import SourceError, open_source
from vakeel_sahayak.privacy.injection_guard import detect_instruction_like
from vakeel_sahayak.schemas.enums import DocumentType, InputKind, PageStatus, ParseRoute
from vakeel_sahayak.schemas.ingestion_report import PageRoute

INJECTION_NOTE = "injection_guard: instruction-like text flagged (kept as data, never acted on)"


@dataclass
class PageRead:
    """One page after routing: the outcome, its raw text and any instruction-like lines found in it."""

    file: str
    path: str
    page: int
    outcome: RouteOutcome
    flagged_lines: list[str] = field(default_factory=list)
    missed_lines: list[str] = field(default_factory=list)  # instruction-like lines the guard would have flagged (S17c arm `no_guard`: nothing is flagged or dropped)
    extra_log: list[str] = field(default_factory=list)  # steps after routing, for example the translation engine

    @property
    def raw(self) -> str:
        """The page's text as read (not pseudonymised: keep in memory only)."""
        return self.outcome.text

    @property
    def unreadable(self) -> bool:
        """Whether the page failed every route."""
        return self.outcome.status == PageStatus.UNREADABLE

    def page_route(self) -> PageRoute:
        """The page's entry in the IngestionReport: kind, the route log, OCR confidence and status."""
        kind = self.outcome.kind or InputKind.K2_SCANNED
        sig = self.outcome.signals
        log = [*self.outcome.log, *self.extra_log, *([INJECTION_NOTE] if self.flagged_lines else [])]
        return PageRoute(
            page=self.page,
            kind=kind_label(kind, sig),
            route=log,
            ocr_conf=round(self.outcome.ocr_conf, 2) if self.outcome.ocr_conf is not None else None,
            status=self.outcome.status,
            confidence=self.outcome.confidence if self.outcome.low_confidence else None,
        )


@dataclass
class FileRead:
    """A file after the survey: its pages, or why it could not be opened."""

    path: str
    name: str
    kind: InputKind | None
    pages: list[PageRead] = field(default_factory=list)
    error: str | None = None  # why the file could not be read: a locked or broken file (K9) or a missing library
    error_kind: str | None = None  # 'locked', 'broken', 'unsupported' or 'unavailable' (a library is missing)


@dataclass
class DocRead:
    """A document found in a file: a page range, its label and its pages."""

    doc_id: str
    file: FileRead
    doc_type: DocumentType
    confidence: float
    first: int
    last: int
    pages: list[PageRead]

    @property
    def lang(self) -> str:
        """'hi', 'en' or 'mixed' over the document's readable text."""
        return lang_of("\n".join(p.raw for p in self.pages if p.raw.strip()))


def flag_instruction_lines(text: str) -> list[str]:
    """Lines that look like instructions aimed at the model; they are data, never acted on.

    A line is flagged when it triggers the guard alone. Two neighbouring lines that only trigger it together (an
    instruction broken across a line wrap) are both flagged; a clean line next to an instruction is not.
    """
    lines = [ln for ln in text.split("\n") if ln.strip()]
    alone = [detect_instruction_like(ln) for ln in lines]
    flagged = [ln for ln, hit in zip(lines, alone, strict=True) if hit]
    for i in range(len(lines) - 1):
        if not alone[i] and not alone[i + 1] and detect_instruction_like(f"{lines[i]} {lines[i + 1]}"):
            flagged += [lines[i], lines[i + 1]]
    return list(dict.fromkeys(flagged))


def read_page(path: str, page: int, thresholds: dict[str, float], max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
              min_route: ParseRoute | None = None, guard: bool = True, keep_weak: bool = False) -> PageRead:  # fmt: skip
    """Route one page and check its text for instruction-like lines (`guard=False`: S17c arm, the lines are only counted as missed)."""
    outcome = route_page_from(path, page, thresholds, max_route, min_route, keep_weak)
    return page_read(path, page, outcome, guard)


def page_read(path: str, page: int, outcome: RouteOutcome, guard: bool = True) -> PageRead:
    """A `PageRead` for a routed page: its instruction-like lines are flagged (guard on) or only counted as missed (guard off)."""
    lines = flag_instruction_lines(outcome.text)
    return PageRead(Path(path).name, path, page, outcome, lines if guard else [], [] if guard else lines)


def read_file(
    path: str,
    thresholds: dict[str, float],
    max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
    on_page: Callable[[PageRead], None] | None = None,
    min_route: ParseRoute | None = None,
    guard: bool = True,
    keep_weak: bool = False,
) -> FileRead:
    """Survey a file: compute signals for every page and run the cheapest acceptable route (plan §4.3 step 1).

    Args:
        path: the file
        thresholds: dev-tuned values
        max_route: ladder cap (baselines)
        on_page: called after each page (the agent logs the route to the event log here)
        min_route: weakest rung allowed for every page (P7 image-only passes VISION)
        guard: False for the S17c arm (instruction-like lines are not flagged or dropped)
        keep_weak: keep a near-miss text layer as a low-confidence read instead of asking counsel (`munshi_keep_weak_text`)

    Returns:
        FileRead. A locked or broken file has no pages and an `error` (K9: ask counsel, never guess).

    Raises:
        ModelUnavailable: PyMuPDF is missing and the file is a PDF.
    """
    name = Path(path).name
    try:
        source = open_source(path)
    except SourceError as exc:
        return FileRead(path, name, InputKind.K9_LOCKED_OR_BROKEN, error=f"{exc}", error_kind=exc.kind)
    pages: list[PageRead] = []
    for number in range(1, source.page_count + 1):
        read = read_page(path, number, thresholds, max_route, min_route, guard, keep_weak)
        pages.append(read)
        if on_page:
            on_page(read)
    return FileRead(path, name, file_kind(path), pages)


def page_signals(pages: list[PageRead]) -> list[PageSignals]:
    """The final signals of each page."""
    return [p.outcome.signals or PageSignals() for p in pages]


def split_and_label(
    file: FileRead,
    thresholds: dict[str, float],
    *,
    split: bool = True,
    fallback: LlmClassifier | None = None,
) -> list[DocRead]:
    """Split a file into documents and label each (plan §4.3 step 2); `doc_id` is filled by the caller.

    Args:
        file: the surveyed file
        thresholds: dev-tuned values
        split: False keeps the whole file as one document (variant P6: no bundle splitting)
        fallback: language-model classifier for low-confidence labels

    Returns:
        Documents in page order; empty for a file without pages.
    """
    if not file.pages:
        return []
    texts = [p.raw for p in file.pages]
    ranges = split_into_documents(texts, page_signals(file.pages), thresholds) if split else [(1, len(file.pages))]
    docs: list[DocRead] = []
    for first, last in ranges:
        pages = file.pages[first - 1 : last]
        body = "\n\n".join(p.raw for p in pages if p.raw.strip())
        opening = next((p.raw for p in pages if p.raw.strip()), "")
        doc_type, confidence = label_document(body, opening, fallback=fallback, thresholds=thresholds)
        docs.append(DocRead("", file, doc_type, confidence, first, last, pages))
    return docs
