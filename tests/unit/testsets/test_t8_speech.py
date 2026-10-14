"""T8 speech (plan §15.2, F8): the Kathbath Hindi test subset plus T1 facts dictated in Hindi and English by Indic Parler-TTS; about 300
utterances. Answers are the transcripts, so word error rate and the date, section and number error rates before and after the read-back
step are measurable without labelling.

# SKELETON-GAP: the skeleton has no TTS client in `models/` (Parler-TTS is 'test construction only', models.yaml). The tests that
# synthesise audio need the real synthesiser and are skipped when `parler_tts` is not installed; the tests that do not need audio check
# only the transcript side.
# ASSUMPTION: out_dir/utterances.jsonl rows {"utt_id", "source": "kathbath" | "tts", "lang": "hi" | "en", "audio", "transcript"}; Kathbath
# input is kathbath_dir/test.jsonl rows {"audio", "text"}.
"""

from __future__ import annotations

import json
import re

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, write_t1_dir
from vakeel_sahayak.testsets.t8_speech import build_t8


def write_kathbath(tmp_path, n: int = 160):
    d = tmp_path / "kathbath"
    d.mkdir()
    rows = [{"audio": f"kb_{i}.wav", "text": f"कथबथ वाक्य संख्या {i}"} for i in range(n)]
    (d / "test.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return d


@pytest.fixture()
def built(tmp_path):
    pytest.importorskip("parler_tts")
    t1 = write_t1_dir(tmp_path)
    out = tmp_path / "t8"
    m = build_t8(str(write_kathbath(tmp_path)), str(t1), str(out))
    return m, read_rows(out / "utterances.jsonl"), out


def test_about_three_hundred_utterances(built):
    m, rows, out = built
    assert_manifest(m, "T8")
    assert 280 <= m.size <= 320 and m.size == len(rows) and read_manifest(out)["size"] == len(rows)
    assert m.used_for == ["F8"]


def test_both_sources_and_both_languages_are_present(built):
    _, rows, _ = built
    assert {r["source"] for r in rows} == {"kathbath", "tts"}
    assert {r["lang"] for r in rows if r["source"] == "tts"} == {"hi", "en"}
    assert {r["lang"] for r in rows if r["source"] == "kathbath"} == {"hi"}


def test_every_utterance_has_an_audio_file_and_a_transcript(built):
    _, rows, out = built
    for r in rows:
        assert r["transcript"].strip() and (out / r["audio"]).exists()


def test_synthetic_dictations_carry_dates_sections_and_numbers_for_the_read_back_metric(built):
    """F8 measures errors on dates, sections and numbers: the T1-derived English dictations contain at least one of each kind."""
    _, rows, _ = built
    en = [r["transcript"] for r in rows if r["source"] == "tts" and r["lang"] == "en"]
    assert en and all(re.search(r"\d", t) for t in en)
    assert any(re.search(r"318\(4\)", t) for t in en)


def test_kathbath_transcripts_are_copied_unchanged(built):
    _, rows, _ = built
    kb = {r["transcript"] for r in rows if r["source"] == "kathbath"}
    assert all(t.startswith("कथबथ वाक्य संख्या") for t in kb)


def test_build_is_deterministic(tmp_path):
    pytest.importorskip("parler_tts")
    t1, kb = write_t1_dir(tmp_path), write_kathbath(tmp_path)
    build_t8(str(kb), str(t1), str(tmp_path / "a"))
    build_t8(str(kb), str(t1), str(tmp_path / "b"))
    assert (tmp_path / "a" / "utterances.jsonl").read_bytes() == (tmp_path / "b" / "utterances.jsonl").read_bytes()


def test_a_missing_kathbath_directory_is_an_error(tmp_path):
    """The Kathbath subset is a required input (unlike e-SCR for T2): no silent fallback to synthetic-only audio. # ASSUMPTION."""
    with pytest.raises((FileNotFoundError, ValueError)):
        build_t8(str(tmp_path / "missing"), str(write_t1_dir(tmp_path)), str(tmp_path / "t8"))
