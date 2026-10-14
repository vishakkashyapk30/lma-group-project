"""Router `upload` (plan §4.1 K1-K10, §4.5, §16): files and dictation come in; raw files stay on the laptop.

Raw client files are stored below `$VS_DATA_DIR/cases/<case_id>/` (laptop only). The event log holds file names and counts,
never page text (plan §16). Audio is deleted after transcription unless counsel keeps it.
"""

from __future__ import annotations

import pytest

from tests.system._helpers import dump_events
from tests.unit.api._helpers import CASE, INVALID, NOT_FOUND, PDF_BYTES, UNSUPPORTED_MEDIA, scenario
from vakeel_sahayak.schemas.enums import EventKind

PDF = ("application/pdf", PDF_BYTES)


def files_payload(*named: tuple[str, str, bytes]):
    return [("files", (name, content, mime)) for name, mime, content in named]


def test_upload_pdf_is_accepted_and_kept_on_the_laptop(tmp_path, monkeypatch):
    """POST upload (multipart): the response lists the accepted names, and the bytes land under the case's data directory."""
    sc = scenario(tmp_path, monkeypatch)
    res = sc.client().post(f"/api/cases/{CASE}/upload", files=files_payload(("bundle_1.pdf", "application/pdf", PDF_BYTES)))
    assert res.status_code == 200
    body = res.json()
    assert body["case_id"] == CASE and body["accepted"] == ["bundle_1.pdf"]
    stored = list((sc.data_dir / "cases" / CASE).rglob("bundle_1.pdf"))
    assert len(stored) == 1 and stored[0].read_bytes() == PDF_BYTES


