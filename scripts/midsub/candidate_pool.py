"""Every Sarvam-scored configuration against the baselines, the ablations and the chosen architecture (dev orders only).

usage: VS_RUNS=<dev_runs of the run worktree> python3 scripts/midsub/candidate_pool.py

Pool: the literature sweep on Sarvam (docs/results/midsub/sarvam/per_case_agreed.csv: S1-S18, P5-P8, A5 on 10 dev orders; A1-A9 and Full
on 30), the architecture-search single switches and combinations (sarvam_search, sarvam_final; 30 orders), and c1457.
Comparators: B0-B6 rerun on the arch-search code (sarvam_final), the ablations A1-A9 of the eval plan (Full minus one part, sweep rows) and
the winner's own leave-one-out arms (sarvam_ablate). Statistics: docs/report/tools/win_loss_tie.py `compare`, imported unchanged
(seeded paired bootstrap, Holm at 0.05 per arm and metric over the comparators, a win only when the Holm-level interval excludes zero).

Selection rule (the same for every candidate): rank by (wins - losses) against B0-B6 on the quality
metrics, then by (wins - losses) against the ablations A1-A9, then by fewer losses, then by fewer mean tokens. Two order sets are ranked
separately because the sweep variants exist on 10 orders only: `pool10` (t1dev-000..009, every candidate) and `pool30`
(t1dev-000..029, candidates with all 30). Head to head: c1457 against every candidate on the orders they share.
Writes docs/results/search/candidate_pool/{wlt_pool10.csv, wlt_pool30.csv, wlt_abl30.csv, h2h.csv, ranking.csv, summary.md}.
"""
import csv
import os
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/report/tools"))
import win_loss_tie as wlt  # noqa: E402

RUNS = Path(os.environ.get("VS_RUNS", ROOT / "data/eval/dev_runs"))
OUT = ROOT / "docs/results/search/candidate_pool"
SWEEP = ROOT / "docs/results/midsub/sarvam/per_case_agreed.csv"
WIN_ID = "s13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
BASES = [f"base:b{i}" for i in range(7)]
SWEEP_ABL = [f"sweep:a{i}" for i in (1, 2, 3, 4, 6, 7, 8, 9)]  # A5 is a model swap (base 4B extractor), not a part removed: a candidate
LABEL = {
    "arch:" + WIN_ID: "c1457 (X1+X4+X5+X7, chosen)",
    "arch:" + WIN_ID + ",fact_grounding=verbatim": "c14578 (c1457+X8)",
    "arch:s13:signal_source=merge,abstention=strict,draft_source=facts_text,critic_material=union_free,objection_grounding=by_id": "X1+X4+X5+X6+X7",
    "arch:s13:abstention=strict,critic_material=union_free,objection_grounding=by_id": "X4+X6+X7 (c457 in the search note)",
}


def lab(s):
    if s.startswith("wabl:"):
        on = set(s[len("wabl:s13:"):].split(","))
        full = {"signal_source=merge": "X1", "abstention=strict": "X4", "draft_source=facts_text": "X5", "objection_grounding=by_id": "X7"}
        gone = [x for k, x in full.items() if k not in on]
        extra = sorted(on - set(full))
        return "c1457 minus " + "+".join(gone) + (" with " + ",".join(extra) if extra else "") + " (ablation run)"
    if s.startswith("rerun:"):
        return "c1457, second run (ablation batch)"
    return LABEL.get(s, s)


def scored(block):
    rows = []
    for f in sorted((RUNS / block / "scores").glob("*/per_case_agreed.csv")):
        rows += list(csv.DictReader(open(f)))
    return rows


def load():
    rows = []
    for r in csv.DictReader(open(SWEEP)):
        s = r["system"].lower()
        if s.startswith("b"):
            continue  # the baselines come from the arch-search rerun (one code stamp with c1457)
        rows.append(dict(r, system="sweep:" + s))
    seen = set()
    for block in ("sarvam_final", "sarvam_search"):  # final first: an arm in both keeps its final-block rows
        for r in scored(block):
            s = r["system"].lower()
            key = ("base:" + s) if s in {f"b{i}" for i in range(7)} else ("arch:" + s)
            if block == "sarvam_search" and key in seen:
                continue
            if block == "sarvam_search" and key.startswith("base:"):
                continue
            rows.append(dict(r, system=key, _block=block))
        seen |= {r["system"] for r in rows if r.get("_block") == block}
    for r in scored("sarvam_ablate"):
        s = r["system"].lower()
        rows.append(dict(r, system=("rerun:" + s) if s == WIN_ID else ("wabl:" + s)))  # c1457 rerun beside its ablations: run-to-run spread
    return rows


def tally(cells, arm, comps):
    t = Counter(c["outcome"] for c in cells if c["arm"] == arm and c["baseline"] in comps)
    return t


