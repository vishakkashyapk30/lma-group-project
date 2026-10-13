"""Tools in advocacy.objections (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, Factor, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, parse_filters


def search_objections(
    query: str,
    factor: Factor | None = None,
    section_family: list[str] | None = None,
    before: str | None = None,
    k: int = 10,
) -> list[ParagraphRecord] | ToolError:
    """Prosecution-submission paragraphs. (plan §5.1)

    Args:
        query: see behaviour
        factor: see behaviour
        section_family: see behaviour
        before: only documents dated before the case's order; required (leakage rule, plan §2)
        k: see behaviour

    Returns:
        Paragraphs.
    """
    tool = "search_objections"
    if err := check_search_args(tool, query, k, before):
        return err
    parsed, family, err = parse_filters(tool, factor, section_family)
    if err:
        return err
    return call_store(
        tool, StoreName.ADVOCACY_OBJECTIONS,
        lambda s: s.search(query, factor=parsed, section_family=family, before=before, k=k),
    )  # fmt: skip


SEARCH_OBJECTIONS_SPEC = ToolSpec(
    name="search_objections",
    description="Prosecution-submission paragraphs.",
    agents=[AgentName.SUTRADHAR, AgentName.ABHIYOJAK],
    stores=[StoreName.ADVOCACY_OBJECTIONS],
    plan_ref="§5.1",
)
