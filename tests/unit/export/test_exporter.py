"""Gated export entry point (plan §8.1, §16): `export_case` runs `GateGuard.assert_export_allowed` first, then writes the
application, the List of Dates, the objections sheet and the hearing card; PDF goes through headless LibreOffice.

Export works only after Gate 2 of this very case; no bulk export. Refusals raise ValueError or PermissionError (ASSUMPTION; as in
tests/unit/orchestration/test_gates.py). The writers are replaced by recording stubs: what is under test is the guard and the
set of files, not the DOCX content (see test_application.py).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.unit.export._helpers import Spy
from tests.unit.orchestration import _helpers as h
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.export.exporter import export_case
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import ClaimCheck, ExportFormat, SparringVerdict

CASE = "case-0007"
REFUSED = (ValueError, PermissionError)


@pytest.fixture()
def spy(monkeypatch):
    s = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", s.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", s.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", s.pdf)
    return s


def record(tmp_path, monkeypatch, dossier, *, gate2: bool):
    """case-0007 with Gate 1 approved, a clean brief and, if `gate2`, Gate 2 approved."""
    h.point_default_log_at(tmp_path, monkeypatch)
    log = EventLog()
    h.seed_dossier(log, CASE, h.resolved_dossier(dossier))
    h.approve(log, CASE, h.G1, [], "h:0a1b")
    h.seed_brief_and_sparring(log, CASE, [h.ground("G1", ClaimCheck.SUPPORTED)], [h.objection("O1", SparringVerdict.ANSWERED)])
    if gate2:
        h.approve(log, CASE, h.G2)
    return log


@pytest.mark.parametrize("fmt", [ExportFormat.DOCX, ExportFormat.PDF])
def test_export_before_gate_2_is_refused_and_writes_nothing(tmp_path, monkeypatch, dossier, spy, fmt):
    """No Gate 2, no export: the guard raises, and no writer runs, so no file exists (plan §16, T7 'unapproved-export attempts')."""
    record(tmp_path, monkeypatch, dossier, gate2=False)
    with pytest.raises(REFUSED):
        export_case(CASE, fmt)
    assert spy.calls == []
    assert [p for p in tmp_path.rglob("*") if p.suffix in (".docx", ".pdf")] == []


def test_export_for_a_case_without_a_record_is_refused(tmp_path, monkeypatch, spy):
    h.point_default_log_at(tmp_path, monkeypatch)
    with pytest.raises(REFUSED):
        export_case("case-9999", ExportFormat.DOCX)
    assert spy.calls == []


def test_gate_1_alone_does_not_unlock_export(tmp_path, monkeypatch, dossier, spy):
    record(tmp_path, monkeypatch, dossier, gate2=False)
    with pytest.raises(REFUSED):
        export_case(CASE, ExportFormat.DOCX)


def test_export_after_gate_2_returns_existing_paths(tmp_path, monkeypatch, dossier, spy):
    """After Gate 2: the application DOCX, the List of Dates, the objections sheet and the hearing card are written (docstring of export_case)."""
    record(tmp_path, monkeypatch, dossier, gate2=True)
    paths = export_case(CASE, ExportFormat.DOCX)
    assert isinstance(paths, list) and len(paths) >= 4
    assert all(Path(p).exists() for p in paths)
    names = " ".join(Path(p).name.lower() for p in paths)
    for word in ("application", "dates", "objection", "card"):
        assert word in names, names
    assert "application" in spy.calls and "card" in spy.calls


def test_docx_export_does_not_convert_to_pdf(tmp_path, monkeypatch, dossier, spy):
    record(tmp_path, monkeypatch, dossier, gate2=True)
    export_case(CASE, ExportFormat.DOCX)
    assert "pdf" not in spy.calls


def test_pdf_export_converts_through_libreoffice(tmp_path, monkeypatch, dossier, spy):
    """ExportFormat.PDF additionally converts the DOCX (plan §13.1: LibreOffice headless)."""
    record(tmp_path, monkeypatch, dossier, gate2=True)
    paths = export_case(CASE, ExportFormat.PDF)
    assert "pdf" in spy.calls
    assert any(p.endswith(".pdf") for p in paths)


def test_every_export_is_for_one_case_only(tmp_path, monkeypatch, dossier, spy):
    """No bulk export: Gate 2 of case-0007 does not let case-0008 export, and every returned path belongs to the requested case."""
    log = record(tmp_path, monkeypatch, dossier, gate2=True)
    h.seed_dossier(log, "case-0008", h.resolved_dossier(dossier).model_copy(update={"case_id": "case-0008"}))
    with pytest.raises(REFUSED):
        export_case("case-0008", ExportFormat.DOCX)
    assert all("0008" not in p for p in export_case(CASE, ExportFormat.DOCX))


def test_docx_to_pdf_calls_headless_libreoffice(tmp_path, monkeypatch):
    """`docx_to_pdf` shells out to `soffice --headless --convert-to pdf` and returns the PDF path next to the DOCX.

    ASSUMPTION: the binary is `soffice` or `libreoffice` and the conversion uses subprocess.run."""
    from vakeel_sahayak.export.pdf import docx_to_pdf

    docx = tmp_path / "application.docx"
    docx.write_bytes(b"docx")
    seen: list[list[str]] = []

    def fake_run(cmd, *a, **k):
        seen.append(list(cmd))
        (tmp_path / "application.pdf").write_bytes(b"%PDF-1.4")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = docx_to_pdf(str(docx))
    assert out == str(tmp_path / "application.pdf")
    cmd = " ".join(seen[0])
    assert "--headless" in cmd and "--convert-to" in cmd and "pdf" in cmd


def test_docx_to_pdf_fails_loudly_when_libreoffice_fails(tmp_path, monkeypatch):
    from vakeel_sahayak.export.pdf import docx_to_pdf

    docx = tmp_path / "a.docx"
    docx.write_bytes(b"docx")
    monkeypatch.setattr(subprocess, "run", lambda cmd, *a, **k: subprocess.CompletedProcess(cmd, 1, b"", b"boom"))
    with pytest.raises((RuntimeError, OSError, subprocess.CalledProcessError)):
        docx_to_pdf(str(docx))
