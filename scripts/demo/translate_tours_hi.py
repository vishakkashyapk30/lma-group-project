#!/usr/bin/env python3
"""Fill the optional Hindi text (`hi`) of every guided-demo tour, `demo/cases/<slug>/tour.json`, with a Gemini-API model (Gemma by default).

What is translated: on the tour its title, story and the four variant lines; on each of the nine steps its title, caption and the
`filled` labels and values. Each Hindi text is stored in the tour's `hi` object (the contract is `Tour` in
`src/vakeel_sahayak/demo/preload.py`; the frontend shows it when the interface language is Hindi), and `hi.src` keeps, per field, a hash
of the English text it was made from (`title`, `caption`, `variant.offence`, `filled.0.label`, ...). A text whose English did not change
is skipped, so a second run sends nothing; a changed English text is stale and is translated again.

Kept as written, in Latin letters and digits: numbers and dates, section references (BNS 318(4), IPC 420, s.479), the role pseudonyms
(Accused-1, Co-accused-2, Complainant-1, IO-1), police stations and case numbers (PS-1, 112/2024, demo-01), file names, the stage terms
(INTAKE, GATE_1, ...), the Rights Radar statuses (ELIGIBLE, WINDOW_CLOSED, ...), and every other upper-case abbreviation. A translation
that loses one of them, or changes a number, is rejected and asked for again (3 tries); a text that stays rejected is left without
Hindi, so the interface shows the English and `--check` reports it. A text with no words to translate (a file name, a number) is copied.

Privacy: the six demo cases are invented (role pseudonyms only, constructed documents), so the text is public data. The request is sent
under `public_scope` with the data class PUBLIC, exactly like `scripts/translate_ui_hi.py`: the privacy gate still checks it, the
client keeps the key pool, the quota ledger and the retries. The key is read from the environment only (`set -a; . ./.env; set +a`).
Nothing is paid. This script never runs by itself in tests; `--dry-run` and `--check` make no model call and need no key.

    .venv/bin/python scripts/demo/translate_tours_hi.py --dry-run          # strings and requests, writes nothing
    .venv/bin/python scripts/demo/translate_tours_hi.py --check            # exit 1 when any tour has missing or stale Hindi
    set -a; . ./.env; set +a
    VS_MODELS=auto VS_GEMINI=public .venv/bin/python scripts/demo/translate_tours_hi.py [--model gemma-4-31b-it] [--batch 10] [--cases 01-cheating-parity]

After re-recording a demo (`scripts/demo/record_demos.py`), run it again: the recorder rebuilds `tour.json` from English only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
DEMO_CASES = ROOT / "demo" / "cases"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
VARIANT_KEYS = ("offence", "custody", "record", "parity")

# Text that must come back unchanged. Order does not matter; matches may overlap and are all required.
PROTECTED = [
    re.compile(r"\b(?:Co-accused|Accused|Complainant|IO|Witness|Victim|Surety|PW|DW)-\d+\b"),  # role pseudonyms
    re.compile(r"\b(?:PS|case|demo)-\d+\b"),  # police stations, case ids
    re.compile(r"\b\d+/\d{4}\b"),  # FIR and case numbers such as 112/2024
    re.compile(r"\b(?:IPC|BNS|BNSS|CrPC|NDPS|BSA|UAPA|PMLA)\s?\d+[A-Za-z]?(?:\(\w+\))*(?:/\d+[A-Za-z]?(?:\(\w+\))*)*"),  # IPC 420/406, BNS 318(4)
    re.compile(r"\bs\.\s?\d+[A-Za-z]?(?:\(\w+\))*"),  # s.479, s.37(1)(b)
    re.compile(r"\b[A-Z][A-Z0-9_]+\b"),  # abbreviations, stage terms, statuses, ids such as GATE_2, FIR, ELIGIBLE, G5, O3
    re.compile(r"[\w-]+\.(?:pdf|docx|png|jpe?g|json|txt)\b", re.I),  # file names
]
NUMBER = re.compile(r"\d+")
WORD = re.compile(r"[A-Za-z]{2,}")

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

SYSTEM = """You translate the captions of a guided demo of a legal-aid web application for Indian lawyers from English into Hindi (Devanagari). The demo describes invented bail cases.
Rules:
- Natural, formal Hindi as used by lawyers and courts in India. Keep the length and the sentence structure close to the English.
- Use the usual legal Hindi: bail = जमानत, custody = हिरासत, grounds (of a bail application) = आधार, objection = आपत्ति, hearing = सुनवाई, counsel = अधिवक्ता, precedent = नज़ीर, authority (a cited judgment) = प्राधिकार, brief/draft = मसौदा, facts = तथ्य, rights = अधिकार, charge sheet = आरोप-पत्र, accused = अभियुक्त, gate/approval step = अनुमोदन.
- Copy these exactly as written, in Latin letters, never translated or transliterated: every number and date as digits (6,50,000, 14.08.2024, 167), section references (BNS 318(4), IPC 420/406, s.479, NDPS 21(c)), role names with their number (Accused-1, Co-accused-2, Complainant-1, IO-1), PS-1, case and FIR numbers (112/2024, demo-01), file names (01_fir.pdf), and every word written in capital letters (FIR, PDF, OCR, INTAKE, GATE_2, ELIGIBLE, WINDOW_CLOSED, UNANSWERED, G5, O3 and the like), and the names Vakeel-Sahayak, Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, Pairokar.
- Do not add, drop or explain anything. Keep the final punctuation as in the English.
Answer with a JSON object {"translations": [{"i": <number>, "hi": "<Hindi>"}, ...]} with one entry per input, same numbers."""

Translator = Callable[[list[str]], dict[int, str]]
"""A translator takes the English texts of one request and returns {index: Hindi} for those it could translate."""


# ── Pure parts (tested offline) ──────────────────────────────────────────────────────────────────────────────────────────────────────


def sha(text: str) -> str:
    """Hash of an English source text (first 16 hex digits of SHA-256)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def protected_tokens(en: str) -> list[str]:
    """Every piece of the English text that has to appear unchanged in the Hindi, in order of appearance, without repeats."""
    found: list[tuple[int, str]] = []
    for rx in PROTECTED:
        found += [(m.start(), m.group(0)) for m in rx.finditer(en)]
    seen: set[str] = set()
    out: list[str] = []
    for _, tok in sorted(found):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def numbers_of(text: str) -> list[str]:
    """The runs of digits in the text, Devanagari digits counted as ASCII, sorted (so a reordered sentence still matches)."""
    return sorted(NUMBER.findall(text.translate(DEVANAGARI_DIGITS)))


