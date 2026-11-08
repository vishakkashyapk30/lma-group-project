"""Final tables of the architecture search (owner decisions of 7 Nov, docs/handoff/arch-search-results.md).

usage: python3 scripts/midsub/final_tables.py   (run from the repository root after the holdout and ablation arms are scored)

Blocks, each with the same statistics as docs/report/tools/win_loss_tie.py (its `compare`, imported unchanged: seeded paired
bootstrap, Holm at 0.05 per arm and metric over the comparators, a win only when the Holm-level interval excludes zero):
  search   30 dev orders t1dev-000..029, every arm on one commit (data/eval/dev_runs/sarvam_final)
  holdout  20 dev orders t1dev-030..049, touched once (data/eval/dev_runs/sarvam_holdout)
  pooled   all 50 dev orders (search + holdout; same src tree), the only block where the factor metrics have enough orders
  ablate   the winner rerun against each ablation on the 30 search orders (data/eval/dev_runs/sarvam_ablate)
Quality metrics decide. Cost (tokens, store calls, seconds) is a separate table judged only against B4 and B5, the baselines of
comparable capability; against B0-B3 and B6 it is shown, not counted. Every numeric column the scorer writes gets a mean.
Writes docs/results/search/final_report/{means_<block>.csv, wlt_<block>.csv, cost.csv, summary.md} and
docs/report/generated/arch_{wlt,ablate,cost}.tex.
"""
import csv
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/report/tools"))
import win_loss_tie as wlt  # noqa: E402
from make_result_tables import esc, fit  # noqa: E402

RUNS = ROOT / "data/eval/dev_runs"
OUT = ROOT / "docs/results/search/final_report"
GEN = ROOT / "docs/report/generated"
WIN = "s13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
BASES = ["b0", "b1", "b2", "b3", "b4", "b5", "b6"]
NAMES = {WIN: "c1457 (winner)", "full": "Full", "a7": "A7"}
ABL = {  # ablation arm (system id, lower case) -> label
    "s13:abstention=strict,draft_source=facts_text,objection_grounding=by_id": "minus X1 (dossier gaps from facts)",
    "s13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id": "minus X4 (strict abstention)",
    "s13:signal_source=merge,abstention=strict,objection_grounding=by_id": "minus X5 (draft from facts)",
    "s13:signal_source=merge,abstention=strict,draft_source=facts_text": "minus X7 (objections by id)",
    WIN + ",no_tools=true": "A3 no tools",
    WIN + ",plain_retrieval=true": "A4 plain retrieval",
    WIN + ",fixed_router=true": "A6 fixed router",
    WIN + ",free_planner=true": "A7 free planner",
    "s13:abstention=strict,objection_grounding=by_id,no_dossier=true": "A1 no dossier (without X1, X5)",
    "s13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id,no_check_repair=true": "A2 no check-repair (without X4)",
    "s13:signal_source=merge,abstention=strict,draft_source=facts_text,no_sparring=true": "A8 no sparring (without X7)",
    "s13:signal_source=merge,draft_source=facts_text,no_sparring=true,no_check_repair=true": "A9 neither (without X4, X7)",
}
COST = {"tokens": ("Tokens", False), "store_calls": ("Store calls", False), "seconds": ("Seconds", False)}


def name(s):
    return NAMES.get(s) or ABL.get(s) or s


def rows_of(block):
    rows = []
    for f in sorted((RUNS / block / "scores").glob("*/per_case_agreed.csv")):
        rows += list(csv.DictReader(open(f)))
    for r in rows:
        r["system"] = r["system"].lower()
    return rows


def numeric_columns(rows):
    skip = {"system", "run", "case_id", "retrieved_source", "passed"}
    cols = []
    for k in rows[0]:
        if k in skip:
            continue
        if any(wlt.value(r, k) is not None for r in rows if _num(r.get(k))):
            cols.append(k)
    return cols


