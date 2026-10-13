"""Tools in law.statutes (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.store_rows import StatuteRow
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.runtime import get_runtime


def get_statute(code: str, section: str) -> StatuteRow | ToolError:
    """Exact lookup of a section. (plan §5.1)

    Args:
        code: see behaviour
        section: see behaviour

    Returns:
        StatuteRow.
    """
    try:
        return get_runtime().statutes().get(code, section)
    except (LookupError, ValueError) as exc:
        return ToolError(tool="get_statute", kind="not_found", message=str(exc), retryable=False)


def search_statutes(query: str, code: str | None = None, k: int = 5) -> list[StatuteRow] | ToolError:
    """BM25 over statute text ('which section covers...'). (plan §5.1)

    Args:
        query: see behaviour
        code: see behaviour
        k: see behaviour

    Returns:
        Rows.
    """
    if not query.strip() or not 1 <= k <= 50:
        return ToolError(
            tool="search_statutes", kind="invalid_input", message="need a query and 1 <= k <= 50", retryable=True
        )
    try:
        return get_runtime().statutes().search(query, code, k)
    except ValueError as exc:
        return ToolError(tool="search_statutes", kind="invalid_input", message=str(exc), retryable=True)


GET_STATUTE_SPEC = ToolSpec(
    name="get_statute",
    description="Exact lookup of a section.",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK],
    stores=[StoreName.LAW_STATUTES],
    plan_ref="§5.1",
)

SEARCH_STATUTES_SPEC = ToolSpec(
    name="search_statutes",
    description="BM25 over statute text ('which section covers...').",
    agents=[AgentName.SUTRADHAR, AgentName.ABHIYOJAK],
    stores=[StoreName.LAW_STATUTES],
    plan_ref="§5.1",
)
