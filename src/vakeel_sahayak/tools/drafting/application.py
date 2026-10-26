"""Tools in drafting.application (plan §8.2). Each function has a matching <NAME>_SPEC.

`assemble_application` is a thin wrapper: it reads the brief, the approved dossier, the List of Dates and the uploaded
documents from the case's event log (views, plan §3.3) and hands them to `export.application.assemble_application_docx`
(the Phase 5 python-docx builder, which exists and is also what `export.exporter.export_case` and the export API call).
The tool returns the real path of a draft DOCX. Gate rule: the draft goes to `<cases_dir>/<case_id>/draft/`, never to
`.../export/`, which only `export_case` fills and only after counsel's Gate 2; the draft carries the "AI-generated draft"
banner and is not an export. Anything the builder raises other than a stub is returned by `BaseAgent.call_tool` as a
ToolError.
"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec

PHASE5_MESSAGE = (
    "assemble_application is not available: the court-ready DOCX builder "
    "(export.application.assemble_application_docx) raised NotImplementedError"
)  # only used if the builder is ever stubbed out again; the builder is implemented today


def assemble_application(case_id: str) -> str | ToolError:
    """Fill the python-docx template from the brief. (plan §8.2)

    Args:
        case_id: the case (its brief, dossier, timeline and documents come from its event log)

    Returns:
        Path of the draft DOCX (under `draft/`, not `export/`), or a ToolError for an invalid or bulk case id. Assembling a
        draft is not exporting: no gate is checked, and no file is ever written into the gated `export/` folder here.
    """
    from vakeel_sahayak.export.application import assemble_application_docx
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.tools.drafting.export_tool import single_case_id
    from vakeel_sahayak.tools.runtime import get_runtime

    one = single_case_id("assemble_application", case_id)
    if isinstance(one, ToolError):
        return one
    case_id = one
    runtime = get_runtime()
    state = CaseState(case_id, runtime.event_log(case_id))
    brief = state.brief()
    report = state.ingestion_report()
    docs = list(report.documents) if report is not None else []
    out_dir = Path(runtime.config.paths.cases_dir) / case_id / "draft"
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