def _num(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def means(rows, block):
    by = defaultdict(list)
    for r in rows:
        by[r["system"]].append(r)
    cols = numeric_columns(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"means_{block}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "label", "cases"] + cols)
        for s, rs in sorted(by.items(), key=lambda kv: (kv[0] not in (WIN, "full"), kv[0])):
            vals = []
            for c in cols:
                v = [float(r[c]) for r in rs if _num(r.get(c)) and r[c] not in ("nan",)]
                vals.append(f"{st.mean(v):.4g} (n={len(v)})" if v else "")
            w.writerow([s, name(s), len(rs)] + vals)
    return cols


def run_wlt(rows, arms, comps, block, metrics=None, extra=None):
    by_sys = wlt.answered(rows)
    arms = [a for a in arms if a in by_sys]
    comps = [b for b in comps if b in by_sys]
    if extra:
        wlt.DECIDING.update(extra)
    cols = set(rows[0])
    metrics = [m for m in (metrics or wlt.DECIDING) if m in cols]
    cells = wlt.compare(by_sys, arms, comps, metrics)
    if extra:
        for k in extra:
            wlt.DECIDING.pop(k, None)
    wlt.write_csv(OUT / f"wlt_{block}.csv", cells)
    return cells, arms, comps


def tally(cells, arm, comp=None):
    return Counter(c["outcome"] for c in cells if c["arm"] == arm and (comp is None or c["baseline"] == comp))


def losses(cells, arm):
    return [f"{wlt.DECIDING.get(c['metric'], COST.get(c['metric'], (c['metric'],)))[0]} vs {name(c['baseline'])}"
            for c in cells if c["arm"] == arm and c["outcome"] == "loss"]


def main():
    md = ["# Final tables of the architecture search (generated by scripts/midsub/final_tables.py)", ""]
    blocks = {"search": rows_of("sarvam_final"), "holdout": rows_of("sarvam_holdout")}
    pooled_arms = {WIN, "full", *BASES}
    blocks["pooled"] = [r for b in ("search", "holdout") for r in blocks[b] if r["system"] in pooled_arms]
    tex_rows = []
    for block in ("search", "holdout", "pooled"):
        rows = blocks[block]
        if not rows:
            md.append(f"## {block}: not scored yet\n")
            continue
        means(rows, block)
        cells, arms, comps = run_wlt(rows, [WIN, "full", "a7"], BASES, block)
        md += [f"## {block} ({len({r['case_id'] for r in rows})} orders): quality, against B0-B6", "",
               "| arm | " + " | ".join(b.upper() for b in comps) + " | total W/T/L (+too few, undefined) | losses |",
               "|---|" + "---|" * (len(comps) + 2)]
        for a in arms:
            per = []
            for b in comps:
                t = tally(cells, a, b)
                per.append(f"{t['win']}/{t['tie']}/{t['loss']}")
            t = tally(cells, a)
            md.append(f"| {name(a)} | " + " | ".join(per) + f" | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) | "
                      + ("; ".join(losses(cells, a)) or "none") + " |")
            tex_rows.append((block, name(a), [tally(cells, a, b) for b in comps], t))
        md.append("")
    # cost, judged only against B4 and B5
    cost_cells = []
    for block in ("search", "holdout"):
        rows = blocks[block]
        if rows:
            cells, _, _ = run_wlt(rows, [WIN, "full"], ["b4", "b5"], f"cost_{block}", metrics=list(COST), extra=COST)
            cost_cells += [dict(c, block=block) for c in cells]
    md += ["## Cost against B4 and B5 (lower is better; not counted against B0-B3 and B6)", "",
           "| block | arm | metric | vs | arm mean | baseline mean | outcome |", "|---|---|---|---|---|---|---|"]
    for c in cost_cells:
        md.append(f"| {c['block']} | {name(c['arm'])} | {COST[c['metric']][0]} | {c['baseline'].upper()} | "
                  f"{c.get('arm_mean', float('nan')):.0f} | {c.get('base_mean', float('nan')):.0f} | {c['outcome']} |")
    md.append("")
    # ablations: the winner against each ablation (the winner is the "arm", each ablation a comparator)
    rows = rows_of("sarvam_ablate")
    abl_rows = []
    if rows:
        means(rows, "ablate")
        comps = [a for a in ABL if a in {r["system"] for r in rows}]
        cells, arms, comps = run_wlt(rows, [WIN], comps, "ablate")
        md += ["## Ablations: the winner against each ablation (30 search orders)", "",
               "| ablation | winner W/T/L (+too few, undefined) | winner loses on |", "|---|---|---|"]
        for b in comps:
            t = tally(cells, WIN, b)
            ls = [wlt.DECIDING[c["metric"]][0] for c in cells if c["baseline"] == b and c["outcome"] == "loss"]
            md.append(f"| {name(b)} | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) | {', '.join(ls) or 'none'} |")
            abl_rows.append((name(b), t, ls))
        missing = [name(a) for a in ABL if a not in comps]
        if missing:
            md += ["", "Not scored yet: " + ", ".join(missing)]
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    write_tex(tex_rows, abl_rows, cost_cells)
    print("\n".join(md))


def write_tex(tex_rows, abl_rows, cost_cells):
    GEN.mkdir(parents=True, exist_ok=True)
    L = [r"\begin{table*}[!t]", r"\centering\small", r"\begin{tabular}{@{}ll" + "c" * len(BASES) + r"c@{}}", r"\toprule",
         "Block & Arm & " + " & ".join(b.upper() for b in BASES) + r" & Total \\", r"\midrule"]
    prev = None
    for block, a, per, t in tex_rows:
        cells = [f"{x['win']}/{x['tie']}/{x['loss']}" for x in per]
        L.append(f"{block if block != prev else ''} & {esc(a)} & " + " & ".join(cells) + f" & {t['win']}/{t['tie']}/{t['loss']} \\\\")
        prev = block
    L += [r"\bottomrule", r"\end{tabular}", r"\caption{Architecture search on Sarvam-105B: wins/ties/losses on the quality metrics "
          r"against each baseline (paired bootstrap, Holm at 0.05 per arm and metric; a win only when the interval excludes zero). "
          r"Search: 30 dev orders, every arm on one commit; holdout: 20 further dev orders, touched once; pooled: all 50. "
          r"c1457 is Full with X1, X4, X5 and X7. Cost is in Table~\ref{tab:arch_cost}.}", r"\label{tab:arch_wlt}", r"\end{table*}"]
    (GEN / "arch_wlt.tex").write_text(fit("\n".join(L) + "\n"))
    L = [r"\begin{table}[!t]", r"\centering\small", r"\begin{tabular}{@{}lcl@{}}", r"\toprule", r"Ablation & W/T/L & Winner loses on \\", r"\midrule"]
    for b, t, ls in abl_rows:
        L.append(f"{esc(b)} & {t['win']}/{t['tie']}/{t['loss']} & {esc(', '.join(ls) or 'none')} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\caption{The winner c1457 against each ablation on the 30 search orders (wins, ties, "
          r"losses of the winner; same statistics as Table~\ref{tab:arch_wlt}).}", r"\label{tab:arch_ablate}", r"\end{table}"]
    (GEN / "arch_ablate.tex").write_text(fit("\n".join(L) + "\n"))
    L = [r"\begin{table}[!t]", r"\centering\small", r"\begin{tabular}{@{}llllrrl@{}}", r"\toprule",
         r"Block & Arm & Metric & vs & Arm & Base & Outcome \\", r"\midrule"]
    for c in cost_cells:
        L.append(f"{c['block']} & {esc(name(c['arm']))} & {COST[c['metric']][0]} & {c['baseline'].upper()} & "
                 f"{c.get('arm_mean', 0):.0f} & {c.get('base_mean', 0):.0f} & {c['outcome']} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\caption{Cost per order against B4 and B5, the baselines of comparable capability "
          r"(lower is better). Against the one-call baselines B0--B3 and the template B6 cost is shown in the means tables, not counted.}",
          r"\label{tab:arch_cost}", r"\end{table}"]
    (GEN / "arch_cost.tex").write_text(fit("\n".join(L) + "\n"))


if __name__ == "__main__":
    main()
