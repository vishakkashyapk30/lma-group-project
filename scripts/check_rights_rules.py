"""Check each Rights rule against the statute store and record the result: `last_verified` is written only when every cited section matches.

For every rule in `configs/rights_rules.yaml` the script finds the statute sections the rule cites (in its `rule` text and its `sources`),
looks each up in the statute store (`data/stores/law/statutes.sqlite`, built from official texts), and checks, per section, what
`configs/rights_statute_checks.yaml` says the rule relies on: the section number exists, its heading is the expected one, the cited
sub-section is in the text, and every condition pattern matches the text. It also checks every "<n> days" or "<n> hours" in the rule
text against the word form in the cited sections ("90 days" -> "ninety days"). A rule matches when it cites at least one statute
section and nothing fails. Sources outside the store (the Constitution, judgments) are listed and do not decide.

Writes:
* `configs/rights_rules.yaml`: for a matching rule `last_verified: <date>` and `verified_hash: <rights.verify_hash.rule_hash>`; for any
  other rule `last_verified: null` and no hash. Only those two keys (and the stale "no verified_hash" comments) are touched.
* `docs/results/rights/rule_check.json`: the full result (the consistency checks and tests read it).
* `docs/qa/rights-verification.md`: the section between the `rights-check` markers (mismatches first).

Usage: `.venv/bin/python scripts/check_rights_rules.py [--store P] [--date YYYY-MM-DD] [--check]`. `--check` writes nothing and exits 1
when the yaml or the report disagrees with what the store says now.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "configs" / "rights_rules.yaml"
SPEC = ROOT / "configs" / "rights_statute_checks.yaml"
REPORT = ROOT / "docs" / "results" / "rights" / "rule_check.json"
QA_DOC = ROOT / "docs" / "qa" / "rights-verification.md"
START, END = "<!-- rights-check:start -->", "<!-- rights-check:end -->"

CODES = ("BNSS", "CrPC", "NDPS", "UAPA", "PMLA", "BNS", "IPC", "Companies Act")
_CITE = re.compile(r"\b(" + "|".join(re.escape(c) for c in CODES) + r")\s+s\.\s*(\d+[A-Z]*)((?:\([0-9a-zA-Z]+\))*)")
_ARTICLE = re.compile(r"\bArt\.\s*\d+[A-Z]?(?:\(\d+\))*")
_QUANTITY = re.compile(r"\b(\d+)\s+(days|hours)\b")
NUMBER_WORDS = {7: "seven", 15: "fifteen", 24: "twenty-four", 30: "thirty", 60: "sixty", 90: "ninety", 180: "one hundred and eighty"}


def normalise(text: str) -> str:
    """Lower case, footnote marks and square brackets removed, curly quotes straight, whitespace collapsed."""
    t = re.sub(r"\[\d+\]", "", text)
    t = t.replace("[", "").replace("]", "").replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def citations(section: dict[str, Any]) -> tuple[dict[str, set[str]], list[str]]:
    """({"BNSS s.187": {"(3)"}, ...}, [sources outside the store]) from a rule's `rule` text and `sources`."""
    found: dict[str, set[str]] = {}
    outside: list[str] = []
    texts = [str(section.get("rule") or "")] + [str(s) for s in section.get("sources") or []]
    for i, text in enumerate(texts):
        hits = list(_CITE.finditer(text))
        for m in hits:
            subs = re.findall(r"\([0-9a-zA-Z]+\)", m.group(3))
            found.setdefault(f"{m.group(1)} s.{m.group(2)}", set()).update(subs[:1])
        outside += [a.group(0) for a in _ARTICLE.finditer(text)]
        if i > 0 and not hits and not _ARTICLE.search(text):
            outside.append(text)  # a judgment
    return found, sorted(set(outside), key=outside.index)


def heading_of(text: str) -> str:
    """The section heading of a store row: the first line ("Heading\\n\\nN. ...") or the words between "N." and the dash ("N. Heading.—")."""
    first = text.strip().split("\n", 1)[0]
    m = re.match(r"\s*\d+[A-Z]*\.\s*(.+?)\s*\.?\s*(?:[—–]|\.-)", first[:400])
    return (m.group(1) if m else first).strip().rstrip(".")


