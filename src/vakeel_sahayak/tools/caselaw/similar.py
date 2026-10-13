"""Tools in caselaw.similar (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.store_rows import FactSignature, SimilarOrderRow
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, check_search_args, parse_filters


def similar_orders(
    facts_text: str, signature: FactSignature | None = None, before: str | None = None, k: int = 10
) -> list[SimilarOrderRow] | ToolError:
    """Whole-order vectors plus structured fact-signature match. Shows reasoning, never grant rates. (plan §5.1)

    Args:
        facts_text: see behaviour
        signature: see behaviour
        before: only orders dated before the case's order; required (leakage rule, plan §2)
        k: see behaviour

    Returns:
        Similar orders (no outcomes, no rates).
    """
    tool = "similar_orders"
    if err := check_search_args(tool, facts_text, k, before):
        return err
    if signature and signature.sections:
        _, _, err = parse_filters(tool, None, signature.sections)
        if err:
            return err
    return call_store(tool, StoreName.CASELAW_SIMILAR, lambda s: s.similar(facts_text, signature, before, k))


SIMILAR_ORDERS_SPEC = ToolSpec(
    name="similar_orders",
    description="Whole-order vectors plus structured fact-signature match. Shows reasoning, never grant rates.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.CASELAW_SIMILAR],
    plan_ref="§5.1",
)
