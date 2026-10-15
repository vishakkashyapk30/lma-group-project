"""Tools in case.facts (plan §5.1). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.dossier import DossierFields
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, invalid


def get_fact(case_id: str, field: str) -> TrackedField[Any] | ToolError:
    """Exact lookup of a dossier field with status and source. (plan §5.1)

    Args:
        case_id: see behaviour
        field: see behaviour

    Returns:
        The tracked field.
    """
    try:
        check_case_id(case_id)
    except (ValueError, TypeError) as exc:
        return invalid("get_fact", str(exc))
    fields = DossierFields.model_fields
    if field not in fields:
        return ToolError(
            tool="get_fact",
            kind="unknown_field",
            message=f"{field!r} is not a dossier field: {sorted(fields)}",
            retryable=True,
        )
    return call_store("get_fact", StoreName.CASE_FACTS, lambda s: s.get(field), case_id=case_id)


GET_FACT_SPEC = ToolSpec(
    name="get_fact",
    description="Exact lookup of a dossier field with status and source.",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK, AgentName.PAIROKAR],
    stores=[StoreName.CASE_FACTS],
    plan_ref="§5.1",
)