def needs_model(en: str) -> bool:
    """False when nothing is left to translate once the protected pieces and the digits are taken out (a file name, a number)."""
    rest = en
    for tok in sorted(protected_tokens(en), key=len, reverse=True):
        rest = rest.replace(tok, " ")
    return bool(WORD.search(rest))


def check_translation(en: str, hi: str) -> str | None:
    """Why a translation is not usable, or None when it is: not empty, Hindi script present, every number kept (digits compared),
    every protected token present as written, a sane length."""
    hi = hi.strip()
    if not hi:
        return "empty"
    if needs_model(en) and not DEVANAGARI.search(hi):
        return "not in Devanagari"
    if numbers_of(en) != numbers_of(hi):
        return f"numbers differ: {numbers_of(en)} -> {numbers_of(hi)}"
    for tok in protected_tokens(en):
        if tok not in hi:
            return f"lost {tok!r}"
    if len(hi) > max(60, 4 * len(en)):
        return "too long"
    return None


@dataclass(frozen=True)
class Item:
    """One English text of a tour. `step` is the step's index, or None for the tour itself; `key` is `title`, `caption`, `story`,
    `variant.offence`, `filled.0.label` or `filled.0.value`."""

    step: int | None
    key: str
    en: str


def collect(tour: dict) -> list[Item]:
    """Every English text of the tour that has Hindi: tour title, story and variant lines, then per step title, caption, filled."""
    items: list[Item] = []

    def add(step: int | None, key: str, en: object) -> None:
        if isinstance(en, str) and en.strip():
            items.append(Item(step, key, en))

    add(None, "title", tour.get("title"))
    add(None, "story", tour.get("story"))
    variant = tour.get("variant") or {}
    for k in [*VARIANT_KEYS, *[k for k in variant if k not in VARIANT_KEYS]]:
        add(None, f"variant.{k}", variant.get(k))
    for i, step in enumerate(tour.get("steps") or []):
        add(i, "title", step.get("title"))
        add(i, "caption", step.get("caption"))
        for j, f in enumerate(step.get("filled") or []):
            add(i, f"filled.{j}.label", f.get("label"))
            add(i, f"filled.{j}.value", f.get("value"))
    return items


