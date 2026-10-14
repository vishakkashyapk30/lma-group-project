"""Router `desk` (plan §11, §13.5 `/desk`): the batch desk of Pairokar. Upload a zip, see the triage board sorted by urgency,
open a case. Safety: no bulk export; opening a case from the board approves nothing, so each case still needs its own approval.

ASSUMPTIONS: a zip member `<name>.pdf` becomes case id `<name>` (the file stem; as in `tests/system/_helpers.BatchToolbox`);
Pairokar's per-case card is stored on the case record as a STORE_WRITE of view `triage_card` and the board folds the cards of
all cases, ordered by `urgency_rank`.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from tests.system import _helpers as sh
from tests.unit.api._helpers import CASE, EXPORT_REFUSED, NOT_FOUND, PDF_BYTES, UNSUPPORTED_MEDIA, scenario
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.triage import TriageCard


def make_zip(names: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, PDF_BYTES)
    return buf.getvalue()


def put_card(sc, card: TriageCard) -> None:
    sc.log.append(sh.make_event(card.case_id, EventKind.STORE_WRITE, "PAIROKAR", inputs={"store": "case.views", "view": "triage_card"},
                                outputs={"value": card.model_dump(mode="json")}))


def test_zip_upload_returns_one_case_id_per_pdf(tmp_path, monkeypatch):
    """Plan §13.6 flow 6: an office uploads its files; each becomes a case."""
    client = scenario(tmp_path, monkeypatch).client()
    res = client.post("/api/desk/upload", files={"file": ("files.zip", make_zip([f"case-{i:04d}.pdf" for i in range(1, 6)]), "application/zip")})
    assert res.status_code == 200
    assert res.json() == [f"case-{i:04d}" for i in range(1, 6)]


def test_single_pdf_is_one_case(tmp_path, monkeypatch):
    res = scenario(tmp_path, monkeypatch).client().post("/api/desk/upload", files={"file": ("case-0042.pdf", PDF_BYTES, "application/pdf")})
    assert res.status_code == 200 and res.json() == ["case-0042"]


def test_other_file_types_are_refused(tmp_path, monkeypatch):
    res = scenario(tmp_path, monkeypatch).client().post("/api/desk/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == UNSUPPORTED_MEDIA


def test_raw_files_stay_on_the_laptop(tmp_path, monkeypatch):
    """Uploaded files are stored below the data directory only (plan §16)."""
    sc = scenario(tmp_path, monkeypatch)
    sc.client().post("/api/desk/upload", files={"file": ("files.zip", make_zip(["case-0001.pdf"]), "application/zip")})
    stored = [p for p in tmp_path.rglob("case-0001*.pdf")]
    assert stored and all(sc.data_dir in p.parents for p in stored)


def test_board_is_sorted_by_urgency_rank(tmp_path, monkeypatch):
    """GET board: cards ascending by urgency_rank (1 is the most urgent), plan §11 'cause-list board sorted by urgency'."""
    sc = scenario(tmp_path, monkeypatch)
    for cid, rank in (("case-0003", 3), ("case-0001", 1), ("case-0002", 2)):
        put_card(sc, TriageCard(case_id=cid, urgency_rank=rank, reasons=[f"reason {rank}"], next_step="full brief queued"))
    cards = sc.client().get("/api/desk/board").json()["cards"]
    assert [c["case_id"] for c in cards] == ["case-0001", "case-0002", "case-0003"]
    assert [c["urgency_rank"] for c in cards] == [1, 2, 3]


def test_board_card_carries_reasons_flags_missing_documents_and_next_step(tmp_path, monkeypatch):
    """The TriageCard example of plan §11 survives the round trip."""
    sc = scenario(tmp_path, monkeypatch)
    put_card(sc, TriageCard(case_id="case-0142", urgency_rank=4, reasons=["Default-bail window opens in 3 days (BNSS s.187(3))"],
                            flags=["CHECK: antecedents unknown"], missing_docs=["custody certificate"],
                            next_step="full brief queued; flag default-bail window to counsel"))
    (card,) = sc.client().get("/api/desk/board").json()["cards"]
    assert card["reasons"] == ["Default-bail window opens in 3 days (BNSS s.187(3))"]
    assert card["flags"] == ["CHECK: antecedents unknown"] and card["missing_docs"] == ["custody certificate"]
    assert card["next_step"].startswith("full brief queued")


def test_empty_board_is_an_empty_list(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().get("/api/desk/board").json() == {"cards": []}


def test_opening_a_case_returns_its_summary_and_approves_nothing(tmp_path, monkeypatch):
    """Plan §11: each case still needs its own approval: opening it from the board writes no GATE_APPROVED event."""
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(CASE, approve_gate1=False)
    res = sc.client().post(f"/api/desk/{CASE}/open")
    assert res.status_code == 200 and res.json()["case_id"] == CASE
    assert sc.events(EventKind.GATE_APPROVED) == []


def test_opening_unknown_case_is_404(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().post("/api/desk/case-9999/open").status_code == NOT_FOUND


def test_opened_case_cannot_be_exported_without_its_own_approval(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(CASE, brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    client = sc.client()
    client.post(f"/api/desk/{CASE}/open")
    assert client.post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).status_code == EXPORT_REFUSED


@pytest.mark.parametrize("path", ["/api/desk/export", "/api/desk/export-all", "/api/desk/board/export"])
def test_there_is_no_bulk_export_route(tmp_path, monkeypatch, path):
    """Safety (plan §11, §16): batch mode never exports in bulk; no desk route does."""
    client = scenario(tmp_path, monkeypatch).client()
    assert client.post(path).status_code in (404, 405)
    assert not [r.path for r in client.app.routes if hasattr(r, "path") and r.path.startswith("/api/desk") and "export" in r.path]