def check_section(key: str, spec: dict[str, Any] | None, row_text: str | None, subs: set[str]) -> list[str]:
    """Problems with one cited section (empty when it matches)."""
    if spec is None:
        return [f"{key}: no entry in configs/rights_statute_checks.yaml, so nothing says what the rule relies on"]
    if row_text is None:
        return [f"{key}: not in the statute store"]
    problems = []
    text = normalise(row_text)
    heading = heading_of(row_text)
    if not re.fullmatch(spec["heading"].lower(), normalise(heading)):
        problems.append(f"{key}: heading in the store is '{heading}', expected '{spec['heading']}'")
    for sub in sorted(subs | ({spec["sub"]} if spec.get("sub") else set())):
        if sub.lower() not in text:
            problems.append(f"{key}: sub-section {sub} is not in the store text")
    for cond in spec.get("conditions") or []:
        if not re.search(cond["pattern"], text):
            problems.append(f"{key}: does not state '{cond['says']}'")
    return problems


def quantity_problems(rule_text: str, texts: list[str], from_judgment: dict[str, str] | None = None, sources: list[str] | None = None) -> list[str]:
    """Every '<n> days|hours' in the rule text must appear as words in at least one cited section, unless the spec names the cited
    judgment it comes from (`_from_judgment`), and that judgment must then be one of the rule's sources."""
    joined = " ".join(normalise(t) for t in texts)
    out = []
    for n, unit in sorted({(int(m.group(1)), m.group(2)) for m in _QUANTITY.finditer(rule_text)}):
        judgment = (from_judgment or {}).get(f"{n} {unit}")
        if judgment:
            if judgment not in (sources or []):
                out.append(f"rule text: '{n} {unit}' is attributed to '{judgment}', which is not among the rule's sources")
            continue
        word = NUMBER_WORDS.get(n)
        if word is None:
            out.append(f"rule text: '{n} {unit}' has no word form to look for")
        elif f"{word} {unit}" not in joined:
            out.append(f"rule text: '{n} {unit}' ('{word} {unit}') is in none of the cited sections")
    return out


def open_store(path: Path) -> dict[tuple[str, str], str]:
    """(code, section) -> text of the statute store; refuses a missing file (the store's own fallback is a small seed)."""
    if not path.is_file():
        raise SystemExit(f"{path}: statute store not found (make data, or build it with build_all --only statutes)")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return {(c, s): t for c, s, t in con.execute("SELECT code, section, text FROM statutes")}
    finally:
        con.close()


def check_rules(rules: dict[str, Any], spec: dict[str, Any], store: dict[tuple[str, str], str]) -> dict[str, dict[str, Any]]:
    """Per rule: matched, the sections checked with their problems, and the sources outside the store."""
    out: dict[str, dict[str, Any]] = {}
    for name, section in rules.items():
        cites, outside = citations(section)
        rule_spec = spec.get(name) or {}
        problems: list[str] = []
        texts: list[str] = []
        checked = []
        for key in sorted(cites):
            code, num = key.rsplit(" s.", 1)
            text = store.get((code, num))
            texts += [text] if text else []
            p = check_section(key, (rule_spec.get("sections") or {}).get(key), text, cites[key])
            checked.append({"section": key, "subs": sorted(cites[key]), "in_store": text is not None, "problems": p})
            problems += p
        problems += quantity_problems(str(section.get("rule") or ""), texts, rule_spec.get("from_judgment"), [str(x) for x in section.get("sources") or []])
        if not cites:
            problems.append("cites no statute section, so the store cannot confirm it")
        out[name] = {"matched": not problems, "sections": checked, "problems": problems, "outside_store": outside}
    return out


