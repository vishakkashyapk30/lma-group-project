"""Tools in drafting.application (plan §8.2). Each function has a matching <NAME>_SPEC.

`assemble_application` is a thin wrapper: it reads the brief, the approved dossier, the List of Dates and the uploaded
documents from the case's event log (views, plan §3.3) and hands them to `export.application.assemble_application_docx`,
which fills the python-docx template. That builder is Phase 5; until it exists the tool raises a clear
NotImplementedError (which `BaseAgent.call_tool` returns as a `not_implemented` ToolError), never a fake file.
"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec

PHASE5_MESSAGE = (
    "assemble_application needs the court-ready DOCX builder (export.application.assemble_application_docx), "
    "which is built in Phase 5 (API and export); it is still a stub"
)


def assemble_application(case_id: str) -> str | ToolError:
    """Fill the python-docx template from the brief. (plan §8.2)

    Args:
        case_id: the case (its brief, dossier, timeline and documents come from its event log)

    Returns:
        Path of the DOCX, or a ToolError for an invalid case id or a case with no drafted grounds.

    Raises:
        NotImplementedError: the Phase 5 DOCX builder is still a stub.
    """
    from vakeel_sahayak.export.application import assemble_application_docx
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.schemas.ids import check_case_id
    from vakeel_sahayak.tools.runtime import get_runtime

    try:
        check_case_id(case_id)
    except ValueError as exc:
        return ToolError(tool="assemble_application", kind="invalid_input", message=str(exc), retryable=False)
    runtime = get_runtime()
    state = CaseState(case_id, runtime.event_log(case_id))
    brief = state.brief()
    if not brief.grounds:
        return ToolError(tool="assemble_application", kind="not_ready", message="the case has no drafted grounds yet", retryable=False)
    report = state.ingestion_report()
    docs = list(report.documents) if report is not None else []
    out_dir = Path(runtime.config.paths.cases_dir) / case_id / "export"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        return assemble_application_docx(brief, state.dossier(), state.timeline(), docs, str(out_dir / "application.docx"))
    except NotImplementedError as exc:
        raise NotImplementedError(PHASE5_MESSAGE) from exc


ASSEMBLE_APPLICATION_SPEC = ToolSpec(
    name="assemble_application",
    description="Fill the python-docx template from the brief.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.2",
)
