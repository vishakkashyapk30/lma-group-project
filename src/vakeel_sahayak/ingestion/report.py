"""Assemble the IngestionReport (plan §4.6)."""

from __future__ import annotations

from vakeel_sahayak.ingestion.questions import group_unreadable, question_limit, unreadable_question
from vakeel_sahayak.schemas.enums import DocumentType, PageStatus
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, FiledCounts, Gap, IngestionReport


def build_report(
    case_id: str,
    file: str,
    documents: list[DocumentEntry],
    filed: FiledCounts,
    gaps: list[Gap],
    questions: list[str],
    max_questions: int | None = None,
) -> IngestionReport:
    """Assemble Munshi's output.

    The report has the shape of plan §4.6 exactly. Documents keep their order, and the result is validated: document
    ids are unique and each `pages` is [first, last] with first <= last. Questions follow the round rules of plan §4.3:
    they are de-duplicated, every unreadable page (status UNREADABLE in the page routes) is covered by ONE grouped
    question, and no more than the round limit are kept (the grouped question always stays; the others keep their order).

    Args:
        case_id: see behaviour
        file: see behaviour
        documents: see behaviour
        filed: see behaviour
        gaps: see behaviour
        questions: see behaviour
        max_questions: round limit (default: configs/budgets.yaml, 3)

    Returns:
        IngestionReport.

    Raises:
        ValueError: for duplicate document ids or a bad page range.
    """
    ids = [d.doc_id for d in documents]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate document ids in {ids}")
    for d in documents:
        if len(d.pages) != 2 or d.pages[0] > d.pages[1] or d.pages[0] < 1:
            raise ValueError(f"document {d.doc_id}: pages must be [first, last] from 1, got {d.pages}")
    limit = max_questions if max_questions is not None else question_limit()
    final = round_questions(file, documents, questions, limit)
    return IngestionReport(case_id=case_id, file=file, documents=documents, filed=filed, gaps=gaps, questions=final)


def _doc_label(doc_type: DocumentType) -> str:
    """How a document type reads in a question ('FIR', 'Remand Order')."""
    return "FIR" if doc_type == DocumentType.FIR else doc_type.value.replace("_", " ").title()


def round_questions(file: str, documents: list[DocumentEntry], questions: list[str], limit: int) -> list[str]:
    """Apply the round rules: unreadable pages in one question, at most `limit` questions, order kept."""
    unique = group_unreadable(list(dict.fromkeys(q.strip() for q in questions if q.strip())))
    unreadable = [
        (page_route.page, _doc_label(d.type)) for d in documents for page_route in d.page_routes if page_route.status == PageStatus.UNREADABLE
    ]
    grouped_at: int | None = None
    if unreadable:
        pages = sorted({p for p, _ in unreadable})
        asks = [i for i, q in enumerate(unique) if "unreadable" in q.lower()]
        if asks and all(str(p) in unique[asks[0]] for p in pages):
            grouped_at = asks[0]
        else:
            text = unreadable_question([(file, page, label) for page, label in unreadable])
            if asks:
                unique[asks[0]] = text
                grouped_at = asks[0]
            else:
                unique.insert(0, text)
                grouped_at = 0
    if len(unique) <= limit:
        return unique
    others = [i for i in range(len(unique)) if i != grouped_at]
    keep = set(others[: max(0, limit - (1 if grouped_at is not None else 0))]) | ({grouped_at} if grouped_at is not None else set())
    return [q for i, q in enumerate(unique) if i in keep]