def update_rules_yaml(text: str, results: dict[str, dict[str, Any]], hashes: dict[str, str], day: str) -> str:
    """Rewrite only `last_verified` / `verified_hash` (and stale 'no verified_hash' comments) in each rule's block."""
    lines = text.split("\n")
    out: list[str] = []
    block: str | None = None

    def emit_keys(name: str) -> list[str]:
        if results[name]["matched"]:
            return [f'  last_verified: "{day}"  # scripts/check_rights_rules.py against the statute store',
                    f"  verified_hash: {hashes[name]}  # rights/verify_hash.py: rule text and code as checked"]
        return ["  last_verified: null  # scripts/check_rights_rules.py: see docs/qa/rights-verification.md"]

    for line in lines:
        top = re.match(r"^([a-z_0-9]+):\s*$", line)
        if top:
            block = top.group(1) if top.group(1) in results else None
        if block and re.match(r"^  (verified_hash:|# no verified_hash)", line):
            continue
        if block and re.match(r"^  last_verified:", line):
            out += emit_keys(block)
            continue
        out.append(line)
    return "\n".join(out)


def qa_section(results: dict[str, dict[str, Any]], day: str, store_path: str) -> str:
    """The markdown between the markers in docs/qa/rights-verification.md."""
    n = sum(r["matched"] for r in results.values())
    md = [START, "", f"## Automatic check against the statute store ({day})", "",
          f"Written by `scripts/check_rights_rules.py` (no reading by hand). Store: `{store_path}`. What each cited section must state: "
          "`configs/rights_statute_checks.yaml`. A rule gets `last_verified` only when every cited statute section matches; sources "
          "outside the store (the Constitution, judgments) are listed and do not decide.", "",
          f"**{n} of {len(results)} rules match.**", "", "| Rule | Result | Sections checked | Outside the store |", "|---|---|---|---|"]
    order = sorted(results, key=lambda k: (results[k]["matched"], k))
    for name in order:
        r = results[name]
        secs = ", ".join(s["section"] + "".join(s["subs"]) for s in r["sections"]) or "none"
        md.append(f"| `{name}` | {'match' if r['matched'] else 'MISMATCH'} | {secs} | {'; '.join(r['outside_store']) or 'none'} |")
    mism = [k for k in order if not results[k]["matched"]]
    if mism:
        md += ["", "### Mismatches", ""]
        for name in mism:
            md.append(f"- `{name}`")
            md += [f"  - {p}" for p in results[name]["problems"]]
    md += ["", END]
    return "\n".join(md)


def replace_marked(doc: str, section: str) -> str:
    """Replace the marked section of the document, or append it."""
    if START in doc and END in doc:
        return doc[: doc.index(START)] + section + doc[doc.index(END) + len(END):]
    return doc.rstrip("\n") + "\n\n" + section + "\n"


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.rights.verify_hash import effective_last_verified, rule_hash

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--store", type=Path, default=None, help="statute SQLite file (default: the configured stores dir)")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if the yaml or the report is out of date")
    args = ap.parse_args(argv)
    cfg = load_config()
    store_path = args.store or Path(cfg.paths.stores_dir) / cfg.stores["law"]["statutes"]["path"]
    rules_text = RULES.read_text(encoding="utf-8")
    rules = yaml.safe_load(rules_text)
    results = check_rules(rules, yaml.safe_load(SPEC.read_text(encoding="utf-8")), open_store(Path(store_path)))
    hashes = {name: rule_hash(name, rules) for name in rules}
    for name, r in results.items():
        print(f"{name}\t{'match' if r['matched'] else 'MISMATCH'}")
        for p in r["problems"]:
            print(f"  - {p}")
    if args.check:
        stale = [n for n, r in results.items() if bool(effective_last_verified(n, rules[n], rules)) != r["matched"]]
        recorded = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
        if {n: r["matched"] for n, r in (recorded.get("rules") or {}).items()} != {n: r["matched"] for n, r in results.items()}:
            stale.append("docs/results/rights/rule_check.json")
        if stale:
            print(f"out of date: {', '.join(stale)} (run scripts/check_rights_rules.py)", file=sys.stderr)
            return 1
        return 0
    RULES.write_text(update_rules_yaml(rules_text, results, hashes, args.date), encoding="utf-8")
    shown = str(store_path.relative_to(ROOT)) if Path(store_path).is_relative_to(ROOT) else str(store_path)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"checked_on": args.date, "store": shown, "rules": results}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    QA_DOC.write_text(replace_marked(QA_DOC.read_text(encoding="utf-8"), qa_section(results, args.date, shown)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
