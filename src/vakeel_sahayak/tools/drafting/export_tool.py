"""Tools in drafting.export_tool (plan §8.1, §16). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, ExportFormat
from vakeel_sahayak.tools.base import ToolSpec


def export(case_id: str, format: ExportFormat) -> list[str]:
    """Gated export: raises unless Gate 2 is approved for this case; no bulk export. (plan §8.1, §16)

    Args:
        case_id: see behaviour
        format: see behaviour

    Returns:
        Paths of exported files.
    """
    from vakeel_sahayak.export.exporter import export_case
    from vakeel_sahayak.record.gates import assert_export_allowed
    from vakeel_sahayak.tools.runtime import get_runtime

    assert_export_allowed(get_runtime().event_log(case_id), case_id)  # raises GateNotApproved without Gate 2
    return export_case(case_id, format)


EXPORT_SPEC = ToolSpec(
    name="export",
    description="Gated export: raises unless Gate 2 is approved for this case; no bulk export.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1, §16",
    gated=True,
)
