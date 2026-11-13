#!/usr/bin/env python3
"""Translate the interface strings of the frontend into Hindi with a Gemini-API model (Gemma by default), no review by hand.

Reads  frontend/lib/i18n/source.en.json  (made by `npx vite-node --config vitest.config.ts scripts/extract-ui-strings.ts` in frontend/)
Writes frontend/lib/i18n/hi.json         (English text -> Hindi; only strings that are not there yet unless --force)
       frontend/lib/i18n/hi.meta.json    (model, date, counts: where the translations came from)

Privacy: these are public interface labels, not client text, so they may go to the Gemini free tier. The request is sent under
`public_scope`, so the privacy gate still checks it, and the client keeps the key pool, the quota ledger and the retries. The key is
read from the environment only (`set -a; . ./.env; set +a` first; the code never reads .env itself). Nothing here is paid.

    set -a; . ./.env; set +a
    VS_MODELS=auto VS_GEMINI=public .venv/bin/python scripts/translate_ui_hi.py [--model gemma-4-31b-it] [--batch 20] [--limit N] [--force]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "frontend" / "lib" / "i18n"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
PLACEHOLDER = re.compile(r"\{[^{}]*\}")

SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {"type": "object", "properties": {"i": {"type": "integer"}, "hi": {"type": "string"}}, "required": ["i", "hi"]},
        }
    },
    "required": ["translations"],
}

SYSTEM = """You translate the interface text of a legal-aid web application for Indian lawyers from English into Hindi (Devanagari).
Rules:
- Natural, formal Hindi as used by lawyers and courts in India. Short: a button or a label stays a button or a label.
- Use the usual legal Hindi: bail = जमानत, custody = हिरासत, grounds (of a bail application) = आधार, objection = आपत्ति, hearing = सुनवाई, counsel = अधिवक्ता, precedent = नज़ीर, authority (a cited judgment) = प्राधिकार, brief/draft = मसौदा, facts = तथ्य, rights = अधिकार, gate/approval step = अनुमोदन.
- Keep these as they are, in Latin letters: Vakeel-Sahayak, FIR, IPC, BNS, BNSS, CrPC, NDPS, NALSA, DOCX, PDF, Word, AI, and section numbers.
- Keep every {placeholder}, number, and the final punctuation (a full stop, a colon, a question mark) as in the English.
- Do not explain, do not add or drop information, do not translate a name that is not a word.
Answer with a JSON object {"translations": [{"i": <number>, "hi": "<Hindi>"}, ...]} with one entry per input, same numbers."""


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def valid(en: str, hi: str) -> bool:
    """A usable translation: not empty, not the English back (unless the English has no letters to translate), same placeholders, sane length."""
    hi = hi.strip()
    if not hi:
        return False
    if sorted(PLACEHOLDER.findall(en)) != sorted(PLACEHOLDER.findall(hi)):
        return False
    letters = re.sub(r"[^A-Za-z]", "", PLACEHOLDER.sub("", en))
    if len(letters) > 4 and not DEVANAGARI.search(hi):
        return False
    return len(hi) <= max(40, 4 * len(en))


def parse(text: str) -> dict[int, str]:
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    try:
        obj = json.loads(s[i : j + 1])
    except ValueError:
        return {}
    out: dict[int, str] = {}
    for row in obj.get("translations", []) if isinstance(obj, dict) else []:
        if isinstance(row, dict) and isinstance(row.get("i"), int) and isinstance(row.get("hi"), str):
            out[row["i"]] = row["hi"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="gemma-4-31b-it", help="Gemini-API model id (fallback: gemini-3.1-flash-lite)")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0, help="translate at most N missing strings (0 = all); for a first check")
    ap.add_argument("--force", action="store_true", help="translate everything again")
    args = ap.parse_args()

    source: list[str] = load(I18N / "source.en.json", [])
    if not source:
        print("no source.en.json: run the extractor in frontend/ first", file=sys.stderr)
        return 2
    table: dict[str, str] = {} if args.force else load(I18N / "hi.json", {})
    todo = [s for s in source if s not in table or not valid(s, table[s])]
    done = len(source) - len(todo)
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(source)} strings, {done} already translated, {len(todo)} to do now with {args.model}")
    if not todo:
        return 0

    from vakeel_sahayak.models.hosted.client import HostedLLMClient
    from vakeel_sahayak.models.hosted.probe import _spec
    from vakeel_sahayak.models.sarvam.policy import DataClass, public_scope

    client = HostedLLMClient(_spec("gemini"), args.model, data=DataClass.PUBLIC, role="ui-translate")
    failed: list[str] = []
    for start in range(0, len(todo), args.batch):
        chunk = todo[start : start + args.batch]
        pending = list(chunk)
        for attempt in range(3):
            if not pending:
                break
            payload = json.dumps([{"i": n, "en": en} for n, en in enumerate(pending)], ensure_ascii=False)
            try:
                with public_scope("ui-labels-hi"):
                    text = client.chat(
                        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": payload}],
                        max_tokens=4096,
                        temperature=0.0,
                        json_schema=SCHEMA,
                    )
            except Exception as exc:  # quota, a model that cannot answer: stop, keep what is saved, resume later
                print(f"stopped: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
                _save(table, args.model, len(source))
                return 1
            got = parse(text)
            still: list[str] = []
            for n, en in enumerate(pending):
                hi = got.get(n, "")
                if valid(en, hi):
                    table[en] = hi.strip()
                else:
                    still.append(en)
            pending = still
        failed += pending
        _save(table, args.model, len(source))
        print(f"  {min(start + args.batch, len(todo))}/{len(todo)} done, {len(failed)} failed so far")
    if failed:
        print("not translated (left in English):", *failed, sep="\n  ")
    return 0


def _save(table: dict[str, str], model: str, total: int) -> None:
    (I18N / "hi.json").write_text(json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta = {"model": model, "provider": "gemini (free tier, public interface text)", "date": dt.date.today().isoformat(), "strings": total, "translated": len(table), "reviewed_by_hand": False}
    (I18N / "hi.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
