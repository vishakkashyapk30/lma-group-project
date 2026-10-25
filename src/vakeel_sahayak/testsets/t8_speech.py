"""T8 speech: Kathbath Hindi test subset plus T1 facts dictated in Hindi and English by Indic Parler-TTS; about 300 utterances (plan §15.2).

Two sources. (1) Kathbath: 150 Hindi utterances drawn with a seed from the Kathbath test_known subset (`kathbath_dir`: either `test.jsonl` with rows {audio,
text}, or the downloaded layout `manifest.jsonl` with rows {audio, transcript} next to an `audio/` folder); the audio files are copied under
`out_dir/audio/kathbath/` and the transcripts are kept unchanged. (2) Dictations built from T1 facts: for 75 cases of the open part of T1 (the sealed blind
slice is not used) a short English and a short Hindi dictation (150 in all) carrying a date, a section and a number, composed from the case's G3 values
where T1 has them (arrest date, sections, FIR number) and from the order date otherwise; the transcript is the text that is spoken, so word error rate and the
date, section and number error rates before and after the read-back step are measurable without any labelling.

Audio for the dictations. The plan's synthesiser, Indic Parler-TTS (`parler_tts`), is not installed on the build machines, and the hosted Sarvam TTS
(Bulbul) may only be called with constructed text inside `public_scope()` and with `SARVAM_API_KEY` set. So by default the builder writes the transcript side
only and marks those rows `audio_status: "pending"` with `audio: null`; `synthesize_pending(out_dir)` (CLI `--synthesize`) fills them through Sarvam Bulbul
under `public_scope` when the key is set. Tests never call it. Dictation text is constructed from public court data (no client file), so it may be sent.

Outputs in `out_dir`: `utterances.jsonl` (utt_id, source kathbath|tts, lang hi|en, audio, audio_status, transcript, case_id, facts), `audio/kathbath/*.m4a`,
`manifest.json` (counts per source and language, audio status, speaker split, what is pending and why).

CLI: `python -m vakeel_sahayak.testsets.t8_speech [--kathbath DIR --t1 DIR --out DIR] [--synthesize]`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.common import (
    TestSetManifest,
    g3_fields,
    load_t1_cases,
    rows_from_file,
    rows_to_file,
    sha256_file,
    write_manifest,
)

SEED = 20260430
N_KATHBATH, N_CASES = 150, 75
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_HI = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
SECTION_PREFIX = ("BNSS ", "BNS ", "IPC ", "CrPC ", "NDPS ")


def _read_kathbath(directory: str) -> list[dict[str, str]]:
    base = Path(directory)
    if not base.is_dir():
        raise FileNotFoundError(f"Kathbath directory not found: {directory}")
    for name, text_key in (("test.jsonl", "text"), ("manifest.jsonl", "transcript")):
        path = base / name
        if path.exists():
            rows = [{"audio": str(r["audio"]), "text": str(r[text_key]).strip()} for r in rows_from_file(path) if r.get("audio") and str(r.get(text_key) or "").strip()]
            if rows:
                return rows
    raise ValueError(f"no usable Kathbath rows in {directory} (expected test.jsonl or manifest.jsonl)")


def _split_section(section: str) -> tuple[str, str]:
    """('318(4)', 'BNS') from '318(4) BNS' or 'BNS 318(4)'."""
    s = section.strip()
    for p in SECTION_PREFIX:
        if s.startswith(p):
            return s[len(p):].strip(), p.strip()
        if s.endswith(" " + p.strip()):
            return s[: -len(p)].strip(), p.strip()
    return s, ""


def _facts(case: dict[str, Any]) -> dict[str, Any]:
    g3 = g3_fields(case)
    sections = g3.get("sections") if isinstance(g3.get("sections"), list) and g3.get("sections") else None
    when = g3.get("arrest_date") if isinstance(g3.get("arrest_date"), str) and len(g3["arrest_date"]) == 10 else case.get("date")
    fir = g3.get("fir") if isinstance(g3.get("fir"), dict) else {}
    number = fir.get("number")
    kind = "arrest" if when == g3.get("arrest_date") else "order"
    return {"date": when, "date_kind": kind, "section": str(sections[0]) if sections else None, "fir_number": number, "custody_days": g3.get("custody_days")}


def _english(f: dict[str, Any], case_id: str, rng: random.Random) -> str | None:
    if not f["date"]:
        return None
    d = date.fromisoformat(f["date"])
    pretty = f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    num, code = _split_section(f["section"] or f"{rng.choice(['318(4)', '103', '303(2)', '64'])} BNS")
    fir_no = f["fir_number"] or f"{rng.randrange(11, 990)}/{d.year}"
    first = f"The accused was arrested on {pretty}." if f["date_kind"] == "arrest" else f"The order in this case is dated {pretty}."
    second = f"The case is registered under Section {num}{' of the ' + code if code else ''}."
    third = f"The FIR number is {fir_no}."
    parts = [first, second, third]
    if isinstance(f["custody_days"], int):
        parts.append(f"The accused has been in custody for {f['custody_days']} days.")
    return " ".join(parts)


def _hindi(f: dict[str, Any], case_id: str, rng: random.Random) -> str | None:
    if not f["date"]:
        return None
    d = date.fromisoformat(f["date"])
    pretty = f"{d.day} {MONTHS_HI[d.month - 1]} {d.year}"
    num, code = _split_section(f["section"] or f"{rng.choice(['318(4)', '103', '303(2)', '64'])} BNS")
    fir_no = f["fir_number"] or f"{rng.randrange(11, 990)}/{d.year}"
    first = f"आरोपी को {pretty} को गिरफ्तार किया गया।" if f["date_kind"] == "arrest" else f"इस मामले में आदेश {pretty} का है।"
    second = f"मामला धारा {num}{' ' + code if code else ''} के अंतर्गत दर्ज है।"
    third = f"एफआईआर संख्या {fir_no} है।"
    parts = [first, second, third]
    if isinstance(f["custody_days"], int):
        parts.append(f"आरोपी {f['custody_days']} दिन से अभिरक्षा में है।")
    return " ".join(parts)


def build_t8(kathbath_dir: str, t1_dir: str, out_dir: str) -> TestSetManifest:
    """Synthesise dictation and package transcripts.

    Audio is synthesised only by `synthesize_pending` (Sarvam Bulbul, public scope, key set); here the dictation rows are written with their transcripts and
    `audio_status: "pending"`.

    Args:
        kathbath_dir: see behaviour
        t1_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.

    Raises:
        FileNotFoundError: the Kathbath directory does not exist.
        ValueError: it holds no usable rows.
    """
    kb_all = _read_kathbath(kathbath_dir)
    rng = random.Random(SEED)
    out = Path(out_dir)
    kb_sorted = sorted(kb_all, key=lambda r: r["audio"])
    rng.shuffle(kb_sorted)
    kb = sorted(kb_sorted[:N_KATHBATH], key=lambda r: r["audio"])
    rows: list[dict[str, Any]] = []
    missing_audio = 0
    for i, r in enumerate(kb):
        src = Path(kathbath_dir) / r["audio"]
        audio, status = None, "missing"
        if src.is_file():
            dst = out / "audio" / "kathbath" / src.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            audio, status = f"audio/kathbath/{src.name}", "present"
        else:
            missing_audio += 1
        rows.append({"utt_id": f"t8-kb-{i:03d}", "source": "kathbath", "lang": "hi", "audio": audio, "audio_status": status, "transcript": r["text"], "case_id": None,
                     "facts": None, "speaker": "female" if src.stem.endswith("-f") else "male" if src.stem.endswith("-m") else None})
    cases = sorted(load_t1_cases(t1_dir), key=lambda c: c["case_id"])
    rng.shuffle(cases)
    n_tts = 0
    for case in cases:
        if n_tts >= N_CASES:
            break
        f = _facts(case)
        en, hi = _english(f, case["case_id"], rng), _hindi(f, case["case_id"], rng)
        if en is None or hi is None:
            continue
        for lang, text in (("en", en), ("hi", hi)):
            rows.append({"utt_id": f"t8-tts-{n_tts:03d}-{lang}", "source": "tts", "lang": lang, "audio": None, "audio_status": "pending", "transcript": text,
                         "case_id": case["case_id"], "facts": {k: v for k, v in f.items() if v is not None}, "speaker": None})
        n_tts += 1
    rows_to_file(out / "utterances.jsonl", rows)
    tts_rows = [r for r in rows if r["source"] == "tts"]
    details = {
        "seed": SEED, "per_source": dict(Counter(r["source"] for r in rows)), "per_lang_source": dict(sorted(Counter(f"{r['source']}:{r['lang']}" for r in rows).items())),
        "kathbath_pool": len(kb_all), "kathbath_speakers": dict(Counter(str(r["speaker"]) for r in rows if r["source"] == "kathbath")),
        "kathbath_audio_missing": missing_audio, "dictation_cases": n_tts, "dictations_with_custody_days": sum("custody_days" in (r["facts"] or {}) for r in tts_rows),
        "dictations_with_arrest_date": sum((r["facts"] or {}).get("date_kind") == "arrest" for r in tts_rows if r["lang"] == "en"),
        "dictation_facts_from_g3": {"section": sum("section" in (r["facts"] or {}) for r in tts_rows if r["lang"] == "en"), "fir_number": sum("fir_number" in (r["facts"] or {}) for r in tts_rows if r["lang"] == "en")},
        "audio_status": dict(Counter(r["audio_status"] for r in rows)), "source_cases_sha256": sha256_file(Path(t1_dir) / "cases.jsonl"), "blind_slice_used": False,
        "not_built": [f"audio for {len(tts_rows)} synthetic dictations: pending (Indic Parler-TTS not installed; Sarvam Bulbul only under public_scope with SARVAM_API_KEY: run with --synthesize)"] if tts_rows else [],
    }  # fmt: skip
    manifest = TestSetManifest(set_id="T8", size=len(rows), answers_from="transcripts: Kathbath's own, and the text of the dictations composed from T1 facts", used_for=["F8"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def synthesize_pending(out_dir: str, limit: int | None = None) -> dict[str, int]:
    """Fill the `pending` dictation rows with Sarvam Bulbul audio (WAV), only under `public_scope()` and only when `SARVAM_API_KEY` is set.

    The text is constructed from public court data, never a client file. Rows already done are skipped, so the call is resumable. Never used by tests.

    Args:
        out_dir: the T8 directory
        limit: stop after this many utterances

    Returns:
        Counts: done, failed, skipped.

    Raises:
        RuntimeError: no key is set.
    """
    from vakeel_sahayak.models.sarvam.adapters import SarvamTts
    from vakeel_sahayak.models.sarvam.config import key_is_set
    from vakeel_sahayak.models.sarvam.policy import public_scope

    if not key_is_set():
        raise RuntimeError("SARVAM_API_KEY is not set: the dictation audio stays pending")
    out = Path(out_dir)
    rows = rows_from_file(out / "utterances.jsonl")
    counts = {"done": 0, "failed": 0, "skipped": 0}
    with public_scope("T8 synthetic dictation from constructed text"):
        tts = SarvamTts()
        for r in rows:
            if r["source"] != "tts" or r["audio_status"] == "present":
                counts["skipped"] += 1
                continue
            if limit is not None and counts["done"] >= limit:
                break
            try:
                wav = tts.synthesize(r["transcript"], r["lang"])
            except Exception:  # noqa: BLE001  (any Sarvam failure leaves the row pending)
                counts["failed"] += 1
                continue
            path = out / "audio" / "tts" / f"{r['utt_id']}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(wav)
            r["audio"], r["audio_status"] = f"audio/tts/{path.name}", "present"
            counts["done"] += 1
    rows_to_file(out / "utterances.jsonl", rows)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    manifest["details"]["audio_status"] = dict(Counter(r["audio_status"] for r in rows))
    manifest["details"]["synthesised_with"] = "Sarvam Bulbul under public_scope" if counts["done"] else manifest["details"].get("synthesised_with")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    base = Path(paths.testsets_dir)
    ap = argparse.ArgumentParser(description="Build T8 (speech)")
    ap.add_argument("--kathbath", default=str(Path(paths.raw_dir) / "kathbath" / "hindi" / "test_known"))
    ap.add_argument("--t1", default=str(base / "t1"))
    ap.add_argument("--out", default=str(base / "t8"))
    ap.add_argument("--synthesize", action="store_true", help="fill pending dictation audio via Sarvam Bulbul (public scope, needs SARVAM_API_KEY)")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)
    if args.synthesize and os.environ.get("SARVAM_API_KEY"):
        print(json.dumps(synthesize_pending(args.out, args.limit)))
        return 0
    m = build_t8(args.kathbath, args.t1, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("per_lang_source", "audio_status", "not_built")}}, indent=1, ensure_ascii=False))
    if args.synthesize:
        print("SARVAM_API_KEY is not set: synthesis skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
