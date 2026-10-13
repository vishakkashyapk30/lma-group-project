"""Tools in caselaw.reasoning (plan §5.1, §8.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, Factor, OrderPart, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, invalid, parse_filters


def search_reasoning(
    query: str,
    factor: Factor | None = None,
    section_family: list[str] | None = None,
    before: str | None = None,
    outcome: str | None = None,
    court: str | None = None,
    k: int = 10,
) -> list[ParagraphRecord] | ToolError:
    """Hybrid BM25 + BGE-M3 with metadata pre-filter over reasoning paragraphs. (plan §5.1)

    Args:
        query: see behaviour
        factor: see behaviour
        section_family: see behaviour
        before: only documents dated before the case's order; required (leakage rule, plan §2)
        outcome: see behaviour
        court: see behaviour
        k: see behaviour

    Returns:
        Paragraphs.
    """
    tool = "search_reasoning"
    if err := check_search_args(tool, query, k, before):
        return err
    parsed, family, err = parse_filters(tool, factor, section_family)
    if err:
        return err
    return call_store(
        tool, StoreName.CASELAW_REASONING,
        lambda s: s.search(query, factor=parsed, section_family=family, before=before, outcome=outcome, court=court, k=k),
    )  # fmt: skip


def get_paragraph(doc_id: str, para: int) -> ParagraphRecord | ToolError:
    """Fetch one reasoning paragraph by id; a submission paragraph is refused. (plan §8.1)

    Args:
        doc_id: see behaviour
        para: see behaviour

    Returns:
        ParagraphRecord.
    """
    if not isinstance(doc_id, str) or not doc_id.strip():
        return invalid("get_paragraph", "doc_id must not be empty")
    if not isinstance(para, int) or isinstance(para, bool) or para < 1:
        return invalid("get_paragraph", "para must be an integer of at least 1")
    return call_store("get_paragraph", StoreName.CASELAW_REASONING, lambda s: _reasoning_only(s.get_paragraph(doc_id, para)))


def _reasoning_only(record: ParagraphRecord) -> ParagraphRecord:
    """Submissions (defense, prosecution) are for coverage and phrasing, never authority: only reasoning can be cited (plan §5.1)."""
    if record.part != OrderPart.REASONING:
        raise LookupError(
            f"paragraph {record.para} of {record.doc_id} is part of the {record.part.value}, not the court's reasoning; it cannot be cited"
        )
    return record


SEARCH_REASONING_SPEC = ToolSpec(
    name="search_reasoning",
    description="Hybrid BM25 + BGE-M3 with metadata pre-filter over reasoning paragraphs.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK],
    stores=[StoreName.CASELAW_REASONING],
    plan_ref="§5.1",
)

GET_PARAGRAPH_SPEC = ToolSpec(
    name="get_paragraph",
    description="Fetch one paragraph by id.",
    agents=[AgentName.VAKEEL],
    stores=[StoreName.CASELAW_REASONING],
    plan_ref="§8.1",
)