def mean_of(rows, sys_, col, cases):
    v = [wlt.value(r, col) for r in rows if r["system"] == sys_ and r["case_id"] in cases]
    v = [x for x in v if x is not None]
    return st.mean(v) if v else float("nan")


def main():
    rows = load()
    metrics = [m for m in wlt.DECIDING if m in rows[0]]
    OUT.mkdir(parents=True, exist_ok=True)
    cases_all = sorted({r["case_id"] for r in rows})
    c10 = {c for c in cases_all if c <= "t1dev-009"}
    c30 = {c for c in cases_all if c <= "t1dev-029"}
    md = ["# Candidate pool on Sarvam-105B (generated by scripts/midsub/candidate_pool.py; dev orders only)", "",
          "Statistics: win_loss_tie.compare unchanged (paired bootstrap, Holm 0.05 per arm and metric). Cells: W/T/L (+too few, undefined).",
          "Ranking: (W-L) vs B0-B6, then (W-L) vs A1-A9, then fewer losses, then fewer tokens. Holm families: B0-B6, and separately A1-A9.", ""]
    rank_rows = []
    for tag, cases in (("pool10", c10), ("pool30", c30)):
        by = wlt.answered(rows, cases)
        cands = sorted(s for s in by if s.startswith(("sweep:", "arch:", "wabl:", "rerun:")) and s not in SWEEP_ABL and len(by[s]) >= len(cases) - 1)
        comps = [b for b in BASES + SWEEP_ABL if b in by]
        # two Holm families per (candidate, metric), as in final_tables.py: the baselines, and separately the ablations
        cells = wlt.compare(by, cands, [b for b in BASES if b in by], metrics)
        cells += wlt.compare(by, cands, [b for b in SWEEP_ABL if b in by], metrics)
        wlt.write_csv(OUT / f"wlt_{tag}.csv", cells)
        table = []
        for a in cands:
            tb, ta = tally(cells, a, set(BASES)), tally(cells, a, set(SWEEP_ABL))
            losses = [f"{wlt.DECIDING[c['metric']][0]} vs {c['baseline'].split(':')[1].upper()}" for c in cells
                      if c["arm"] == a and c["outcome"] == "loss"]
            tok = mean_of(rows, a, "tokens", cases)
            table.append((a, tb, ta, losses, tok))
        table.sort(key=lambda x: (-(x[1]["win"] - x[1]["loss"]), -(x[2]["win"] - x[2]["loss"]), x[1]["loss"] + x[2]["loss"], x[4]))
        md += [f"## {tag}: {len(cases)} dev orders, {len(cands)} candidates; comparators B0-B6 and the sweep ablations "
               + ", ".join(b.split(':')[1].upper() for b in SWEEP_ABL if b in comps), "",
               "| rank | candidate | vs B0-B6 | vs A1-A9 | mean tokens | losses |", "|---|---|---|---|---|---|"]
        for i, (a, tb, ta, losses, tok) in enumerate(table, 1):
            md.append(f"| {i} | {lab(a)} | {tb['win']}/{tb['tie']}/{tb['loss']} (+{tb['too_few']}, {tb['undefined']}) | "
                      f"{ta['win']}/{ta['tie']}/{ta['loss']} (+{ta['too_few']}, {ta['undefined']}) | {tok:,.0f} | {'; '.join(losses) or 'none'} |")
            rank_rows.append({"block": tag, "rank": i, "candidate": a, "label": lab(a), "base_w": tb["win"], "base_t": tb["tie"],
                              "base_l": tb["loss"], "base_too_few": tb["too_few"], "abl_w": ta["win"], "abl_t": ta["tie"], "abl_l": ta["loss"],
                              "abl_too_few": ta["too_few"], "tokens": round(tok), "losses": "; ".join(losses)})
        md.append("")
        # head to head: c1457 as the arm, every other candidate as a comparator (Holm over all of them, per metric)
        win = "arch:" + WIN_ID
        others = [a for a in cands if a != win]
        h = wlt.compare(by, [win], others, metrics)
        wlt.write_csv(OUT / f"h2h_{tag}.csv", h)
        md += [f"### Head to head on {tag}: c1457 against every other candidate and its own leave-one-out arms", "",
               "| comparator | c1457 W/T/L (+too few, undefined) | c1457 loses on |", "|---|---|---|"]
        for b in others:
            t = tally(h, win, {b})
            ls = [wlt.DECIDING[c["metric"]][0] for c in h if c["baseline"] == b and c["outcome"] == "loss"]
            md.append(f"| {lab(b)} | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) | {', '.join(ls) or 'none'} |")
        md.append("")
    with open(OUT / "ranking.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rank_rows[0]))
        w.writeheader()
        w.writerows(rank_rows)
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
