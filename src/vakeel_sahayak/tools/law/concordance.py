"""Tools in law.concordance (plan §5.4). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from datetime import date

from vakeel_sahayak.pipelines.concordance.refs import make_ref
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.stores.registry import open_store
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.types import MapSectionResult, TransferCheckResult


def map_section(code: str, section: str, offence_date: str) -> MapSectionResult | ToolError:
    """Map an IPC/BNS or CrPC/BNSS section across the 2024 change using the concordance graph; offence date decides the era. Unclear mappings are AMBIGUOUS. (plan §5.4)

    Args:
        code: see behaviour
        section: see behaviour
        offence_date: see behaviour

    Returns:
        MapSectionResult.
    """
    try:
        make_ref(code, section)  # unknown act or empty section: ValueError
        if not section.strip() or len(offence_date) != 10:
            raise ValueError("need a section and an offence date as YYYY-MM-DD")
        date.fromisoformat(offence_date)
        return open_store(StoreName.LAW_CONCORDANCE).map_section(code, section, offence_date)
    except ValueError as exc:
        return ToolError(tool="map_section", kind="invalid_input", message=str(exc), retryable=True)
    except LookupError as exc:
        return ToolError(tool="map_section", kind="not_found", message=str(exc), retryable=False)


def transfer_check(old_ref: str, new_ref: str) -> TransferCheckResult | ToolError:
    """Compute SAME_TEXT / CHANGED / NEW from the concordance and a text diff. (plan §5.4)

    Args:
        old_ref: see behaviour
        new_ref: see behaviour

    Returns:
        TransferCheckResult.
    """
    try:
        return open_store(StoreName.LAW_CONCORDANCE).transfer_flag(old_ref, new_ref)
    except ValueError as exc:
        return ToolError(tool="transfer_check", kind="invalid_input", message=str(exc), retryable=True)
    except LookupError as exc:
        return ToolError(tool="transfer_check", kind="not_found", message=str(exc), retryable=False)


MAP_SECTION_SPEC = ToolSpec(
    name="map_section",
    description="Map an IPC/BNS or CrPC/BNSS section across the 2024 change using the concordance graph; offence date decides the era. Unclear mappings are AMBIGUOUS.",
    agents=[AgentName.PESHKAR, AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.LAW_CONCORDANCE],
    plan_ref="§5.4",
)

TRANSFER_CHECK_SPEC = ToolSpec(
    name="transfer_check",
    description="Compute SAME_TEXT / CHANGED / NEW from the concordance and a text diff.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.LAW_CONCORDANCE],
    plan_ref="§5.4",
)
