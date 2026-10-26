"""Router `export` (plan §8.2, §13.1, §16): gated export of the application DOCX/PDF.

Export works only after Gate 2 of this very case, enforced in code (403 until then). The response lists the exported files,
which are written below the case's data directory. The writers are replaced by recording stubs (their content is tested in
tests/unit/export/).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.system import _helpers as sh
from tests.unit.api._helpers import CASE, EXPORT_REFUSED, INVALID, scenario
from tests.unit.export._helpers import Spy
from tests.unit.pipelines._helpers import patch_everywhere
G2 = sh.G2


@pytest.fixture()
def spy(monkeypatch):
    s = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", s.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", s.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", s.pdf)
    return s


def clean_case(tmp_path, monkeypatch, approve_gate2: bool):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    if approve_gate2:
        sc.approve(G2)
    return sc, sc.client()


@pytest.mark.parametrize("fmt", ["DOCX", "PDF"])
def test_export_before_gate_2_is_403_and_writes_nothing(tmp_path, monkeypatch, spy, fmt):
    """The T7 check 'unapproved-export attempts' (plan §15.8): refused with 403, no writer ran, no file exists."""
    sc, client = clean_case(tmp_path, monkeypatch, approve_gate2=False)
    res = client.post(f"/api/cases/{CASE}/export", json={"format": fmt})
    assert res.status_code == EXPORT_REFUSED
    assert spy.calls == []
    assert not [p for p in sc.data_dir.rglob("*") if p.suffix in (".docx", ".pdf")]


def test_export_after_gate_2_lists_the_files(tmp_path, monkeypatch, spy):
    """After Gate 2: 200 and the paths of the application, List of Dates, objections sheet and hearing card (plan §13.6 flow 3)."""
    _, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    res = client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"})
    assert res.status_code == 200
    paths = res.json()
    assert len(paths) >= 4 and all(Path(p).exists() for p in paths)


def test_exported_files_live_under_the_case_directory(tmp_path, monkeypatch, spy):
    sc, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    paths = client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()
    case_dir = (sc.data_dir / "cases" / CASE).resolve()
    assert all(case_dir in Path(p).resolve().parents for p in paths)


def test_export_of_another_case_is_still_403(tmp_path, monkeypatch, spy):
    """No bulk export: Gate 2 of case-0007 does not unlock case-0008."""
    sc, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    sc.seed_record("case-0008", brief=sh.clean_brief("case-0008"), sparring=sh.clean_sparring("case-0008"))
    assert client.post("/api/cases/case-0008/export", json={"format": "DOCX"}).status_code == EXPORT_REFUSED
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).status_code == 200


def test_unknown_format_is_422(tmp_path, monkeypatch, spy):
    _, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "RTF"}).status_code == INVALID


def test_format_defaults_to_docx(tmp_path, monkeypatch, spy):
    """ExportRequest.format defaults to DOCX (api/models.py)."""
    _, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    paths = client.post(f"/api/cases/{CASE}/export", json={}).json()
    assert not any(p.endswith(".pdf") for p in paths)
    assert "pdf" not in spy.calls


def test_exported_files_can_be_downloaded_after_gate_2(tmp_path, monkeypatch, spy):
    """GET .../export/files/{name} serves an exported file of this case (the frontend's download links)."""
    _, client = clean_case(tmp_path, monkeypatch, approve_gate2=True)
    paths = client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()
    name = Path(paths[0]).name
    res = client.get(f"/api/cases/{CASE}/export/files/{name}")
    assert res.status_code == 200 and res.content == Path(paths[0]).read_bytes()


def test_download_is_refused_before_gate_2_and_outside_the_export_folder(tmp_path, monkeypatch, spy):
    sc, client = clean_case(tmp_path, monkeypatch, approve_gate2=False)
    assert client.get(f"/api/cases/{CASE}/export/files/application.docx").status_code == EXPORT_REFUSED
    sc.approve(G2)
    assert client.get(f"/api/cases/{CASE}/export/files/..%2F..%2Frecord.sqlite").status_code == 404
    assert client.get(f"/api/cases/{CASE}/export/files/nothing.docx").status_code == 404
