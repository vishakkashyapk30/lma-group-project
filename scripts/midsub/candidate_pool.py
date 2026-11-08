"""Post-freeze EXPLORATORY dev analysis (pre-registration D9): every Sarvam-scored configuration, compared only like for like.

usage: VS_RUNS=<dev_runs of the run worktree> python3 scripts/midsub/candidate_pool.py

Two blocks, never mixed (an independent provenance check on 9 Nov found the literature-sweep rows on another code tree, 7ad6ed41, with M6 scored
by the offline stand-in checker, while the architecture-search arms share tree b44ddeae and MiniCheck):
  A. arch   the architecture-search arms (single switches X1-X7, combinations, c1457 and its leave-one-out runs) on the 30 dev search orders
            t1dev-000..029, against B0-B6 rerun on the same tree. Same code tree, prompt hash, config hash, gold and scorer.
  B. sweep  the literature sweep on Sarvam (docs/results/midsub/sarvam/per_case_agreed.csv): each variant (S1-S18, P5-P8, A5, and the
            ablations A1-A9) against the sweep's own Full on the orders both answered. Same code and scorer within the block; M6, M6a, the
            unsupported count and confident-wrong there come from the stand-in checker, so they are marked.
Not included: the c1457 "second run" of the ablation batch (a response-cache replay, identical to the first run, not a replication).
Statistics: docs/report/tools/win_loss_tie.py `compare`, imported unchanged (seeded paired bootstrap, Holm 0.05 per arm and metric over the
comparators of that block, a win only when the Holm-level interval excludes zero).
Writes docs/results/search/candidate_pool/{wlt_arch.csv, h2h_arch.csv, wlt_sweep.csv, summary.md}.
"""
import csv
import os
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/report/tools"))
import win_loss_tie as wlt  # noqa: E402

RUNS = Path(os.environ.get("VS_RUNS", ROOT / "data/eval/dev_runs"))
OUT = ROOT / "docs/results/search/candidate_pool"
SWEEP = ROOT / "docs/results/midsub/sarvam/per_case_agreed.csv"
WIN = "s13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
BASES = [f"b{i}" for i in range(7)]
CHECKER = {"unsupported_fact_rate", "unsupported_case_fact_rate", "unsupported_fact_count", "confident_wrong_rate"}
SW = {"signal_source=merge": "X1", "argument_policy=fact_law_split": "X2", "sparring_scope=all_factors": "X3", "abstention=strict": "X4",
      "draft_source=facts_text": "X5", "critic_material=union_free": "X6", "objection_grounding=by_id": "X7", "fact_grounding=verbatim": "X8"}


def lab(s):
    if s == WIN:
        return "c1457 (X1+X4+X5+X7, registered headline)"
    if s.startswith("s13:"):
        parts = s[4:].split(",")
        xs = [SW[p] for p in parts if p in SW]
        rest = [p for p in parts if p not in SW]
        if not xs:
            return "S13:" + ",".join(rest)
        return "+".join(xs) + (" with " + ",".join(rest) if rest else "")
    return s.upper()


def scored(block):
    rows = []
    for f in sorted((RUNS / block / "scores").glob("*/per_case_agreed.csv")):
        rows += list(csv.DictReader(open(f)))
    for r in rows:
        r["system"] = r["system"].lower()
    return rows


def tally(cells, arm, comps=None):
    return Counter(c["outcome"] for c in cells if c["arm"] == arm and (comps is None or c["baseline"] in comps))


def mean_of(by, s, col):
    v = [wlt.value(r, col) for r in by[s].values()]
    v = [x for x in v if x is not None]
    return st.mean(v) if v else float("nan")


def fmt(t):
    return f"{t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']})"


