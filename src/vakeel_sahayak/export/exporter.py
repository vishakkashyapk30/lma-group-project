"""Gated export entry point used by the export tool and API (plan §8.1, §16).

The guard runs before anything is read or written: without counsel's Gate 2 approval for this very case, `export_case`
raises and no file exists. Files go to `<cases_dir>/<case_id>/export/`, so every path names exactly one case (no bulk
export). The writers are looked up on their modules at call time (`application.assemble_application_docx`, ...).
"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.export import application, hearing_card, list_of_dates, objections, pdf
from vakeel_sahayak.schemas.enums import ExportFormat


def export_case(case_id: str, format: ExportFormat) -> list[str]:
    """Run GateGuard.assert_export_allowed, then write application, List of Dates, objections sheet and hearing card.

    Args:
        case_id: exactly one case
        format: DOCX, or PDF (the four DOCX files plus a PDF of each, through LibreOffice)

    Returns:
        Paths of exported files.

    Raises:
        ValueError: a bulk, empty or malformed case id.
        PermissionError: no Gate 2 approval by counsel for this case (`GateNotApproved`).
    """
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.record.gates import assert_export_allowed
    from vakeel_sahayak.tools.base import ToolError
    from vakeel_sahayak.tools.drafting.export_tool import single_case_id
    from vakeel_sahayak.tools.runtime import get_runtime

    one = single_case_id("export", case_id)
    if isinstance(one, ToolError):
        raise ValueError(one.message)
    fmt = ExportFormat(format)
    runtime = get_runtime()
    log = runtime.event_log(one)
    assert_export_allowed(log, one)

    state = CaseState(one, log)
    brief, sparring, timeline = state.brief(), state.sparring(), state.timeline()
    report = state.ingestion_report()
    docs = list(report.documents) if report is not None else []
    out = Path(runtime.config.paths.cases_dir) / one / "export"
    out.mkdir(parents=True, exist_ok=True)

    rights = state.rights_report()
    written = [
        application.assemble_application_docx(brief, state.dossier(), timeline, docs, str(out / "application.docx"), rights=rights),
        list_of_dates.write_list_of_dates_docx(timeline, one, str(out / "list_of_dates.docx")),
        objections.write_objections_docx(sparring, one, str(out / "objections_sheet.docx")),
        hearing_card.write_hearing_card_docx(hearing_card.build_hearing_card(brief, sparring, one), one, str(out / "hearing_card.docx"), rights=rights),
    ]
    if fmt == ExportFormat.PDF:
        written += [pdf.docx_to_pdf(p) for p in written]
    return written
