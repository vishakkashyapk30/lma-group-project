"""Tools in dossier (plan §7.1, §7.3, §7.4). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import SpanCheckResult


def extract_dossier(case_id: str, fields: list[str] | None = None) -> CaseDossier:
    """Fine-tuned Qwen3-4B extraction from the case shelf, with a quote per field. (plan §7.1)

    Args:
        case_id: see behaviour
        fields: restrict to fields that failed the check

    Returns:
        CaseDossier.
    """
    raise NotImplementedError


def span_check(value: Any, quote: str) -> SpanCheckResult:
    """NLI test that the quote supports the value. (plan §7.1)

    Args:
        value: see behaviour
        quote: see behaviour

    Returns:
        SpanCheckResult.
    """
    raise NotImplementedError


def rights_check(case_id: str, as_of: str | None = None) -> RightsReport:
    """Run the Rights Radar rules engine. (plan §7.3)

    Args:
        case_id: see behaviour
        as_of: see behaviour

    Returns:
        RightsReport.
    """
    from datetime import date

    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.rights.engine import RightsEngine
    from vakeel_sahayak.tools.runtime import get_runtime

    state = CaseState(case_id, get_runtime().event_log(case_id))
    return RightsEngine().run(state.dossier(), state.timeline(), as_of or date.today().isoformat())


def diff_case_state(case_id: str, since_hash: str | None = None) -> ChangeSet:
    """Diff current case state against the last approved state. (plan §7.4)

    Args:
        case_id: see behaviour
        since_hash: see behaviour

    Returns:
        ChangeSet.
    """
    raise NotImplementedError


EXTRACT_DOSSIER_SPEC = ToolSpec(
    name="extract_dossier",
    description="Fine-tuned Qwen3-4B extraction from the case shelf, with a quote per field.",
    agents=[AgentName.PESHKAR],
    stores=[StoreName.CASE_DOCS],
    plan_ref="§7.1",
)

SPAN_CHECK_SPEC = ToolSpec(
    name="span_check",
    description="NLI test that the quote supports the value.",
    agents=[AgentName.PESHKAR],
    stores=[],
    plan_ref="§7.1",
)

RIGHTS_CHECK_SPEC = ToolSpec(
    name="rights_check",
    description="Run the Rights Radar rules engine.",
    agents=[AgentName.PESHKAR, AgentName.VAKEEL, AgentName.SUTRADHAR],
    stores=[StoreName.CASE_TIMELINE, StoreName.CASE_FACTS],
    plan_ref="§7.3",
)

DIFF_CASE_STATE_SPEC = ToolSpec(
    name="diff_case_state",
    description="Diff current case state against the last approved state.",
    agents=[AgentName.PESHKAR],
    stores=[StoreName.CASE_FACTS, StoreName.CASE_TIMELINE],
    plan_ref="§7.4",
)