def block_arch(md):
    rows = scored("sarvam_final")
    have = {r["system"] for r in rows}
    for r in scored("sarvam_search"):  # single switches and combinations not rerun in the final block
        if r["system"] not in have and r["system"] not in BASES:
            rows.append(r)
    have = {r["system"] for r in rows}
    rows += [r for r in scored("sarvam_ablate") if r["system"] != WIN and r["system"] not in have]  # leave-one-outs; skip the cache replay
    metrics = [m for m in wlt.DECIDING if m in rows[0]]
    by = wlt.answered(rows)
    arms = sorted(s for s in by if s not in BASES)
    cells = wlt.compare(by, arms, BASES, metrics)
    wlt.write_csv(OUT / "wlt_arch.csv", cells)
    table = []
    for a in arms:
        t = tally(cells, a)
        ls = [f"{wlt.DECIDING[c['metric']][0]} vs {c['baseline'].upper()}" for c in cells if c["arm"] == a and c["outcome"] == "loss"]
        table.append((a, t, ls, mean_of(by, a, "tokens"), mean_of(by, a, "n_claims")))
    table.sort(key=lambda x: (x[1]["loss"], -x[1]["win"], x[3]))  # the search's own rule (3 Nov): fewest losses, then most wins, then tokens
    md += ["## A. Architecture-search arms against B0-B6 (30 dev search orders, one code tree, MiniCheck)", "",
           "Order: fewest losses, then most wins, then fewer tokens (the rule the search used on 3 Nov). W/T/L (+too few, undefined).", "",
           "| arm | vs B0-B6 | mean claims per order | mean tokens | losses |", "|---|---|---|---|---|"]
    for a, t, ls, tok, nc in table:
        md.append(f"| {lab(a)} | {fmt(t)} | {nc:.2f} | {tok:,.0f} | {'; '.join(ls) or 'none'} |")
    # head to head: c1457 against each other arm, one pair at a time (one comparator, so the Holm level is the plain 0.05)
    h = []
    for b in arms:
        if b != WIN:
            h += wlt.compare(by, [WIN], [b], metrics)
    wlt.write_csv(OUT / "h2h_arch.csv", h)
    md += ["", "### c1457 head to head against each arm (paired, same orders, one pair at a time at 0.05; descriptive, no correction over pairs)", "",
           "| other arm | c1457 W/T/L (+too few, undefined) | c1457 better on | c1457 worse on |", "|---|---|---|---|"]
    for b in arms:
        if b == WIN:
            continue
        t = tally(h, WIN, {b})
        better = [wlt.DECIDING[c["metric"]][0] for c in h if c["baseline"] == b and c["outcome"] == "win"]
        worse = [wlt.DECIDING[c["metric"]][0] for c in h if c["baseline"] == b and c["outcome"] == "loss"]
        md.append(f"| {lab(b)} | {fmt(t)} | {', '.join(better) or '-'} | {', '.join(worse) or '-'} |")
    md.append("")


def block_sweep(md):
    rows = [dict(r, system=r["system"].lower()) for r in csv.DictReader(open(SWEEP))]
    metrics = [m for m in wlt.DECIDING if m in rows[0]]
    by = wlt.answered(rows)
    arms = sorted(s for s in by if s != "full" and not s.startswith("b"))
    cells = []
    for a in arms:  # each variant against the sweep's Full only: one comparator, so the Holm level is the plain 0.05
        cells += wlt.compare(by, [a], ["full"], metrics)
    wlt.write_csv(OUT / "wlt_sweep.csv", cells)
    md += ["## B. Literature sweep on Sarvam: each variant against the sweep's own Full (same code and scorer; orders both answered)", "",
           "Metrics marked * (M6, M6a, unsupported count, confident wrong) were scored with the offline stand-in checker in this block.", "",
           "| variant | orders | W/T/L vs Full (+too few, undefined) | better than Full on | worse than Full on |", "|---|---|---|---|---|"]
    star = lambda m: wlt.DECIDING[m][0] + ("*" if m in CHECKER else "")  # noqa: E731
    for a in arms:
        t = tally(cells, a)
        better = [star(c["metric"]) for c in cells if c["arm"] == a and c["outcome"] == "win"]
        worse = [star(c["metric"]) for c in cells if c["arm"] == a and c["outcome"] == "loss"]
        n = len(set(by[a]) & set(by["full"]))
        md.append(f"| {lab(a)} | {n} | {fmt(t)} | {', '.join(better) or '-'} | {', '.join(worse) or '-'} |")
    md.append("")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in ("wlt_pool10.csv", "wlt_pool30.csv", "h2h_pool10.csv", "h2h_pool30.csv", "ranking.csv"):
        (OUT / old).unlink(missing_ok=True)
    md = ["# Candidate pool on Sarvam-105B: post-freeze exploratory dev analysis (pre-registration D9)", "",
          "Generated by scripts/midsub/candidate_pool.py. Like-for-like blocks only; not a registered test. c1457 stays the only headline.", ""]
    block_arch(md)
    block_sweep(md)
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
