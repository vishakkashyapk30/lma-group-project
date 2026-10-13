"""Tools in advocacy.arguments (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, Factor, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, parse_filters


def search_arguments(
    query: str,
    factor: Factor | None = None,
    section_family: list[str] | None = None,
    before: str | None = None,
    k: int = 10,
) -> list[ParagraphRecord] | ToolError:
    """Defense-submission paragraphs for coverage and phrasing; never cited as authority. (plan §5.1)

    Args:
        query: see behaviour
        factor: see behaviour
        section_family: see behaviour
        before: only documents dated before the case's order; required (leakage rule, plan §2)
        k: see behaviour

    Returns:
        Paragraphs.
    """
    tool = "search_arguments"
    if err := check_search_args(tool, query, k, before):
        return err
    parsed, family, err = parse_filters(tool, factor, section_family)
    if err:
        return err
    return call_store(
        tool, StoreName.ADVOCACY_ARGUMENTS,
        lambda s: s.search(query, factor=parsed, section_family=family, before=before, k=k),
    )  # fmt: skip


SEARCH_ARGUMENTS_SPEC = ToolSpec(
    name="search_arguments",
    description="Defense-submission paragraphs for coverage and phrasing; never cited as authority.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.ADVOCACY_ARGUMENTS],
    plan_ref="§5.1",
)
