"""Tools in case.docs (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, DocumentType, StoreName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.store_rows import CaseChunk
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, invalid


def search_case_docs(
    case_id: str, query: str, doc_types: list[DocumentType] | None = None, k: int = 5
) -> list[CaseChunk] | ToolError:
    """Hybrid search over the client's chunks. (plan §5.1)

    Args:
        case_id: see behaviour
        query: see behaviour
        doc_types: see behaviour
        k: see behaviour

    Returns:
        Chunks with page and box.
    """
    tool = "search_case_docs"
    try:
        check_case_id(case_id)
    except (ValueError, TypeError) as exc:
        return invalid(tool, str(exc))
    if err := check_search_args(tool, query, k, None, need_before=False):
        return err
    try:
        types = [DocumentType(t) for t in doc_types] if doc_types else None
    except ValueError:
        return invalid(tool, f"unknown document type in {doc_types!r}: use one of {[t.value for t in DocumentType]}")
    return call_store(tool, StoreName.CASE_DOCS, lambda s: s.search(query, types, k), case_id=case_id)


SEARCH_CASE_DOCS_SPEC = ToolSpec(
    name="search_case_docs",
    description="Hybrid search over the client's chunks.",
    agents=[AgentName.MUNSHI, AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK],
    stores=[StoreName.CASE_DOCS],
    plan_ref="§5.1",
)
