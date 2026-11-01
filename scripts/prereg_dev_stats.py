"""Dev-slice statistics behind the thresholds of docs/preregistration.md.

Reads only docs/results/midsub/*/per_case_agreed.csv (dev orders). Prints, per backend block, Full minus comparator on the registered metrics with the
scorer's own paired bootstrap interval and Wilcoxon p, the SD of the paired differences, and the minimum detectable effect at the blind slice's n.
It never touches the blind slice. Run: PYTHONPATH=src .venv/bin/python scripts/prereg_dev_stats.py > docs/results/prereg/dev_stats.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import csv
import statistics
from collections import defaultdict

from vakeel_sahayak.eval.scoring import engine
from vakeel_sahayak.eval.stats.bootstrap import paired_bootstrap_ci
from vakeel_sahayak.eval.stats.wilcoxon import wilcoxon_signed_rank

ROOT = Path(__file__).resolve().parents[1] / "docs/results/midsub"
METRICS = ["factor_recall", "factor_precision_lenient", "factor_f1", "unsupported_fact_rate", "answerable_coverage", "objection_recall",
           "tokens", "store_calls", "fabricated_citation_rate", "citation_precision", "recall_at_10"]
BLOCKS = {"openai": ["openai_v3b", "a7"], "sarvam": ["sarvam"], "gemini": ["gemini_A"], "v1": ["v1"]}
N_BLIND = 80


def load(dirs: list[str]) -> list[dict]:
    rows = []
    for d in dirs:
        with open(ROOT / d / "per_case_agreed.csv", newline="") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def case_means(rows: list[dict], metric: str) -> dict[str, dict[str, float]]:
    """system (lower case) -> case id -> mean over runs, skipping empty cells (runs are averaged within a case, plan 5.1)."""
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r[metric] not in ("", None):
            acc[r["system"].lower()][r["case_id"]].append(float(r[metric]))
    return {s: {c: sum(v) / len(v) for c, v in cs.items()} for s, cs in acc.items()}


def main() -> None:
    out: dict = {}
    for block, dirs in BLOCKS.items():
        rows = load(dirs)
        n_cases: dict[str, set] = defaultdict(set)
        errs: dict[str, int] = defaultdict(int)
        for r in rows:
            n_cases[r["system"].lower()].add(r["case_id"])
            errs[r["system"].lower()] += int(float(r["n_errors"] or 0))
        out[block] = {"n_cases": {s: len(v) for s, v in sorted(n_cases.items())}, "error_rows": dict(sorted(errs.items())), "metrics": {}}
        for m in METRICS:
            t = case_means(rows, m)
            if "full" not in t:
                continue
            res: dict = {"full_overall": {"mean": round(statistics.mean(t["full"].values()), 4), "n": len(t["full"])}}
            for c in sorted(t):
                if c == "full":
                    continue
                common = sorted(set(t["full"]) & set(t[c]))
                if len(common) < 2:
                    res[c] = {"n": len(common)}
                    continue
                a, b = [t["full"][k] for k in common], [t[c][k] for k in common]
                diff, lo, hi = paired_bootstrap_ci(a, b, engine.N_BOOT)
                try:
                    p = float(wilcoxon_signed_rank(a, b))
                except Exception:  # all differences zero
                    p = 1.0
                sd = statistics.stdev([x - y for x, y in zip(a, b)])
                res[c] = {"n": len(common), "full": round(statistics.mean(a), 4), "comp": round(statistics.mean(b), 4), "diff": round(diff, 4),
                          "lo": round(lo, 4), "hi": round(hi, 4), "p": round(p, 4), "sd_diff": round(sd, 4),
                          "mde_blind80": round(1.96 * sd / math.sqrt(N_BLIND), 4)}
            out[block]["metrics"][m] = res
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
