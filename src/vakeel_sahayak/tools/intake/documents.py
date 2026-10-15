"""Tools in intake.documents (plan §4.1 K8, §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.ingestion.classify import label_document
from vakeel_sahayak.ingestion.filing import Filer
from vakeel_sahayak.ingestion.pageindex import PageIndex, index_path
from vakeel_sahayak.ingestion.pipeline import read_file, read_page, split_and_label
from vakeel_sahayak.ingestion.thresholds import load_thresholds
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, StoreName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.intake._common import check_file, check_page, guarded
from vakeel_sahayak.tools.store_call import check_search_args, invalid
from vakeel_sahayak.tools.types import FileItemResult

_CASE_STORES = (StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS)


def split_bundle(file_path: str) -> list[DocumentEntry] | ToolError:
    """Split a bundle into documents. (plan §4.1 K8)

    Args:
        file_path: see behaviour

    Returns:
        DocumentEntry skeletons: ids d1, d2, ..., the label and its confidence, the page range, the language and the
        route of each page.
    """
    if err := check_file("split_bundle", file_path):
        return err

    def run() -> list[DocumentEntry]:
        thresholds = load_thresholds()
        surveyed = read_file(file_path, thresholds)
        if surveyed.error:
            raise_unreadable(surveyed.error)
        entries = []
        for n, doc in enumerate(split_and_label(surveyed, thresholds), start=1):
            entries.append(
                DocumentEntry(
                    doc_id=f"d{n}",
                    type=doc.doc_type,
                    pages=[doc.first, doc.last],
                    lang=doc.lang,
                    type_confidence=doc.confidence,
                    page_routes=[p.page_route() for p in doc.pages],
                )
            )
        return entries

    return guarded("split_bundle", run)


def raise_unreadable(error: str) -> None:
    """Raise the SourceError a locked or broken file stands for (error is 'kind: message')."""
    from vakeel_sahayak.ingestion.source import SourceError

    kind, _, message = error.partition(": ")
    raise SourceError(kind, message)


def classify_document(file_path: str, pages: list[int]) -> tuple[DocumentType, float] | ToolError:
    """Label a document. (plan §4.3)

    Args:
        file_path: see behaviour
        pages: page numbers of the document, from 1

    Returns:
        (type, confidence).
    """
    tool = "classify_document"
    if not isinstance(pages, list) or not pages:
        return invalid(tool, "pages must be a non-empty list of page numbers")
    for number in pages:
        if err := check_page(tool, file_path, number):
            return err

    def run() -> tuple[DocumentType, float]:
        thresholds = load_thresholds()
        texts = [read_page(file_path, n, thresholds).raw for n in sorted(set(pages))]
        body = "\n\n".join(t for t in texts if t.strip())
        return label_document(body, next((t for t in texts if t.strip()), ""), thresholds=thresholds)

    return guarded(tool, run)


def file_item(store: StoreName, item: dict[str, Any], source: SourceRef) -> FileItemResult | ToolError:
    """Write an item to a case-shelf store with its source (document, page, box, route, language, confidence). Names pseudonymised before filing. (plan §4.3)

    Args:
        store: case.docs (item = chunk fields), case.timeline (item = date, label) or case.facts (item = field, value)
        item: the item; a `case_id` key names the case, otherwise the runtime's current case is used
        source: where it came from

    Returns:
        FileItemResult.
    """
    tool = "file_item"
    from vakeel_sahayak.tools.runtime import get_runtime

    case = (item.get("case_id") if isinstance(item, dict) else None) or get_runtime().current_case_id
    if not case:
        return invalid(tool, "no case: put a 'case_id' key in item, or set the runtime's current case")
    try:
        check_case_id(case)
    except (ValueError, TypeError) as exc:
        return invalid(tool, str(exc))
    if StoreName(store) not in _CASE_STORES:
        return invalid(tool, f"store must be one of {[s.value for s in _CASE_STORES]}, got {StoreName(store).value!r}")
    if not isinstance(item, dict) or not item:
        return invalid(tool, "item must be a non-empty object")
    payload = {k: v for k, v in item.items() if k != "case_id"}

    def run() -> FileItemResult:
        from vakeel_sahayak.tools.runtime import get_runtime

        runtime = get_runtime()
        filer = Filer(case, runtime.event_log(case), cases_dir=runtime.config.paths.cases_dir)
        try:
            item_id = filer.file_raw_item(StoreName(store), payload, source)
            filer.save_map()
        finally:
            filer.close()
        return FileItemResult(store=StoreName(store), item_id=item_id)

    try:
        return guarded(tool, run)
    except KeyError as exc:  # a facts field that is not a dossier field
        return ToolError(tool=tool, kind="unknown_field", message=str(exc.args[0] if exc.args else exc), retryable=True)


def search_pages(case_id: str, query: str, k: int = 5) -> list[dict[str, Any]] | ToolError:
    """Search the not-yet-read pages of the case file during gap checks. (plan §4.3)

    The search runs over the case's page index (pseudonymised text of every page Munshi has seen), most useful for the
    pages that belong to no typed document or could not be read.

    Args:
        case_id: see behaviour
        query: see behaviour
        k: see behaviour

    Returns:
        Page hits: file, page, doc_id, doc_type, status, score and a snippet.
    """
    tool = "search_pages"
    try:
        check_case_id(case_id)
    except (ValueError, TypeError) as exc:
        return invalid(tool, str(exc))
    if err := check_search_args(tool, query, k, None, need_before=False):
        return err

    def run() -> list[dict[str, Any]]:
        from vakeel_sahayak.tools.runtime import get_runtime

        index = PageIndex.load(index_path(case_id, get_runtime().config.paths.cases_dir))
        hits = []
        for page, score in index.search(query, k):
            at = max(0, page.text.lower().find(query.split()[0].lower()))
            hits.append(
                {
                    "file": page.file,
                    "page": page.page,
                    "doc_id": page.doc_id,
                    "doc_type": page.doc_type,
                    "status": page.status,
                    "score": score,
                    "snippet": page.text[max(0, at - 60) : at + 160],
                }
            )
        return hits

    return guarded(tool, run)


SPLIT_BUNDLE_SPEC = ToolSpec(
    name="split_bundle",
    description="Split a bundle into documents.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.1 K8",
)

CLASSIFY_DOCUMENT_SPEC = ToolSpec(
    name="classify_document", description="Label a document.", agents=[AgentName.MUNSHI], stores=[], plan_ref="§4.3"
)

FILE_ITEM_SPEC = ToolSpec(
    name="file_item",
    description="Write an item to a case-shelf store with its source (document, page, box, route, language, confidence). Names pseudonymised before filing.",
    agents=[AgentName.MUNSHI],
    stores=[StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS],
    plan_ref="§4.3",
)

SEARCH_PAGES_SPEC = ToolSpec(
    name="search_pages",
    description="Search the not-yet-read pages of the case file during gap checks.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.3",
)