def _owner(tour: dict, step: int | None) -> dict | None:
    node = tour if step is None else (tour.get("steps") or [])[step]
    hi = node.get("hi")
    return hi if isinstance(hi, dict) else None


def _read(hi: dict | None, key: str) -> str | None:
    """The stored Hindi for a key of an `hi` object, or None."""
    if hi is None:
        return None
    parts = key.split(".")
    node: object = hi
    for p in parts:
        if isinstance(node, list):
            node = node[int(p)] if p.isdigit() and int(p) < len(node) else None
        elif isinstance(node, dict):
            node = node.get(p)
        else:
            return None
        if node is None:
            return None
    return node if isinstance(node, str) else None


def status(tour: dict, item: Item) -> str:
    """'ok' (Hindi present, made from this English), 'stale' (Hindi present, English changed since) or 'missing'."""
    hi = _owner(tour, item.step)
    text = _read(hi, item.key)
    if not text or not text.strip():
        return "missing"
    src = (hi or {}).get("src") or {}
    return "ok" if src.get(item.key) == sha(item.en) else "stale"


def pending(tour: dict) -> list[Item]:
    """The items whose Hindi is missing or stale."""
    return [it for it in collect(tour) if status(tour, it) != "ok"]


def apply(tour: dict, item: Item, hindi: str) -> None:
    """Store the Hindi of one item and the hash of its English in `hi.src` (creates `hi`, `variant` and `filled` as needed)."""
    node = tour if item.step is None else tour["steps"][item.step]
    hi = node.get("hi")
    if not isinstance(hi, dict):
        hi = node["hi"] = {}
    parts = item.key.split(".")
    if parts[0] == "variant":
        hi.setdefault("variant", {})[parts[1]] = hindi
    elif parts[0] == "filled":
        rows = hi.setdefault("filled", [])
        j = int(parts[1])
        while len(rows) <= j:
            rows.append({"label": "", "value": ""})
        rows[j][parts[2]] = hindi
    else:
        hi[parts[0]] = hindi
    hi.setdefault("src", {})[item.key] = sha(item.en)


def tidy(tour: dict) -> None:
    """Drop Hindi rows and hashes whose English no longer exists (a step with fewer filled lines, a removed variant line)."""
    live: dict[int | None, set[str]] = {}
    for it in collect(tour):
        live.setdefault(it.step, set()).add(it.key)
    for step in [None, *range(len(tour.get("steps") or []))]:
        node = tour if step is None else tour["steps"][step]
        hi = node.get("hi")
        if not isinstance(hi, dict):
            continue
        keys = live.get(step, set())
        hi["src"] = {k: v for k, v in (hi.get("src") or {}).items() if k in keys}
        if isinstance(hi.get("filled"), list):
            n = 1 + max([int(k.split(".")[1]) for k in keys if k.startswith("filled.")], default=-1)
            hi["filled"] = hi["filled"][:n]
            if not hi["filled"]:
                del hi["filled"]
        if isinstance(hi.get("variant"), dict):
            hi["variant"] = {k: v for k, v in hi["variant"].items() if f"variant.{k}" in keys}
            if not hi["variant"]:
                del hi["variant"]


