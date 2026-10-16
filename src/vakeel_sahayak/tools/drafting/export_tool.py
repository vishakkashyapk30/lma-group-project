"""Tools in drafting.export_tool (plan §8.1, §16). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName, ExportFormat
from vakeel_sahayak.tools.base import ToolError, ToolSpec

BULK_CASE_IDS = frozenset({"*", "all", "any", "every", "everything"})


def single_case_id(tool: str, case_id: object) -> str | ToolError:
    """The case id when it names exactly one case; a ToolError for empty, wildcard, list or comma-joined ids (no bulk operations, plan §16)."""
    from vakeel_sahayak.schemas.ids import check_case_id

    if not isinstance(case_id, str) or not case_id.strip() or case_id.strip().lower() in BULK_CASE_IDS:
        return ToolError(tool=tool, kind="invalid_input", message="name exactly one case: bulk or empty case ids are refused", retryable=False)
    try:
        return check_case_id(case_id.strip())
    except ValueError as exc:
        return ToolError(tool=tool, kind="invalid_input", message=str(exc), retryable=False)


def export(case_id: str, format: ExportFormat) -> list[str] | ToolError:
    """Gated export: raises unless Gate 2 is approved for this case; no bulk export. (plan §8.1, §16)

    Args:
        case_id: exactly one case
        format: DOCX or PDF

    Returns:
        Paths of exported files, or a ToolError for a bulk or malformed case id or an unknown format (checked before the guard).

    Raises:
        PermissionError: Gate 2 is not approved for this case (`GateNotApproved`).
    """
    from vakeel_sahayak.export.exporter import export_case
    from vakeel_sahayak.orchestration.gates import GateGuard

    one = single_case_id("export", case_id)
    if isinstance(one, ToolError):
        return one
    try:
        fmt = ExportFormat(format)
    except ValueError:
        return ToolError(tool="export", kind="invalid_input", message=f"format must be one of {[f.value for f in ExportFormat]}", retryable=False)
    GateGuard().assert_export_allowed(one)  # raises GateNotApproved without Gate 2 of this case
    return export_case(one, fmt)


EXPORT_SPEC = ToolSpec(
    name="export",
    description="Gated export: raises unless Gate 2 is approved for this case; no bulk export.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1, §16",
    gated=True,
)
