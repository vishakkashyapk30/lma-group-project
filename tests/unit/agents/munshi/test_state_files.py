"""Munshi reads the files handed over on the graph state (plan §4.3, §13.6 flow 1).

The API upload route, the LangGraph intake node and the evaluation driver all pass the uploaded files as `CaseGraphState.files`;
`MunshiAgent.run` used to read only `add_files` and the case inbox, so an upload through the API produced an empty IngestionReport
(no documents, every dossier field UNSUPPORTED). This runs the real offline tools on a constructed text PDF, as the upload route does.
"""

from __future__ import annotations

from tests.fixtures import pdfgen


def test_run_reads_the_files_on_the_state(pdfs, require_pymupdf, monkeypatch):
    monkeypatch.setenv("VS_MODELS", "offline")
    monkeypatch.setenv("VS_LLM_BACKEND", "offline")
    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.api import deps, service
    from vakeel_sahayak.orchestration.state import CaseGraphState
    from vakeel_sahayak.schemas.enums import AgentName

    pdf = pdfs.text("bundle.pdf", [pdfgen.REMAND_PAGE, pdfgen.BAIL_ORDER_PAGE])
    log = deps.get_event_log("case-0001")
    state = CaseGraphState(case_id="case-0001", log_path=log.db_path, files=[str(pdf)])
    munshi = create_agent(AgentName.MUNSHI, service.agent_context(log, "case-0001"))
    try:
        report = munshi.run(state).ingestion
    finally:
        munshi.close()
    assert report is not None
    assert "bundle.pdf" in report.file
    assert report.documents, "Munshi read nothing from the files on the state"
    assert sum(len(range(d.pages[0], d.pages[-1] + 1)) for d in report.documents) == 2
