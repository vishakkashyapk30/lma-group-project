"""Feature evaluation F8: Hindi and voice intake vs English-only pipeline, Whisper vs IndicConformer, no read-back. Test set: T2 (K5, K6); T8. Metrics: Hindi CER; field-accuracy gap Hindi vs English; WER; date/section/number error rate before and after read-back (plan §15.6).

Arms (one directory each, one JSON file per bundle or utterance; `score` reads one arm):

- `hindi_pipeline` (T2 K1, K5, K6 bundles): Munshi's full path with the scripted counsel; Hindi CER of the page texts against the known text, and the share of dossier fields read right (offline rule extractor, the stand-in of the fine-tuned 4B).
- `english_only` (same bundles): OCR on every page asked for English only, no text-layer shortcut and no Hindi handling. Tesseract has no Hindi data on this machine (`tesseract --list-langs`: eng, kan, nep, osd, snum), so both arms read Hindi scans with English data; the
  arms differ where the text layer is used (K5). Hindi scans (K6) therefore score a high CER in both: that is the missing data, not the pipeline.
- `whisper_small` (T8 Kathbath, Hindi): `openai/whisper-small` from `models/hf` through transformers on CPU, audio decoded with ffmpeg; WER against the Kathbath transcript, words split on spaces. `indicconformer`: unavailable (no NeMo or checkpoint), recorded as such.
- `readback` and `no_readback` (T8 dictations, 150 utterances): the date, the section and the FIR number of each dictation. The audio of the dictations is pending (docs/handoff/testsets-t2-t9.md), so ASR errors are SIMULATED: with probability 0.3 per entity one digit of
  the spoken value is changed (seeded by the utterance id). `entity_errors_before` counts entities that `ingestion.voice.readback` does not report with the true value (wrong or not heard); with read-back counsel confirms or corrects every item the read-back shows, so
  `entity_errors_after` counts the entities it never showed; `no_readback` leaves after equal to before. This measures what the read-back can surface (its extraction coverage), under assumed noise: not a measured ASR error rate.

Metrics from `score`: `hindi_cer` (macro mean over Hindi files, with `hindi_cer/<kind>`), `field_accuracy_gap` (English minus Hindi mean field accuracy), `wer` (mean per-utterance), `entity_error_rate_before_readback`, `entity_error_rate_after_readback`.
`VS_FEATURE_N` is the number of items per kind (bundles) or in all (utterances); defaults are small because Munshi takes about 25 s a bundle and Whisper about 8 s an utterance on CPU.
"""

from __future__ import annotations

import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval import feature_common as fc
from vakeel_sahayak.eval.ingestion import common as ic

ARMS = ("hindi_pipeline", "english_only", "whisper_small", "indicconformer", "readback", "no_readback")
DEFAULT_N = 4
NOISE = 0.3
WHISPER_DIR = "models/hf/openai--whisper-small"


# ---------------------------------------------------------------------------------------------- T2 bundles
def _bundle_payload(truth: dict[str, Any], result: ic.BundleResult, arm: str) -> dict[str, Any]:
    texts = (result.page_texts + [""] * len(truth["pages"]))[: len(truth["pages"])]
    scores = ic.field_scores(ic.read_fields(ic.passages_from(result.report, texts, result.counsel_answers)), truth.get("fields") or {})
    return {"arm": arm, "kind": truth["kind"], "lang": truth["lang"], "hyp": "\n".join(texts), "ref": "\n".join(p["text"] for p in truth["pages"]),
            "field_accuracy": fc.mean(float(v) for v in scores.values()), "fields_n": len(scores), "notes": result.notes}


def run_bundles(out_dir: str, arm: str, n: int, shard: int, n_shards: int) -> None:
    """Hindi-pipeline and English-only arms over the first `n` bundles of K1, K5 and K6."""
    from vakeel_sahayak.eval.ingestion import munshi_full, p2_ocr_every_page, rq2
    from vakeel_sahayak.testsets.t2_messy_bundles import scripted_counsel

    truth_path = fc.testsets_dir() / "t2" / "truth.jsonl"
    rows = rq2.load_truth(str(truth_path), {"K1", "K5", "K6"}, n)
    ok, note = (munshi_full if arm == "hindi_pipeline" else p2_ocr_every_page).availability()
    if not ok:
        fc.mark_unavailable(out_dir, arm, note)
        return
    for truth in fc.shard_slice(rows, shard, n_shards):
        if fc.case_file(out_dir, arm, truth["bundle_id"]).exists():
            continue
        pdf = str(truth_path.parent / truth["pdf"])
        with rq2.ocr_for_run("munshi"):
            if arm == "hindi_pipeline":
                result = munshi_full.run_bundle(pdf, None, counsel=scripted_counsel(truth.get("fields") or {}))
            else:
                result = p2_ocr_every_page.run_bundle(pdf, None, lang="eng")
        fc.save_case(out_dir, arm, truth["bundle_id"], _bundle_payload(truth, result, arm))


