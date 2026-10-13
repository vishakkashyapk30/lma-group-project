"""Tools in intake.documents (plan §4.1 K8, §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, StoreName
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import FileItemResult


def split_bundle(file_path: str) -> list[DocumentEntry]:
    """Split a bundle into documents. (plan §4.1 K8)

    Args:
        file_path: see behaviour

    Returns:
        DocumentEntry skeletons.
    """
    raise NotImplementedError


def classify_document(file_path: str, pages: list[int]) -> tuple[DocumentType, float]:
    """Label a document. (plan §4.3)

    Args:
        file_path: see behaviour
        pages: see behaviour

    Returns:
        (type, confidence).
    """
    raise NotImplementedError


def file_item(store: StoreName, item: dict[str, Any], source: SourceRef) -> FileItemResult:
    """Write an item to a case-shelf store with its source (document, page, box, route, language, confidence). Names pseudonymised before filing. (plan §4.3)

    Args:
        store: see behaviour
        item: see behaviour
        source: see behaviour

    Returns:
        FileItemResult.
    """
    raise NotImplementedError


def search_pages(case_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
    """Search the not-yet-read pages of the case file during gap checks. (plan §4.3)

    Args:
        case_id: see behaviour
        query: see behaviour
        k: see behaviour

    Returns:
        Page hits.
    """
    raise NotImplementedError


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
