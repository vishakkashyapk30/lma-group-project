"""Final tables of the architecture search (owner decisions of 7 Nov, docs/handoff/arch-search-results.md).

usage: python3 scripts/midsub/final_tables.py   (run from the repository root after the holdout and ablation arms are scored)

Blocks, each with the same statistics as docs/report/tools/win_loss_tie.py (its `compare`, imported unchanged: seeded paired
bootstrap, Holm at 0.05 per arm and metric over the comparators, a win only when the Holm-level interval excludes zero):
  search   30 dev orders t1dev-000..029, every arm on one commit (data/eval/dev_runs/sarvam_final)
  holdout  20 dev orders t1dev-030..049, touched once (data/eval/dev_runs/sarvam_holdout)
  pooled   all 50 dev orders (search + holdout; same src tree), the only block where the factor metrics have enough orders
  ablate   the winner rerun against each ablation on the 30 search orders (data/eval/dev_runs/sarvam_ablate)
  blind    the 80 sealed blind orders, opened once (data/eval/dev_runs/sarvam_blind, one gated scoring call over all nine arms), with the
           registered hypotheses H-A1 to H-A5 of pre-registration 1.5 and the declared sensitivity analyses (errored records kept, 1.4; D7)
Quality metrics decide. Cost (tokens, store calls, seconds) is a separate table judged only against B4 and B5, the baselines of
comparable capability; against B0-B3 and B6 it is shown, not counted. Every numeric column the scorer writes gets a mean.
Writes docs/results/search/final_report/{means_<block>.csv, wlt_<block>.csv, hypotheses_blind.json, summary.md} and
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

RUNS = Path(__import__("os").environ.get("VS_RUNS", ROOT / "data/eval/dev_runs"))  # VS_RUNS: the worktree that holds the runs
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
    # one scorer call per arm writes scores/<arm>/per_case_agreed.csv; the blind slice's single gated call writes scores/per_case_agreed.csv
    for f in sorted((RUNS / block / "scores").glob("per_case_agreed.csv")) + sorted((RUNS / block / "scores").glob("*/per_case_agreed.csv")):
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
    blind = rows_of("sarvam_blind")
    if blind:
        md += blind_block(blind, tex_rows, cost_cells)
    else:
        md += ["## blind: not scored yet", ""]
    md += variance_block()
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    write_tex(tex_rows, abl_rows, cost_cells)
    print("\n".join(md))


# Pre-registration 1.5: cells declared structural on dev before the blind slice was opened (H-A1 excepts exactly these)
STRUCTURAL = {("unfinished_factor_share", "b4"), ("unfinished_factor_share", "b5"), ("confident_wrong_rate", "b4"), ("coverage", "b6")}
D7_SET_ASIDE = {"full": "t1-000", WIN: "t1-002"}  # pre-registration D7: the two cases rerun after a local SQLite error at start-up


def _cell(cells, arm, base, metric):
    return next((c for c in cells if c["arm"] == arm and c["baseline"] == base and c["metric"] == metric), None)


def _show(c):
    if c is None:
        return "not computed"
    if c["outcome"] in ("undefined",):
        return "undefined"
    s = f"{c['outcome']} (diff {c['diff']:+.3f}"
    if "lo" in c:
        s += f", interval {c['lo']:+.3f} to {c['hi']:+.3f}"
    return s + f", n={c['n']})"


def hypotheses(rows, tag):
    """H-A1..H-A5 of pre-registration 1.5, exactly as registered; returns (markdown lines, verdict dict)."""
    by = wlt.answered(rows)
    if WIN not in by:
        return [f"c1457 has no answered case ({tag})"], {}
    bases = [b for b in BASES if b in by]
    metrics = [m for m in wlt.DECIDING if m in rows[0]]
    q = wlt.compare(by, [WIN], bases, metrics)
    out, v = [], {}
    # H-A1: no loss against B0-B6 on any quality metric outside the four structural cells
    bad = [c for c in q if c["outcome"] == "loss" and (c["metric"], c["baseline"]) not in STRUCTURAL]
    struct = [c for c in q if (c["metric"], c["baseline"]) in STRUCTURAL]
    v["H-A1"] = "supported" if len(bases) == 7 and not bad else "falsified"
    out.append(f"- **H-A1** ({v['H-A1']}): losses outside the structural cells: "
               + ("; ".join(f"{wlt.DECIDING[c['metric']][0]} vs {c['baseline'].upper()} {_show(c)}" for c in bad) or "none")
               + ". Structural cells as found: " + "; ".join(f"{wlt.DECIDING[c['metric']][0]} vs {c['baseline'].upper()} {c['outcome']}" for c in struct)
               + (f". Baselines present: {', '.join(b.upper() for b in bases)}" if len(bases) < 7 else "") + ".")
    # H-A2: beats Full on objection recall and answerable coverage (one comparator, Holm level 0.05)
    h2 = wlt.compare(by, [WIN], ["full"], ["objection_recall", "answerable_coverage"]) if "full" in by else []
    ok = len(h2) == 2 and all(c["outcome"] == "win" for c in h2)
    v["H-A2"] = "supported" if ok else "falsified"
    out.append(f"- **H-A2** ({v['H-A2']}): " + "; ".join(f"{wlt.DECIDING[c['metric']][0]} vs Full {_show(c)}" for c in h2))
    # H-A3: beats B4 and B5 on citation precision and fabricated-citation rate (cells of the B0-B6 family)
    h3 = [(m, b, _cell(q, WIN, b, m)) for m in ("citation_precision", "fabricated_citation_rate") for b in ("b4", "b5")]
    v["H-A3"] = "supported" if all(c and c["outcome"] == "win" for _, _, c in h3) else "falsified"
    out.append(f"- **H-A3** ({v['H-A3']}): " + "; ".join(f"{wlt.DECIDING[m][0]} vs {b.upper()} {_show(c)}" for m, b, c in h3))
    # H-A4: M6 not a loss against any of B0-B6
    h4 = [(b, _cell(q, WIN, b, "unsupported_fact_rate")) for b in BASES]
    v["H-A4"] = "falsified" if any(c and c["outcome"] == "loss" for _, c in h4) or len(bases) < 7 else "supported"
    out.append(f"- **H-A4** ({v['H-A4']}): " + "; ".join(f"M6 vs {b.upper()} {_show(c)}" for b, c in h4))
    # H-A5: fewer store calls than B4 (cost family: B4 and B5)
    COSTM = {"store_calls": ("Store calls", False)}
    wlt.DECIDING.update(COSTM)
    h5 = wlt.compare(by, [WIN], [b for b in ("b4", "b5") if b in by], ["store_calls"])
    wlt.DECIDING.pop("store_calls")
    c = _cell(h5, WIN, "b4", "store_calls")
    v["H-A5"] = "supported" if c and c["outcome"] == "win" else "falsified"
    out.append(f"- **H-A5** ({v['H-A5']}): store calls vs B4 {_show(c)}"
               + (f" (means {c['arm_mean']:.0f} against {c['base_mean']:.0f})" if c and "arm_mean" in c else ""))
    return out, v


def blind_block(rows, tex_rows, cost_cells):
    md = []
    errs = Counter(r["system"] for r in rows if int(float(r.get("n_errors") or 0)) > 0)
    n = len({r["case_id"] for r in rows})
    means(rows, "blind")
    cells, arms, comps = run_wlt(rows, [WIN, "full"], BASES, "blind")
    md += [f"## blind ({n} orders, opened once): quality, against B0-B6", "",
           "Errored records per system (left out of every paired comparison, as in win_loss_tie.py): "
           + (", ".join(f"{name(s)} {k}" for s, k in sorted(errs.items())) or "none") + ".", "",
           "| arm | " + " | ".join(b.upper() for b in comps) + " | total W/T/L (+too few, undefined) | losses |",
           "|---|" + "---|" * (len(comps) + 2)]
    for a in arms:
        t = tally(cells, a)
        md.append(f"| {name(a)} | " + " | ".join(f"{tally(cells, a, b)['win']}/{tally(cells, a, b)['tie']}/{tally(cells, a, b)['loss']}" for b in comps)
                  + f" | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) | " + ("; ".join(losses(cells, a)) or "none") + " |")
        tex_rows.append(("blind", name(a), [tally(cells, a, b) for b in comps], t))
    cc, _, _ = run_wlt(rows, [WIN, "full"], ["b4", "b5"], "cost_blind", metrics=list(COST), extra=COST)
    cost_cells += [dict(c, block="blind") for c in cc]
    md += ["", "Cost against B4 and B5 (lower is better):", "", "| arm | metric | vs | arm mean | baseline mean | outcome |", "|---|---|---|---|---|---|"]
    md += [f"| {name(c['arm'])} | {COST[c['metric']][0]} | {c['baseline'].upper()} | {c.get('arm_mean', float('nan')):.0f} | "
           f"{c.get('base_mean', float('nan')):.0f} | {c['outcome']} |" for c in cc]
    h = wlt.compare(wlt.answered(rows), [WIN], ["full"], [m for m in wlt.DECIDING if m in rows[0]]) if "full" in {r["system"] for r in rows} else []
    wlt.write_csv(OUT / "wlt_blind_c1457_vs_full.csv", h)
    t = tally(h, WIN)
    md += ["", f"c1457 against Full, head to head on the blind slice: {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}); "
           f"better on {', '.join(wlt.DECIDING[c['metric']][0] for c in h if c['outcome'] == 'win') or '-'}; "
           f"worse on {', '.join(wlt.DECIDING[c['metric']][0] for c in h if c['outcome'] == 'loss') or '-'}.", ""]
    lines, v = hypotheses(rows, "primary")
    md += ["### Registered hypotheses H-A1 to H-A5 (pre-registration 1.5), primary analysis", ""] + lines + [""]
    # sensitivity 1 (pre-registration 1.4): errored records kept as scored instead of left out
    kept = [dict(r, n_errors="0") for r in rows]
    lines1, v1 = hypotheses(kept, "errors kept")
    # sensitivity 2 (D7): the two rerun cases dropped for the arm that was rerun (the original degraded records were errored, so they
    # would be left out of every paired comparison; dropping the rerun gives the same 79 paired cases)
    d7 = [r for r in rows if D7_SET_ASIDE.get(r["system"]) != r["case_id"]]
    lines2, v2 = hypotheses(d7, "D7")
    md += ["### Declared sensitivity analyses (add no test, cannot change a verdict)", "",
           "| hypothesis | primary | errored records kept as scored (1.4) | D7: rerun cases dropped, 79 paired |", "|---|---|---|---|"]
    for k in v:
        md.append(f"| {k} | {v[k]} | {v1.get(k, '-')} | {v2.get(k, '-')} |")
    md += ["", "Errored records kept as scored:", ""] + lines1 + ["", "D7, 79 paired cases:", ""] + lines2 + [""]
    # sensitivity 3 (pre-registration section 0 and 3, run under D11): the same saved outputs scored against the rule-only gold
    v3 = {}
    rule_csv = RUNS / "sarvam_blind" / "scores_rule" / "per_case_rule.csv"
    if rule_csv.exists():
        rule = list(csv.DictReader(open(rule_csv)))
        for r in rule:
            r["system"] = r["system"].lower()
        lines3, v3 = hypotheses(rule, "rule-only gold")
        means(rule, "blind_rule")
        rc, _, _ = run_wlt(rule, [WIN, "full"], BASES, "blind_rule")
        md += ["### Rule-only gold (D11: the declared label-source sensitivity, run once on the same saved outputs)", "",
               "| arm | " + " | ".join(b.upper() for b in BASES) + " | total W/T/L (+too few, undefined) | losses |", "|---|" + "---|" * (len(BASES) + 2)]
        for a in (WIN, "full"):
            t = tally(rc, a)
            md.append(f"| {name(a)} | " + " | ".join(f"{tally(rc, a, b)['win']}/{tally(rc, a, b)['tie']}/{tally(rc, a, b)['loss']}" for b in BASES)
                      + f" | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) | " + ("; ".join(losses(rc, a)) or "none") + " |")
        # a cell is robust to the label source when its outcome (sign and Holm decision) is the same on both golds (pre-registration 3)
        agreed_cells = {(c["arm"], c["baseline"], c["metric"]): c["outcome"] for c in cells}
        diff = [(k, agreed_cells[k], c["outcome"]) for c in rc for k in [(c["arm"], c["baseline"], c["metric"])] if k in agreed_cells and agreed_cells[k] != c["outcome"]]
        md += ["", f"Cells whose outcome differs between the golds ({len(diff)} of {len(rc)}): "
               + ("; ".join(f"{name(a)} vs {b.upper()} {wlt.DECIDING[m][0]}: agreed {x}, rule {y}" for (a, b, m), x, y in diff) or "none") + ".", "",
               "Hypotheses on the rule-only gold:", ""] + lines3 + [""]
    else:
        md += ["Not run on the blind slice: the rule-only gold sensitivity (the gated opening is one scoring call, on the agreed gold).", ""]
    md[md.index("| hypothesis | primary | errored records kept as scored (1.4) | D7: rerun cases dropped, 79 paired |")] = (
        "| hypothesis | primary | errored records kept as scored (1.4) | D7: rerun cases dropped, 79 paired | rule-only gold (D11) | robust to the label source |")
    md[md.index("|---|---|---|---|")] = "|---|---|---|---|---|---|"
    for k in v:
        i = next(j for j, line in enumerate(md) if line.startswith(f"| {k} | {v[k]} | {v1.get(k, '-')} | {v2.get(k, '-')} |"))
        md[i] += f" {v3.get(k, 'not run')} | {('yes' if v3.get(k) == v[k] else 'no') if v3 else '-'} |"
    (OUT / "hypotheses_blind.json").write_text(__import__("json").dumps({"primary": v, "errors_kept": v1, "d7_79": v2, "rule_gold_d11": v3}, indent=1) + "\n")
    return md


def variance_block():
    """Pre-registration D12 (exploratory): the nine arms run twice more on the 30 search orders, frozen code, Sarvam cache off.
    Per arm and metric: the mean of each run, the mean absolute per-case difference, the mean per-case SD across the two runs, the share of
    cases whose pass (factor recall >= 0.5) flips; c1457's W/T/L against B0-B6 in each run; and each arm against itself (run 1 vs run 2),
    where any 'win' or 'loss' is a false alarm of the decision rule."""
    r1, r2 = rows_of("sarvam_var1"), rows_of("sarvam_var2")
    if not (r1 and r2):
        return ["## Run-to-run spread (D12): not scored yet", ""]
    md = ["## Run-to-run spread (D12, exploratory): two fresh runs, cache off, 30 search orders, frozen code", ""]
    a1, a2 = wlt.answered(r1), wlt.answered(r2)
    arms = [a for a in [WIN, "full", *BASES] if a in a1 and a in a2]
    metrics = [m for m in wlt.DECIDING if m in r1[0] and m in r2[0]]
    out = []
    for a in arms:
        shared = sorted(set(a1[a]) & set(a2[a]))
        for m in metrics:
            pairs = [(wlt.value(a1[a][c], m), wlt.value(a2[a][c], m)) for c in shared]
            pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
            if len(pairs) < 2:
                continue
            d = [abs(x - y) for x, y in pairs]
            out.append({"arm": a, "metric": m, "n": len(pairs), "mean_run1": st.mean(x for x, _ in pairs), "mean_run2": st.mean(y for _, y in pairs),
                        "mean_abs_case_diff": st.mean(d), "mean_case_sd": st.mean(x / 2 ** 0.5 for x in d), "share_cases_changed": sum(x > 1e-9 for x in d) / len(d)})
        flips = [c for c in shared if str(a1[a][c].get("passed")) in ("True", "False", "1", "0") and str(a1[a][c].get("passed")) != str(a2[a][c].get("passed"))]
        out.append({"arm": a, "metric": "pass_flip_share", "n": len(shared), "share_cases_changed": len(flips) / len(shared) if shared else float("nan")})
    with open(OUT / "variance_d12.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["arm", "metric", "n", "mean_run1", "mean_run2", "mean_abs_case_diff", "mean_case_sd", "share_cases_changed"])
        w.writeheader()
        w.writerows(out)
    md += ["| arm | metric | n | run 1 | run 2 | mean abs. per-case diff | cases changed |", "|---|---|---|---|---|---|---|"]
    for o in out:
        if o["metric"] == "pass_flip_share":
            md.append(f"| {name(o['arm'])} | pass flips (factor recall >= 0.5) | {o['n']} | | | | {o['share_cases_changed']:.0%} |")
        elif o["metric"] in ("factor_recall", "unsupported_fact_rate", "objection_recall", "answerable_coverage", "citation_precision", "coverage"):
            md.append(f"| {name(o['arm'])} | {wlt.DECIDING[o['metric']][0]} | {o['n']} | {o['mean_run1']:.3f} | {o['mean_run2']:.3f} | {o['mean_abs_case_diff']:.3f} | {o['share_cases_changed']:.0%} |")
    md += ["", "(every metric: docs/results/search/final_report/variance_d12.csv)", ""]
    for tag, rows in (("run 1", r1), ("run 2", r2)):
        cells, _, comps = run_wlt(rows, [WIN, "full"], BASES, f"var_{tag.replace(' ', '')}")
        for a in (WIN, "full"):
            t = tally(cells, a)
            md.append(f"- {tag}, {name(a)} against B0-B6: {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}); losses: " + ("; ".join(losses(cells, a)) or "none"))
    # each arm against itself: run 2 relabelled as a comparator
    both = r1 + [dict(r, system=r["system"] + "@2") for r in r2]
    by = wlt.answered(both)
    self_cells = []
    for a in arms:
        self_cells += wlt.compare(by, [a], [a + "@2"], metrics)
    wlt.write_csv(OUT / "wlt_var_self.csv", self_cells)
    alarms = [c for c in self_cells if c["outcome"] in ("win", "loss")]
    md += ["", f"Each arm against its own rerun ({len(self_cells)} cells): {len(alarms)} decided as a win or loss "
           + ("(" + "; ".join(f"{name(c['arm'])} {wlt.DECIDING[c['metric']][0]} {c['outcome']}" for c in alarms) + ")" if alarms else "(none)") + ".", ""]
    return md


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
          r"Search: 30 dev orders, every arm on one commit; holdout: 20 further dev orders, touched once; pooled: all 50; blind: the 80 sealed orders, opened once. "
          r"c1457 is Full with X1, X4, X5 and X7. Cost is in Table~\ref{tab:arch_cost}.}", r"\label{tab:arch_wlt}", r"\end{table*}"]
    (GEN / "arch_wlt.tex").write_text(fit("\n".join(L) + "\n"))
    # one column wide: the loss list wraps in its own column instead of the table being scaled past the column
    L = [r"\begin{table}[!t]", r"\centering\small", r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.42\linewidth}c>{\raggedright\arraybackslash}p{0.36\linewidth}@{}}",
         r"\toprule", r"Ablation & W/T/L & Winner loses on \\", r"\midrule"]
    for b, t, ls in abl_rows:
        L.append(f"{esc(b)} & {t['win']}/{t['tie']}/{t['loss']} & {esc(', '.join(ls) or 'none')} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\caption{The winner c1457 against each ablation on the 30 search orders (wins, ties, "
          r"losses of the winner; same statistics as Table~\ref{tab:arch_wlt}).}", r"\label{tab:arch_ablate}", r"\end{table}"]
    (GEN / "arch_ablate.tex").write_text("\n".join(L) + "\n")
    L = [r"\begin{table}[!t]", r"\centering\small", r"\begin{adjustbox}{max width=\linewidth}", r"\begin{tabular}{@{}llllrrl@{}}", r"\toprule",
         r"Block & Arm & Metric & vs & Arm & Base & Outcome \\", r"\midrule"]
    for c in cost_cells:
        L.append(f"{c['block']} & {esc(name(c['arm']))} & {COST[c['metric']][0]} & {c['baseline'].upper()} & "
                 f"{c.get('arm_mean', 0):.0f} & {c.get('base_mean', 0):.0f} & {c['outcome']} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}", r"\caption{Cost per order against B4 and B5, the baselines of comparable capability "
          r"(lower is better). Against the one-call baselines B0--B3 and the template B6 cost is shown in the means tables, not counted.}",
          r"\label{tab:arch_cost}", r"\end{table}"]
    (GEN / "arch_cost.tex").write_text(fit("\n".join(L) + "\n"))


if __name__ == "__main__":
    main()