def batches(texts: list[str], size: int = 10, max_chars: int = 3500) -> list[list[str]]:
    """Group texts into requests of at most `size` texts and about `max_chars` characters (a long text may stand alone)."""
    out: list[list[str]] = []
    cur: list[str] = []
    chars = 0
    for t in texts:
        if cur and (len(cur) >= size or chars + len(t) > max_chars):
            out.append(cur)
            cur, chars = [], 0
        cur.append(t)
        chars += len(t)
    if cur:
        out.append(cur)
    return out


def translate_texts(
    texts: list[str], translator: Translator, size: int = 10, tries: int = 3, on_batch: Callable[[dict[str, str]], None] | None = None
) -> tuple[dict[str, str], dict[str, str]]:
    """Translate distinct English texts through `translator`, a request per batch. Every answer is checked with `check_translation`
    and a rejected text is sent again (up to `tries` times). Returns ({english: hindi} for accepted texts, {english: reason} for the
    rest). `on_batch` is called with each batch's accepted texts, so a caller can save as it goes."""
    done: dict[str, str] = {}
    why: dict[str, str] = {}
    for chunk in batches(list(dict.fromkeys(texts)), size):
        todo = list(chunk)
        got_here: dict[str, str] = {}
        for _ in range(tries):
            if not todo:
                break
            answers = translator(todo)
            still: list[str] = []
            for n, en in enumerate(todo):
                hi = answers.get(n, "")
                reason = check_translation(en, hi)
                if reason is None:
                    got_here[en] = hi.strip()
                    why.pop(en, None)
                else:
                    why[en] = reason
                    still.append(en)
            todo = still
        done.update(got_here)
        if on_batch and got_here:
            on_batch(got_here)
    return done, why


def plan(tours: dict[str, dict], size: int = 10) -> dict:
    """What a run would do, without doing it: counts of strings by state and the number of requests."""
    total = ok = stale = missing = copied = 0
    to_send: list[str] = []
    for tour in tours.values():
        for it in collect(tour):
            total += 1
            st = status(tour, it)
            if st == "ok":
                ok += 1
                continue
            stale += st == "stale"
            missing += st == "missing"
            if needs_model(it.en):
                to_send.append(it.en)
            else:
                copied += 1
    unique = list(dict.fromkeys(to_send))
    return {
        "tours": len(tours), "strings": total, "up_to_date": ok, "missing": missing, "stale": stale, "copied_unchanged": copied,
        "to_translate": len(to_send), "distinct_to_translate": len(unique), "requests": len(batches(unique, size)),
        "characters": sum(len(t) for t in unique),
    }


def run(tours: dict[str, dict], translator: Translator, size: int = 10, save: Callable[[str, dict], None] | None = None) -> dict:
    """Fill every missing or stale Hindi text. Texts with nothing to translate are copied; the rest go to `translator`. `save(slug, tour)`
    is called after each batch and at the end. Returns {'translated', 'copied', 'failed': {english: reason}}."""
    copied = translated = 0
    for slug, tour in tours.items():
        for it in pending(tour):
            if not needs_model(it.en):
                apply(tour, it, it.en)
                copied += 1
        tidy(tour)
        if save:
            save(slug, tour)
    todo = list(dict.fromkeys(it.en for t in tours.values() for it in pending(t)))

    def fill(batch: dict[str, str]) -> None:
        nonlocal translated
        for slug, tour in tours.items():
            touched = False
            for it in pending(tour):
                if it.en in batch:
                    apply(tour, it, batch[it.en])
                    translated += 1
                    touched = True
            if touched and save:
                save(slug, tour)

    _, failed = translate_texts(todo, translator, size, on_batch=fill) if todo else ({}, {})
    return {"translated": translated, "copied": copied, "failed": failed}


# ── Files and the model ──────────────────────────────────────────────────────────────────────────────────────────────────────────────


def load_tours(demo_dir: Path, only: list[str] | None = None) -> dict[str, dict]:
    tours: dict[str, dict] = {}
    for path in sorted(demo_dir.glob("*/tour.json")):
        if only and path.parent.name not in only:
            continue
        tours[path.parent.name] = json.loads(path.read_text(encoding="utf-8"))
    return tours