# ---------------------------------------------------------------------------------------------- T8 speech
def word_error_rate(hyp: str, ref: str) -> float:
    """Word-level edit distance over reference words."""
    h, r = hyp.split(), ref.split()
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(r) + 1))
    for i, hw in enumerate(h, 1):
        cur = [i]
        for j, rw in enumerate(r, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (hw != rw)))
        prev = cur
    return prev[-1] / len(r)


def _whisper():
    """A transformers Whisper pipeline over the local checkpoint, or raises ModelUnavailable."""
    from vakeel_sahayak.models.base import ModelUnavailable

    if not Path(WHISPER_DIR).joinpath("config.json").is_file():
        raise ModelUnavailable(f"{WHISPER_DIR} is missing (scripts/download_models.sh)", "speech")
    from transformers import pipeline

    return pipeline("automatic-speech-recognition", model=WHISPER_DIR, device=-1)


def transcribe_file(pipe: Any, path: str) -> str:
    """Hindi transcript of an audio file (ffmpeg decodes to 16 kHz mono)."""
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    out = pipe({"raw": np.frombuffer(raw, dtype=np.float32), "sampling_rate": 16000}, generate_kwargs={"language": "hindi", "task": "transcribe"})
    return str(out["text"]).strip()


def run_asr(out_dir: str, arm: str, n: int, shard: int, n_shards: int) -> None:
    """WER of an ASR arm over the first `n` Kathbath utterances of T8."""
    from vakeel_sahayak.models.base import ModelUnavailable

    if arm == "indicconformer":
        fc.mark_unavailable(out_dir, arm, "IndicConformer (NeMo) and its checkpoint are not installed; nothing hosted was called")
        return
    root = fc.testsets_dir() / "t8"
    rows = [r for r in fc.read_jsonl(root / "utterances.jsonl") if r["source"] == "kathbath" and r.get("audio_status") == "present"][:n]
    try:
        pipe = _whisper()
    except (ModelUnavailable, ImportError) as exc:
        fc.mark_unavailable(out_dir, arm, str(exc))
        return
    for row in fc.shard_slice(rows, shard, n_shards):
        if fc.case_file(out_dir, arm, row["utt_id"]).exists():
            continue
        hyp = transcribe_file(pipe, str(root / row["audio"]))
        fc.save_case(out_dir, arm, row["utt_id"], {"arm": arm, "lang": "hi", "words_hyp": hyp, "words_ref": row["transcript"]})


# ---------------------------------------------------------------------------------------------- read-back
_FIR = re.compile(r"\b(\d{1,6})/((?:19|20)\d{2})\b")


def _noisy(value: str, rng: random.Random) -> str:
    """One digit of the spoken value changed (a simulated recognition error)."""
    digits = [i for i, c in enumerate(value) if c.isdigit()]
    if not digits:
        return value
    i = rng.choice(digits)
    new = rng.choice([d for d in "0123456789" if d != value[i]])
    return value[:i] + new + value[i + 1:]


