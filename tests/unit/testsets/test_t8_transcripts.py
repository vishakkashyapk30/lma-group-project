"""T8 (new tests): the transcript side, which needs no synthesiser. The audio tests of `test_t8_speech.py` wait for Parler-TTS; here the dictations are
`pending` rows with their transcripts, and Kathbath audio is copied when the files exist."""

from __future__ import annotations

import json
import re

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, write_t1_dir
from tests.unit.testsets.test_t8_speech import write_kathbath
from vakeel_sahayak.testsets import t8_speech
from vakeel_sahayak.testsets.t8_speech import build_t8

DEVANAGARI = re.compile("[ऀ-ॿ]")


@pytest.fixture()
def built(tmp_path):
    t1 = write_t1_dir(tmp_path)
    out = tmp_path / "t8"
    m = build_t8(str(write_kathbath(tmp_path)), str(t1), str(out))
    return m, read_rows(out / "utterances.jsonl"), out


def test_about_three_hundred_utterances_with_the_planned_sources(built):
    m, rows, out = built
    assert_manifest(m, "T8")
    assert 280 <= m.size <= 320 and m.size == len(rows) and read_manifest(out)["size"] == len(rows) and m.used_for == ["F8"]
    assert {r["source"] for r in rows} == {"kathbath", "tts"}
    assert {r["lang"] for r in rows if r["source"] == "tts"} == {"hi", "en"} and {r["lang"] for r in rows if r["source"] == "kathbath"} == {"hi"}


def test_dictations_are_pending_with_transcripts_and_are_never_marked_as_audio(built):
    m, rows, _ = built
    tts = [r for r in rows if r["source"] == "tts"]
    assert tts and all(r["audio"] is None and r["audio_status"] == "pending" and r["transcript"].strip() for r in tts)
    assert any("pending" in x for x in m.details["not_built"])


def test_english_dictations_carry_a_date_a_section_and_a_number(built):
    _, rows, _ = built
    en = [r["transcript"] for r in rows if r["source"] == "tts" and r["lang"] == "en"]
    assert en and all(re.search(r"\b\d{1,2} [A-Z][a-z]+ \d{4}\b", t) and "Section" in t and re.search(r"FIR number is [\d/]+", t) for t in en)
    assert any("318(4)" in t for t in en)


def test_hindi_dictations_are_devanagari_with_the_same_digits(built):
    _, rows, _ = built
    by_case: dict[str, dict[str, str]] = {}
    for r in rows:
        if r["source"] == "tts":
            by_case.setdefault(r["case_id"], {})[r["lang"]] = r["transcript"]
    assert by_case and all(DEVANAGARI.search(v["hi"]) and "318(4)" in v["hi"] for v in by_case.values())
    assert all(re.findall(r"\d+/\d+", v["hi"]) == re.findall(r"\d+/\d+", v["en"]) for v in by_case.values())


def test_kathbath_audio_is_copied_and_the_downloaded_layout_is_read(tmp_path):
    kb = tmp_path / "kb"
    (kb / "audio").mkdir(parents=True)
    rows = []
    for i in range(160):
        name = f"u{i}-{'f' if i % 2 else 'm'}.m4a"
        (kb / "audio" / name).write_bytes(b"x" * 10)
        rows.append({"audio": f"audio/{name}", "transcript": f"वाक्य {i}"})
    (kb / "manifest.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    out = tmp_path / "t8"
    m = build_t8(str(kb), str(write_t1_dir(tmp_path)), str(out))
    got = [r for r in read_rows(out / "utterances.jsonl") if r["source"] == "kathbath"]
    assert len(got) == 150 and all(r["audio_status"] == "present" and (out / r["audio"]).read_bytes() == b"x" * 10 for r in got)
    assert {r["speaker"] for r in got} == {"male", "female"} and m.details["kathbath_audio_missing"] == 0


def test_synthesis_refuses_without_a_key(tmp_path, monkeypatch):
    """The Sarvam path is never taken without SARVAM_API_KEY (and tests never set one)."""
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    build_t8(str(write_kathbath(tmp_path)), str(write_t1_dir(tmp_path)), str(tmp_path / "t8"))
    with pytest.raises(RuntimeError):
        t8_speech.synthesize_pending(str(tmp_path / "t8"))


def test_build_is_deterministic(tmp_path):
    t1, kb = write_t1_dir(tmp_path), write_kathbath(tmp_path)
    build_t8(str(kb), str(t1), str(tmp_path / "a"))
    build_t8(str(kb), str(t1), str(tmp_path / "b"))
    assert (tmp_path / "a" / "utterances.jsonl").read_bytes() == (tmp_path / "b" / "utterances.jsonl").read_bytes()
