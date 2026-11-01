"""Paired comparison of the architecture-search arms against Full (and the baselines) on the search cases.

Reads the scorer's `per_case_agreed.csv`, keeps `t1dev-000..029`, and for every arm prints the mean of each metric over the cases where it is defined and the paired
difference to a reference arm (arm minus reference, over the cases where both are defined) with a bootstrap 95% interval (2000 resamples, fixed seed).
A difference below 0.10 is marked `~` (dev gold is thin: factor metrics rest on 8 orders, objection recall on 20: do not rank on it).
Optional `--split` takes `<arm>=<csv>` files written by `eval/scoring/split_metric.py` and adds the separate metric M6a (`unsupported_case_fact_rate`) and its count.

    python scripts/midsub/arch_search_compare.py --scores <per_case_agreed.csv> --ref full --out <report.md> [--split x2=<csv> ...]
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

METRICS = [
    ("objection_recall", "objection recall", True), ("objection_precision", "objection precision", True), ("answerable_coverage", "answerable coverage", True),
    ("coverage", "coverage", True), ("factor_recall", "factor recall", True), ("factor_precision_lenient", "factor precision (lenient)", True), ("factor_f1", "factor F1", True),
    ("citation_precision", "citation precision", True), ("fabricated_citation_rate", "fabricated citations", False), ("unsupported_fact_rate", "unsupported-fact rate (M6)", False),
    ("tokens", "tokens per case", False),
]
CASES = {f"t1dev-{i:03d}" for i in range(30)}


def load(path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """arm -> case -> metric -> value (blank cells left out)."""
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["case_id"] not in CASES:
                continue
            for key, _, _ in METRICS:
                if row.get(key) not in (None, ""):
                    out[row["system"].lower()][row["case_id"]][key] = float(row[key])
    return out


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def paired(arm: dict[str, dict[str, float]], ref: dict[str, dict[str, float]], key: str, seed: int = 7) -> tuple[float | None, float | None, float | None, int]:
    diffs = [arm[c][key] - ref[c][key] for c in arm if c in ref and key in arm[c] and key in ref[c]]
    if not diffs:
        return None, None, None, 0
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(2000))
    return sum(diffs) / len(diffs), boots[int(0.025 * 2000)], boots[int(0.975 * 2000) - 1], len(diffs)


def fmt(x: float | None, tokens: bool = False) -> str:
    return "-" if x is None else (f"{x:,.0f}" if tokens else f"{x:.3f}")


def split_summary(path: Path) -> tuple[float | None, int, int]:
    with path.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["case_id"] in CASES]
    rates = [float(r["unsupported_case_fact_rate"]) for r in rows if r["unsupported_case_fact_rate"] != ""]
    return mean(rates), len(rates), sum(int(r["n_case_fact"]) for r in rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--ref", default="full")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--split", nargs="*", default=[])
    ap.add_argument("--arms", nargs="*", default=None, help="arms to print (default all in the file)")
    args = ap.parse_args()
    data = load(args.scores)
    ref = data[args.ref.lower()]
    arms = [a.lower() for a in (args.arms or sorted(data))]
    lines = [f"Search cases t1dev-000..029; reference `{args.ref}` ({len(ref)} cases). Mean over cases where the metric is defined; paired difference = arm minus reference with a 95% bootstrap interval; n = paired cases; `~` marks |difference| < 0.10.", ""]
    head = "| arm | cases | " + " | ".join(label for _, label, _ in METRICS) + " |"
    lines += [head, "|" + "---|" * (len(METRICS) + 2)]
    for a in arms:
        d = data[a]
        lines.append(f"| {a} | {len(d)} | " + " | ".join(fmt(mean([d[c][k] for c in d if k in d[c]]), k == "tokens") for k, _, _ in METRICS) + " |")
    lines += ["", f"### Paired difference to `{args.ref}` (arm minus {args.ref}; higher is better except fabricated citations, M6 and tokens)", ""]
    lines += ["| arm | " + " | ".join(label for _, label, _ in METRICS) + " |", "|" + "---|" * (len(METRICS) + 1)]
    for a in arms:
        if a == args.ref.lower():
            continue
        cells = []
        for k, _, _ in METRICS:
            m, lo, hi, n = paired(data[a], ref, k)
            if m is None:
                cells.append("-")
            else:
                tok = k == "tokens"
                mark = "" if tok or abs(m) >= 0.10 else " ~"
                cells.append(f"{m:+,.0f}" if tok else f"{m:+.3f} [{lo:+.3f}, {hi:+.3f}] n={n}{mark}")
        lines.append(f"| {a} | " + " | ".join(cells) + " |")
    if args.split:
        lines += ["", "### M6a (separate metric: case-fact sentences only, `eval/scoring/split_metric.py`); never read without the count", "", "| arm | M6a mean | cases with a case-fact sentence | case-fact sentences |", "|---|---|---|---|"]
        for spec in args.split:
            name, _, path = spec.partition("=")
            m, n, total = split_summary(Path(path))
            lines.append(f"| {name} | {fmt(m)} | {n} | {total} |")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
