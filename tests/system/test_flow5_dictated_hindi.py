"""User flow 5 (plan §13.6, §4.5): a dictated case. Counsel dictates the story in Hindi, Munshi reads back the dates and sections for
confirmation, the facts are USER_STATED, and the brief labels them "per counsel, not on record".

Real modules: the upload/audio route, Munshi's voice handling (read-back, deletion of audio), the dossier statuses, Vakeel's drafting, the
exporter. Fakes: ASR (`Scenario.set_asr`: the transcript does not depend on where the API stored the audio), the translator, models,
stores. No audio model runs.

ASSUMPTIONS: the audio route answers `questions` that read back every date, section and number heard and ask counsel to confirm; audio is
deleted after transcription unless `?keep=true`; a ground that rests on a USER_STATED field ends with 'per counsel, not on record' even
when the drafter did not write it; the dictated fact of the worked example is `personal` = ['sole earning member'] from chat turn 3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes.data import PLANTED_NAMES_HI
from tests.fakes.toolbox import leaked_names
from tests.system import _helpers as sh
from tests.unit.export._helpers import docx_text
from vakeel_sahayak.schemas.enums import EventKind, Factor, FieldStatus

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G2 = sh.G2
HI_DICTATION = "मुझे 20.08.2024 को धारा 318(4) बी.एन.एस. में गिरफ्तार किया गया। मैं परिवार में अकेला कमाने वाला हूँ।"
HI_FIR_DICTATION = "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024\nधारा 318(4) बी.एन.एस.\nघटना दिनांक 10.08.2024"
SOLE_EARNER = "The applicant is the sole earning member of his family [F:personal]."
PHRASE = "per counsel, not on record"
WAV = ("dictation.wav", b"RIFF....WAVE", "audio/wav")


def dictate(sc: sh.Scenario, transcript: str, query: str = ""):
    sc.set_asr(transcript)
    return sc.client().post(f"/api/cases/{CASE}/audio{query}", files={"file": WAV})


def dictated_and_drafted(tmp_path, monkeypatch) -> sh.Scenario:
    extra = sh.ground("G4", Factor.HEALTH_AGE_FAMILY, SOLE_EARNER)
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages(), ada=sh.ada_client(grounds=("G1",), extra_grounds=[extra]))
    sc.through_gate1()
    sc.through_draft()
    return sc


# ---- steps 1-2: dictation and read-back --------------------------------------------------------------------------------
def test_hindi_dictation_is_read_back_for_confirmation(tmp_path, monkeypatch):
    """Munshi reads back the date and the section it heard and asks counsel to confirm."""
    sc = sh.Scenario(tmp_path, monkeypatch)
    res = dictate(sc, HI_DICTATION)
    assert res.status_code == 200
    asked = " ".join(res.json()["questions"])
    assert "20.08.2024" in asked and "318(4)" in asked and "confirm" in asked.lower()


def test_every_date_section_and_number_heard_is_read_back(tmp_path, monkeypatch):
    """The three lines of an FIR dictated: both dates, the section and the FIR number are all in the read-back."""
    sc = sh.Scenario(tmp_path, monkeypatch)
    asked = " ".join(dictate(sc, HI_FIR_DICTATION).json()["questions"])
    for heard in ("14.08.2024", "10.08.2024", "318(4)", "112/2024"):
        assert heard in asked, heard


def test_audio_is_deleted_after_transcription_unless_counsel_keeps_it(tmp_path, monkeypatch):
    """Plan §4.5, §16: audio stays on the laptop and is deleted after transcription unless counsel keeps it."""
    sc = sh.Scenario(tmp_path / "default", monkeypatch)
    dictate(sc, HI_DICTATION)
    assert not list(sc.data_dir.rglob("*.wav"))
    keep = sh.Scenario(tmp_path / "keep", monkeypatch)
    dictate(keep, HI_DICTATION, "?keep=true")
    assert list(keep.data_dir.rglob("*.wav"))


def test_dictation_reaches_no_ada_client(tmp_path, monkeypatch):
    """Audio and the transcript are handled on the laptop; nothing is sent to Ada at this stage."""
    sc = sh.Scenario(tmp_path, monkeypatch)
    dictate(sc, HI_DICTATION)
    assert sc.ada_prompts == []


# ---- step 3: USER_STATED -----------------------------------------------------------------------------------------------
def test_dictated_facts_are_user_stated_with_a_chat_source(tmp_path, monkeypatch):
    sc = dictated_and_drafted(tmp_path, monkeypatch)
    personal = sc.state.dossier.fields.personal
    assert (personal.status, personal.source.chat) == (FieldStatus.USER_STATED, "turn 3")


def test_no_field_is_verified_without_a_court_document(tmp_path, monkeypatch):
    """A fact is VERIFIED only with a document and page; a dictated one is USER_STATED with a chat turn."""
    sc = dictated_and_drafted(tmp_path, monkeypatch)
    fields = sc.client().get(f"/api/cases/{CASE}/dossier").json()["fields"]
    for name, tracked in fields.items():
        if tracked["status"] == "VERIFIED":
            assert tracked["source"] and tracked["source"].get("doc"), name
        if tracked["status"] == "USER_STATED":
            assert tracked["source"] and tracked["source"].get("chat"), name


def test_the_brief_says_per_counsel_not_on_record(tmp_path, monkeypatch):
    """The ground that rests on the dictated fact is labelled, even though the draft did not write the phrase."""
    sc = dictated_and_drafted(tmp_path, monkeypatch)
    g4 = next(g for g in sc.state.brief.grounds if g.id == "G4")
    assert PHRASE not in SOLE_EARNER and PHRASE in g4.argument.lower()
    assert all(PHRASE not in g.argument.lower() for g in sc.state.brief.grounds if g.id != "G4")  # court-record grounds are not labelled


def test_the_exported_application_keeps_the_label(tmp_path, monkeypatch):
    """Needs python-docx: the DOCX that counsel files carries 'per counsel, not on record' next to the dictated fact."""
    pytest.importorskip("docx")
    sc = dictated_and_drafted(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = [Path(p) for p in sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()]
    assert PHRASE in docx_text(next(p for p in paths if "application" in p.name.lower())).lower()


# ---- privacy of what was dictated --------------------------------------------------------------------------------------
def test_a_name_in_the_dictation_never_reaches_ada_or_the_log(tmp_path, monkeypatch):
    """Plan §16: a Hindi name dictated by counsel is pseudonymised before anything is logged or sent to Ada."""
    transcript = f"आरोपी {PLANTED_NAMES_HI[0]} को 20.08.2024 को गिरफ्तार किया गया।"
    sc = sh.Scenario(tmp_path, monkeypatch, pages=sh.messy_bundle_pages())
    dictate(sc, transcript)
    sc.through_gate1()
    sc.through_draft()
    texts = [sh.dump_events(sc.events()), *sc.ada_prompts, sh.stores_text(sc.world, shared=False)]
    assert leaked_names(texts, list(PLANTED_NAMES_HI)) == []


def test_dictation_is_a_user_action_in_the_log_without_the_audio(tmp_path, monkeypatch):
    sc = sh.Scenario(tmp_path, monkeypatch)
    dictate(sc, HI_DICTATION)
    assert any(e.kind == EventKind.USER_ACTION for e in sc.events())
    assert "RIFF" not in sh.dump_events(sc.events())
    assert sh.agent_approvals(sc.events()) == []
