"""A separate, clearly named metric beside M6: the unsupported rate of case-fact sentences alone (`unsupported_case_fact_rate`, "M6a").

M6 (`eval/metrics/unsupported_fact.py`, unchanged) scores EVERY sentence of every ground against the order's facts. A sentence that states a legal principle from a
retrieved precedent, or says the record is silent, cannot be entailed by the facts whatever the system does (`docs/handoff/architecture-search-2026-11-01.md` 2.1),
so M6 mixes a drafting defect with a structural one. This module reports the split WITHOUT replacing M6: it classifies each sentence of the same brief by its markers
and scores only the case-fact class against the same facts with the same checker (`unsupported_fact._scorer`, MiniCheck, cut 0.5).

Classes (by the sentence's own markers, never by a model): `case_fact` has an `[F:...]` marker and no `[A:...]`; `legal` has an `[A:...]` marker; `other` has neither.
A sentence of the `case_fact` class that matches the absence template (`agents/vakeel/agent.ABSENCE`) is counted as `absence` and left out of `case_fact`.
The rate is None where a brief has no case-fact sentence, and every table must print the count `n_case_fact` beside it. It applies to every arm alike
(a baseline that writes no markers has all its sentences in `other`, so its M6a is None; that is why M6a is never read alone).

Command: `python -m vakeel_sahayak.eval.scoring.split_metric --runs <outputs dir of one arm> --cases <cases.jsonl> --out <per_case.csv>` (one row per case).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

MARKER = re.compile(r"\[\s*(F|A)\s*:\s*[^\]]+\]")
NOTE_PREFIXES = ("Qualification:", "Warning:")
FIELDS = ["case_id", "n_sentences", "n_case_fact", "n_legal", "n_other", "n_absence", "n_case_fact_unsupported", "unsupported_case_fact_rate", "unsupported_all_rate"]


def classify(sentence: str) -> str:
    """'note', 'case_fact', 'legal', 'other' or 'absence' for one sentence of a ground's argument (markers read, no model)."""
    from vakeel_sahayak.agents.vakeel.agent import ABSENCE

    if sentence.lstrip().startswith(NOTE_PREFIXES):
        return "note"
    kinds = {m.group(1) for m in MARKER.finditer(sentence)}
    if "A" in kinds:
        return "legal"
    plain = MARKER.sub("", sentence)
    if "F" in kinds:
        return "absence" if ABSENCE.search(plain) else "case_fact"
    return "other"


def case_row(brief: dict[str, Any], facts_text: str, case_id: str, score: Any, cut: float) -> dict[str, Any]:
    """One per-case row: the class counts and the unsupported counts of the case-fact class and of all sentences (M6, for reference)."""
    from vakeel_sahayak.eval.feature_common import sentences_of

    counts = {"note": 0, "case_fact": 0, "legal": 0, "other": 0, "absence": 0}
    bad_fact = bad_all = n_all = 0
    for g in (brief or {}).get("grounds") or []:
        for s in sentences_of(str(g.get("argument") or "")):
            kind = classify(s)
            counts[kind] += 1
            if kind == "note":
                continue
            n_all += 1
            unsupported = score(facts_text, s) < cut
            bad_all += unsupported
            if kind == "case_fact":
                bad_fact += unsupported
    n_fact = counts["case_fact"]
    return {
        "case_id": case_id, "n_sentences": n_all, "n_case_fact": n_fact, "n_legal": counts["legal"], "n_other": counts["other"], "n_absence": counts["absence"],
        "n_case_fact_unsupported": bad_fact, "unsupported_case_fact_rate": (bad_fact / n_fact) if n_fact else "", "unsupported_all_rate": (bad_all / n_all) if n_all else "",
    }


def case_fact_rate(brief: dict[str, Any], facts_text: str) -> tuple[float | None, int]:
    """(M6a, number of case-fact sentences) of one brief, for the scorer's per-case row: only the case-fact class is checked (same checker and cut as M6).

    None when the brief has no case-fact sentence (M6a undefined; the count 0 is reported beside it).
    """
    from vakeel_sahayak.eval.feature_common import sentences_of
    from vakeel_sahayak.eval.metrics.unsupported_fact import _scorer

    facts = [s for g in (brief or {}).get("grounds") or [] for s in sentences_of(str(g.get("argument") or "")) if classify(s) == "case_fact"]
    if not facts:
        return None, 0
    _, score, cut = _scorer()
    return sum(1 for s in facts if score(facts_text, s) < cut) / len(facts), len(facts)


def run(runs: Path, cases: Path, out: Path) -> list[dict[str, Any]]:
    """Score every `<case_id>.json` of one arm's output folder; write the per-case CSV and return the rows."""
    from vakeel_sahayak.eval.metrics.unsupported_fact import _scorer

    facts = {}
    for line in cases.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            facts[row["case_id"]] = str(row.get("facts_text") or row.get("facts") or "")
    _, score, cut = _scorer()
    rows = []
    for f in sorted(runs.glob("t1dev-*.json")):
        record = json.loads(f.read_text(encoding="utf-8"))
        cid = f.stem
        if cid in facts:
            rows.append(case_row(record.get("brief") or {}, facts[cid], cid, score, cut))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", required=True, type=Path)
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    rows = run(args.runs, args.cases, args.out)
    rated = [float(r["unsupported_case_fact_rate"]) for r in rows if r["unsupported_case_fact_rate"] != ""]
    print(f"{args.runs}: {len(rows)} cases, case-fact sentences {sum(r['n_case_fact'] for r in rows)}, mean M6a {sum(rated) / len(rated) if rated else float('nan'):.3f} over {len(rated)} cases")


if __name__ == "__main__":
    main()
