"""Voice intake (plan §4.5, §13.6 flow 5): transcription on the laptop, read-back of dates/sections/numbers, audio deletion."""

from __future__ import annotations

from tests.fakes.models import FakeAsr
from tests.unit.ingestion._helpers import patch_attr_everywhere
from vakeel_sahayak.ingestion.voice import delete_audio, readback, transcribe_dictation

DICTATION = "arrested on twentieth August 2024 under section 318(4) BNS, FIR 112 of 2024"
DATE_FORMS = ["2024-08-20", "20.08.2024", "20-08-2024", "20/08/2024", "20 August 2024", "August 20, 2024"]


def lines_with(items: list[str], token: str) -> bool:
    return any(token in line for line in items)


def has_any(items: list[str], tokens: list[str]) -> bool:
    return any(lines_with(items, t) for t in tokens)


def test_readback_extracts_date_section_and_number_from_spoken_date():
    """Spoken 'twentieth August 2024' is read back as a date; section 318(4) and FIR number 112 are read back."""
    # ASSUMPTION: exact string format is free; each expected token must appear in some read-back line.
    items = readback(DICTATION)
    assert isinstance(items, list) and all(isinstance(i, str) and i.strip() for i in items)
    assert has_any(items, DATE_FORMS)
    assert lines_with(items, "318(4)")
    assert lines_with(items, "112")


def test_readback_extracts_digit_dates():
    """A date dictated with digits ('20 August 2024') is read back."""
    items = readback("the first remand was on 21 August 2024 and the charge sheet on 2 November 2024")
    assert has_any(items, ["2024-08-21", "21.08.2024", "21-08-2024", "21/08/2024", "21 August 2024"])
    assert has_any(items, ["2024-11-02", "02.11.2024", "02-11-2024", "02/11/2024", "2 November 2024"])


def test_readback_picks_up_several_sections():
    """Several sections heard are all read back."""
    items = readback("offences under section 318(4) BNS and section 316(2) BNS")
    assert lines_with(items, "318(4)") and lines_with(items, "316(2)")


def test_readback_of_text_without_facts_is_empty():
    """Nothing to confirm when no date, section or number was heard."""
    assert readback("he is a good person and the family depends on him") == []


def test_readback_does_not_invent_values():
    """Values not in the transcript (another date, another section) never appear in the read-back."""
    items = readback(DICTATION)
    assert not lines_with(items, "2024-09-30") and not lines_with(items, "420")


def test_transcribe_uses_the_asr_client_from_the_factory(monkeypatch, tmp_path):
    """Transcription goes through models.factory.get_asr (all model calls do), on the laptop."""
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(b"RIFF....fake")
    asr = FakeAsr({str(audio): DICTATION})
    patch_attr_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_asr", lambda *a, **k: asr)
    assert transcribe_dictation(str(audio)) == DICTATION


def test_transcribe_does_not_delete_the_audio(monkeypatch, tmp_path):
    """ASSUMPTION: deletion is the separate explicit step `delete_audio`; transcribing leaves the file in place."""
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(b"RIFF....fake")
    asr = FakeAsr({str(audio): DICTATION})
    patch_attr_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_asr", lambda *a, **k: asr)
    transcribe_dictation(str(audio))
    assert audio.exists()


def test_delete_audio_removes_the_file(tmp_path):
    """Plan §4.5: audio is deleted after transcription unless counsel keeps it."""
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(b"RIFF....fake")
    delete_audio(str(audio))
    assert not audio.exists()


def test_delete_audio_keep_true_keeps_the_file(tmp_path):
    """keep=True is counsel choosing to keep the recording."""
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(b"RIFF....fake")
    delete_audio(str(audio), keep=True)
    assert audio.exists()


def test_delete_audio_is_idempotent_for_missing_file(tmp_path):
    """ASSUMPTION: deleting a file that is already gone is not an error."""
    delete_audio(str(tmp_path / "gone.wav"))


# ---- read-back of spoken and Hindi FIR numbers and Hindi sections (found by feature run F8) ----------------------------------
def test_readback_shows_spoken_fir_number_and_unbracketed_section():
    items = readback("The order in this case is dated 10 July 2025. The case is registered under Section 269 of the BNS. The FIR number is 664/2025.")
    assert "FIR number: 664/2025" in items and "section: BNS 269" in items


def test_readback_shows_hindi_fir_number_and_hindi_sections():
    items = readback("इस मामले में आदेश 10 जुलाई 2025 का है। मामला धारा 269 BNS के अंतर्गत दर्ज है। एफआईआर संख्या 879/2025 है।")
    assert "FIR number: 879/2025" in items and "section: BNS 269" in items and any(i.startswith("date: 2025-07-10") for i in items)
    assert "section: IPC 420" in readback("धारा 420 आईपीसी के अंतर्गत मामला दर्ज है।")
    assert "section: BNS 318(4)" in readback("बीएनएस की धारा 318(4) लगी है।")


def test_readback_is_unchanged_where_it_already_worked_and_has_no_false_fir():
    assert readback("FIR no. 112/2024 under Section 318(4) BNS") == ["section: BNS 318(4)", "FIR number: 112/2024"]
    assert not [i for i in readback("The FIR was registered on 12/03/2024 at the station.") if i.startswith("FIR number")]