def save_tour(demo_dir: Path, slug: str, tour: dict) -> None:
    """Write tour.json in the recorder's format (indent 1, UTF-8 as is, final newline)."""
    (demo_dir / slug / "tour.json").write_text(json.dumps(tour, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_answer(text: str) -> dict[int, str]:
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


def request_payload(texts: list[str]) -> str:
    """What one request sends as the user message: the English texts, numbered (the system prompt carries the rules)."""
    return json.dumps([{"i": n, "en": en} for n, en in enumerate(texts)], ensure_ascii=False)


def gemma_translator(model: str) -> Translator:
    """A translator over the repo's hosted client: the Gemini free tier, public data class, behind the privacy gate."""
    from vakeel_sahayak.models.hosted.client import HostedLLMClient
    from vakeel_sahayak.models.hosted.probe import _spec
    from vakeel_sahayak.models.sarvam.policy import DataClass, public_scope

    client = HostedLLMClient(_spec("gemini"), model, data=DataClass.PUBLIC, role="demo-tour-translate")

    def translate(texts: list[str]) -> dict[int, str]:
        with public_scope("demo-tours-hi"):
            text = client.chat(
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": request_payload(texts)}],
                max_tokens=4096,
                temperature=0.0,
                json_schema=SCHEMA,
            )
        return parse_answer(text)

    return translate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo-dir", type=Path, default=DEMO_CASES, help="folder holding <slug>/tour.json (default demo/cases)")
    ap.add_argument("--cases", nargs="*", help="only these slugs")
    ap.add_argument("--model", default="gemma-4-31b-it", help="Gemini-API model id (fallback: gemini-3.1-flash-lite)")
    ap.add_argument("--batch", type=int, default=10, help="texts per request (Gemma times out on 20)")
    ap.add_argument("--dry-run", action="store_true", help="list the strings and the request count; write nothing, call nothing")
    ap.add_argument("--check", action="store_true", help="exit 1 when any tour has missing or stale Hindi; call nothing")
    args = ap.parse_args(argv)

    tours = load_tours(args.demo_dir, args.cases)
    if not tours:
        print(f"no tours under {args.demo_dir}", file=sys.stderr)
        return 2

    if args.check:
        bad = 0
        for slug, tour in tours.items():
            for it in pending(tour):
                bad += 1
                print(f"{slug}: {status(tour, it)} {'tour' if it.step is None else 'step ' + str(it.step + 1)} {it.key}")
        print(f"{bad} missing or stale Hindi texts in {len(tours)} tours" if bad else f"all Hindi texts are current in {len(tours)} tours")
        return 1 if bad else 0

    p = plan(tours, args.batch)
    if args.dry_run:
        for slug, tour in tours.items():
            todo = pending(tour)
            print(f"{slug}: {len(collect(tour))} strings, {len(todo)} to do ({sum(needs_model(i.en) for i in todo)} for the model)")
            for it in todo:
                where = "tour" if it.step is None else f"step {it.step + 1}"
                print(f"  [{where} {it.key}] {'send' if needs_model(it.en) else 'copy'}: {it.en[:90]!r}")
        print(json.dumps(p, indent=2))
        print(f"dry run: {p['to_translate']} strings ({p['distinct_to_translate']} distinct) in {p['requests']} requests, nothing written")
        return 0

    if p["to_translate"] == 0 and p["copied_unchanged"] == 0:
        print("nothing to do: every Hindi text is current")
        return 0
    print(f"{p['strings']} strings, {p['up_to_date']} current, {p['distinct_to_translate']} distinct to translate in {p['requests']} requests with {args.model}")
    translator = gemma_translator(args.model) if p["distinct_to_translate"] else (lambda texts: {})
    try:
        result = run(tours, translator, args.batch, save=lambda slug, tour: save_tour(args.demo_dir, slug, tour))
    except Exception as exc:  # quota, a model that cannot answer: what was saved stays, run again later
        print(f"stopped: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        return 1
    print(f"translated {result['translated']} texts, copied {result['copied']}, failed {len(result['failed'])}")
    for en, why in result["failed"].items():
        print(f"  not translated ({why}): {en[:90]!r}", file=sys.stderr)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