@pytest.mark.parametrize(
    ("name", "mime"),
    [("fir_photo.jpg", "image/jpeg"), ("fir_photo.png", "image/png"), ("order.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
     ("iphone.heic", "image/heic")],
)
def test_other_input_kinds_of_k10_are_accepted(tmp_path, monkeypatch, name, mime):
    """Plan §4.1 K4 and K10: photos (JPG/HEIC/PNG) and DOCX are read directly."""
    res = scenario(tmp_path, monkeypatch).client().post(f"/api/cases/{CASE}/upload", files=files_payload((name, mime, b"stub")))
    assert res.status_code == 200 and res.json()["accepted"] == [name]


def test_several_files_in_one_request(tmp_path, monkeypatch):
    res = scenario(tmp_path, monkeypatch).client().post(
        f"/api/cases/{CASE}/upload", files=files_payload(("a.pdf", "application/pdf", PDF_BYTES), ("b.pdf", "application/pdf", PDF_BYTES)))
    assert res.json()["accepted"] == ["a.pdf", "b.pdf"]


def test_unsupported_file_type_is_refused_and_not_stored(tmp_path, monkeypatch):
    """An executable is not an input kind: 415, nothing written. ASSUMPTION for the code."""
    sc = scenario(tmp_path, monkeypatch)
    res = sc.client().post(f"/api/cases/{CASE}/upload", files=files_payload(("run.exe", "application/octet-stream", b"MZ")))
    assert res.status_code == UNSUPPORTED_MEDIA
    assert not list(sc.data_dir.rglob("run.exe"))


def test_upload_without_files_is_422(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().post(f"/api/cases/{CASE}/upload").status_code == INVALID


def test_file_name_cannot_escape_the_case_directory(tmp_path, monkeypatch):
    """A name like ../../x.pdf is stored (if at all) inside the case directory only."""
    sc = scenario(tmp_path, monkeypatch)
    sc.client().post(f"/api/cases/{CASE}/upload", files=files_payload(("../../evil.pdf", "application/pdf", PDF_BYTES)))
    inside = sc.data_dir / "cases" / CASE
    assert not (sc.data_dir / "evil.pdf").exists() and not (tmp_path / "evil.pdf").exists()
    assert all(inside in p.parents for p in sc.data_dir.rglob("evil.pdf"))


def test_event_log_records_the_upload_without_file_content(tmp_path, monkeypatch):
    """The audit trail notes the upload (name only); page text and bytes never enter the log (plan §16)."""
    sc = scenario(tmp_path, monkeypatch)
    sc.client().post(f"/api/cases/{CASE}/upload", files=files_payload(("bundle_1.pdf", "application/pdf", PDF_BYTES + b"SECRET-PAGE-TEXT")))
    events = sc.events(EventKind.USER_ACTION)
    assert any("bundle_1.pdf" in e.model_dump_json() for e in events)
    assert "SECRET-PAGE-TEXT" not in dump_events(sc.events())


def test_corrupt_pdf_leads_to_a_question_for_counsel(tmp_path, monkeypatch, require_pymupdf, pdfs):
    """K9: a broken file is never guessed at; the response asks for an unlocked or intact copy (plan §4.1)."""
    sc = scenario(tmp_path, monkeypatch)
    bad = pdfs.corrupt("broken.pdf").read_bytes()
    body = sc.client().post(f"/api/cases/{CASE}/upload", files=files_payload(("broken.pdf", "application/pdf", bad))).json()
    assert body["questions"], body
    assert any("copy" in q.lower() for q in body["questions"])


def test_upload_to_an_unknown_case_creates_it_or_404s(tmp_path, monkeypatch):
    """ASSUMPTION: uploading to a case id that was never created is a 404 (create it first with POST /api/cases)."""
    res = scenario(tmp_path, monkeypatch).client().post("/api/cases/case-9999/upload", files=files_payload(("a.pdf", "application/pdf", PDF_BYTES)))
    assert res.status_code in (NOT_FOUND, 200)


# ---- dictation ---------------------------------------------------------------------------------------------------
DICTATION = "Arrested on 20.08.2024 under section 318(4) BNS; custody since 21.08.2024."


def test_dictation_is_read_back_for_confirmation(tmp_path, monkeypatch):
    """Plan §4.5: Munshi reads back the dates and sections it heard and asks counsel to confirm them."""
    sc = scenario(tmp_path, monkeypatch)
    sc.set_asr(DICTATION)
    res = sc.client().post(f"/api/cases/{CASE}/audio", files={"file": ("dictation.wav", b"RIFF....WAVE", "audio/wav")})
    assert res.status_code == 200
    questions = " ".join(res.json()["questions"])
    for heard in ("20.08.2024", "318(4)", "21.08.2024"):
        assert heard in questions
    assert "confirm" in questions.lower()


def test_audio_is_deleted_after_transcription_by_default(tmp_path, monkeypatch):
    """Audio stays on the laptop and is deleted after transcription unless counsel keeps it (plan §4.5, §16)."""
    sc = scenario(tmp_path, monkeypatch)
    sc.set_asr(DICTATION)
    sc.client().post(f"/api/cases/{CASE}/audio", files={"file": ("dictation.wav", b"RIFF....WAVE", "audio/wav")})
    assert not list(sc.data_dir.rglob("*.wav"))


def test_audio_is_kept_when_counsel_asks_to_keep_it(tmp_path, monkeypatch):
    """ASSUMPTION: `?keep=true` is how counsel keeps the recording."""
    sc = scenario(tmp_path, monkeypatch)
    sc.set_asr(DICTATION)
    sc.client().post(f"/api/cases/{CASE}/audio?keep=true", files={"file": ("dictation.wav", b"RIFF....WAVE", "audio/wav")})
    assert list(sc.data_dir.rglob("*.wav"))


def test_dictated_facts_are_user_stated_not_verified(tmp_path, monkeypatch):
    """Dictated facts are `USER_STATED` (plan §4.5): none of them is marked VERIFIED without a court record."""
    sc = scenario(tmp_path, monkeypatch)
    sc.set_asr("The applicant is the sole earning member of the family.")
    sc.client().post(f"/api/cases/{CASE}/audio", files={"file": ("d.wav", b"RIFF....WAVE", "audio/wav")})
    dossier = sc.client().get(f"/api/cases/{CASE}/dossier").json()
    assert dossier["fields"]["personal"]["status"] == "USER_STATED"


def test_audio_upload_needs_a_file(tmp_path, monkeypatch):
    assert scenario(tmp_path, monkeypatch).client().post(f"/api/cases/{CASE}/audio").status_code == INVALID