def dictation_entities(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(kind, spoken string, true normalised value) for the date, section and FIR number of a T8 dictation."""
    from vakeel_sahayak.pipelines.order_facts import DATE_RE

    text, facts = row["transcript"], row.get("facts") or {}
    ents: list[tuple[str, str, str]] = []
    m = DATE_RE.search(text)
    if m and facts.get("date"):
        ents.append(("date", m.group(0), str(facts["date"])))
    sec = str(facts.get("section") or "")
    num = re.search(r"\d+(?:\([^)]*\))*", sec)
    if num and num.group(0) in text:
        ents.append(("section", num.group(0), sec))
    f = _FIR.search(text)
    if f:
        ents.append(("fir_number", f.group(0), f.group(0)))
    return ents


def readback_case(row: dict[str, Any], noise: float = NOISE) -> dict[str, Any]:
    """Errors before and after read-back for one dictation (see the module docstring)."""
    from vakeel_sahayak.ingestion.voice import readback

    rng = random.Random(f"f8|{row['utt_id']}")
    text = row["transcript"]
    ents = dictation_entities(row)
    for _kind, spoken, _true in ents:
        if rng.random() < noise:
            text = text.replace(spoken, _noisy(spoken, rng), 1)
    shown = readback(text)
    before = after = 0
    for kind, _spoken, true in ents:
        if kind == "date":
            surfaced = [s for s in shown if s.startswith("date:")]
            ok = any(true in s for s in surfaced)
        elif kind == "section":
            surfaced = [s for s in shown if s.startswith("section:")]
            ok = any(true.replace(" ", "").lower() in s.replace(" ", "").lower() for s in surfaced)
        else:
            surfaced = [s for s in shown if s.startswith("FIR number:")]
            ok = any(true in s for s in surfaced)
        before += not ok
        after += not surfaced  # counsel corrects what the read-back shows; an entity never shown stays wrong
    return {"lang": row["lang"], "entity_errors_before": before, "entity_errors_after": after, "entities_total": len(ents)}


def run_readback(out_dir: str, arm: str, n: int, shard: int, n_shards: int) -> None:
    """Read-back and no-read-back arms over the first `n` dictations of T8."""
    rows = [r for r in fc.read_jsonl(fc.testsets_dir() / "t8" / "utterances.jsonl") if r["source"] == "tts"][:n]
    for row in fc.shard_slice(rows, shard, n_shards):
        if fc.case_file(out_dir, arm, row["utt_id"]).exists():
            continue
        res = readback_case(row)
        if arm == "no_readback":
            res["entity_errors_after"] = res["entity_errors_before"]
        fc.save_case(out_dir, arm, row["utt_id"], {"arm": arm, **res, "asr_noise": "simulated, p=" + str(NOISE) + " per entity"})


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F8 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm, one JSON file per bundle or utterance
        shard: this shard's index
        n_shards: the number of shards (items are dealt out by index)
    """
    n = fc.env_limit()
    for arm in fc.selected_arms(ARMS):
        if arm in ("hindi_pipeline", "english_only"):
            run_bundles(out_dir, arm, n or DEFAULT_N, shard, n_shards)
        elif arm in ("whisper_small", "indicconformer"):
            run_asr(out_dir, arm, n or 10, shard, n_shards)
        elif arm in ("readback", "no_readback"):
            run_readback(out_dir, arm, n or 150, shard, n_shards)


def score(run_dir: str) -> dict[str, float]:
    """Compute F8 metrics for one arm directory.

    Args:
        run_dir: an arm's directory; files carry whichever of `hyp`/`ref`, `field_accuracy`, `words_hyp`/`words_ref`, `entity_errors_*` apply

    Returns:
        `hindi_cer` (macro over `lang == "hi"` files with text, plus `hindi_cer/<kind>`), `field_accuracy_gap` (English minus Hindi mean field accuracy, when both exist), `wer` (mean over files
        with word strings), `entity_error_rate_before_readback` and `..._after_readback` (sums over entities). A metric with nothing to measure is left out.

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    hi = [r for r in rows if r.get("lang") == "hi" and "hyp" in r and "ref" in r]
    out: dict[str, float | None] = {"hindi_cer": fc.mean(ic.character_error_rate(r["hyp"], r["ref"]) for r in hi)}
    for kind in sorted({r["kind"] for r in hi if r.get("kind")}):
        out[f"hindi_cer/{kind}"] = fc.mean(ic.character_error_rate(r["hyp"], r["ref"]) for r in hi if r.get("kind") == kind)
    fa = {lang: fc.mean(float(r["field_accuracy"]) for r in rows if r.get("lang") == lang and r.get("field_accuracy") is not None) for lang in ("en", "hi")}
    out["field_accuracy_gap"] = fa["en"] - fa["hi"] if fa["en"] is not None and fa["hi"] is not None else None
    out["wer"] = fc.mean(word_error_rate(r["words_hyp"], r["words_ref"]) for r in rows if "words_hyp" in r and "words_ref" in r)
    ent = [r for r in rows if "entities_total" in r]
    total = sum(r["entities_total"] for r in ent)
    out["entity_error_rate_before_readback"] = fc.rate(sum(r["entity_errors_before"] for r in ent), total)
    out["entity_error_rate_after_readback"] = fc.rate(sum(r["entity_errors_after"] for r in ent), total)
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
