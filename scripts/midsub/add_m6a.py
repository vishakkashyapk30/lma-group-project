"""Add the M6a columns (`unsupported_case_fact_rate`, `n_case_fact`) to an existing scorer per-case CSV, from the stored run outputs.

M6a is reported BESIDE M6 (never instead). This rescoring touches no other column: it reads each row's brief from the run output it was scored from,
checks only the case-fact sentences (`eval/scoring/split_metric.case_fact_rate`, the scorer's own checker and cut) and writes the two columns.
A row whose run output cannot be found is left blank and listed on stderr (it is not guessed).

    VS_MODELS=auto VS_M6_CHECKER=minicheck python scripts/midsub/add_m6a.py --csv <per_case.csv> --outputs <dir> [<dir> ...] --cases <t1 jsonl> [...]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def index_outputs(roots: list[Path]) -> dict[str, Path]:
    """system (lower case) -> output folder, from every MANIFEST.json under the roots (first found wins)."""
    out: dict[str, Path] = {}
    for root in roots:
        for man in sorted(root.rglob("MANIFEST.json")):
            try:
                system = str(json.loads(man.read_text(encoding="utf-8")).get("system") or "").lower()
            except (OSError, ValueError):
                continue
            if system and system not in out:
                out[system] = man.parent
    return out


def main() -> None:
    from vakeel_sahayak.eval.scoring.split_metric import case_fact_rate

    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--outputs", nargs="+", required=True, type=Path)
    ap.add_argument("--cases", nargs="+", required=True, type=Path)
    args = ap.parse_args()
    facts = {}
    for p in args.cases:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                facts[r["case_id"]] = str(r.get("facts_text") or r.get("facts") or "")
    dirs = index_outputs(args.outputs)
    with args.csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows, cols = list(reader), list(reader.fieldnames or [])
    for c in ("unsupported_case_fact_rate", "n_case_fact"):
        if c not in cols:
            cols.insert(cols.index("unsupported_fact_rate") + 1 if "unsupported_fact_rate" in cols else len(cols), c)
    missing = 0
    for r in rows:
        d = dirs.get(r["system"].lower())
        f = d / f"{r['case_id']}.json" if d else None
        if f is None or not f.is_file() or r["case_id"] not in facts:
            r["unsupported_case_fact_rate"], r["n_case_fact"] = "", ""
            missing += 1
            continue
        brief = json.loads(f.read_text(encoding="utf-8")).get("brief") or {}
        rate, n = case_fact_rate(brief, facts[r["case_id"]])
        r["unsupported_case_fact_rate"], r["n_case_fact"] = ("" if rate is None else rate), n
    with args.csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{args.csv}: {len(rows)} rows, {missing} without a run output", file=sys.stderr)


if __name__ == "__main__":
    main()
