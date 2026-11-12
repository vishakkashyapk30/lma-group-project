"""Win / loss / tie table of architecture-search arms against every baseline, metric by metric (search cases t1dev-000..029).

For each (arm, baseline, metric): the paired difference arm minus baseline over the cases where both define the metric, with a 95% bootstrap interval
(2000 resamples, fixed seed). W = the interval excludes zero in the arm's favour, L = it excludes zero against the arm, T = it includes zero (a tie, also
when every paired difference is zero), `n/a` = no paired case. Direction: higher is better except fabricated citations, the unsupported-fact rate (M6) and
tokens. M6a (case-fact sentences only) is a separate metric and is not in this table.

    python scripts/midsub/arch_search_table.py --scores <merged per-case CSV> --arms full x4 ... --baselines b0 b1 b2 b3 b4 b5 b6 --out <md>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arch_search_compare import METRICS, load, mean, paired  # noqa: E402

LOWER_BETTER = {"fabricated_citation_rate", "unsupported_fact_rate", "tokens"}


def verdict(arm, base, key):
    m, lo, hi, n = paired(arm, base, key)
    if m is None:
        return "n/a", None, n
    good = -1 if key in LOWER_BETTER else 1
    if lo is not None and hi is not None and lo * good > 0 and hi * good > 0:
        return "W", m, n
    if lo is not None and hi is not None and lo * good < 0 and hi * good < 0:
        return "L", m, n
    return "T", m, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--baselines", nargs="+", required=True, help="column names in the CSV (lower case), e.g. b0_old b4")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    data = load(args.scores)
    lines = []
    for a in [x.lower() for x in args.arms]:
        lines += [f"#### {a}", "", "| metric | arm mean | " + " | ".join(args.baselines) + " | wins / losses / ties |", "|" + "---|" * (len(args.baselines) + 3)]
        tot = {"W": 0, "L": 0, "T": 0}
        for key, label, _ in METRICS:
            d = data.get(a, {})
            am = mean([d[c][key] for c in d if key in d[c]])
            cells, cnt = [], {"W": 0, "L": 0, "T": 0}
            for b in args.baselines:
                v, m, n = verdict(d, data.get(b.lower(), {}), key)
                cnt[v] = cnt.get(v, 0) + 1
                cells.append("n/a" if m is None else (f"{v} {m:+,.0f}" if key == "tokens" else f"{v} {m:+.3f} (n={n})"))
            for k in tot:
                tot[k] += cnt.get(k, 0)
            fmt = "-" if am is None else (f"{am:,.0f}" if key == "tokens" else f"{am:.3f}")
            lines.append(f"| {label} | {fmt} | " + " | ".join(cells) + f" | {cnt['W']} / {cnt['L']} / {cnt['T']} |")
        lines += ["", f"Total over metrics and baselines: {tot['W']} wins, {tot['L']} losses, {tot['T']} ties.", ""]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
