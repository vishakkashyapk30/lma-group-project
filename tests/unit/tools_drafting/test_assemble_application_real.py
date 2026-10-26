"""`assemble_application` runs the real Phase 5 builder: a real DOCX, written to `draft/` and never to the gated `export/` folder."""

from __future__ import annotations

from pathlib import Path

from tests.unit.orchestration import _helpers as h
from vakeel_sahayak.schemas.enums import ClaimCheck
from vakeel_sahayak.tools.drafting.application import assemble_application

CASE = "case-0007"


def test_real_builder_writes_a_draft_not_an_export(tmp_path, monkeypatch, dossier):
    log = h.point_default_log_at(tmp_path, monkeypatch)
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    h.seed_brief_and_sparring(log, CASE, [h.ground("G1", ClaimCheck.SUPPORTED)], [])
    path = assemble_application(CASE)  # Gate 2 not approved
    assert isinstance(path, str) and Path(path).read_bytes()[:2] == b"PK"
    assert Path(path).parent.name == "draft"
    assert not list(Path(path).parent.parent.glob("export/*"))
    import docx

    text = "\n".join(p.text for p in docx.Document(path).paragraphs)
    assert "AI-generated draft" in text or "AI-GENERATED" in text.upper()


def test_vakeel_call_tool_returns_the_real_path_not_a_not_implemented_error(tmp_path, monkeypatch, dossier):
    """`BaseAgent.call_tool('assemble_application')` reaches the real registry function: a path, never a `not_implemented` ToolError."""
    from tests.unit.agents._helpers import build_agent
    from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
    from vakeel_sahayak.tools.base import ToolError

    log = h.point_default_log_at(tmp_path, monkeypatch)
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    h.seed_brief_and_sparring(log, CASE, [h.ground("G1", ClaimCheck.SUPPORTED)], [])
    agent, _, _ = build_agent(VakeelAgent)
    agent.tools = {}  # no scripted toolbox: the call goes to the tool registry
    out = agent.call_tool("assemble_application", case_id=CASE)
    assert not isinstance(out, ToolError), out
    assert out.endswith("application.docx") and Path(out).is_file()
