"""Tables (Markdown, LaTeX booktabs fragments, CSV) and figures (PDF and PNG when matplotlib is installed) from the JSON written by `pipeline`.

Table cells are `mean [lo, hi]` (95% bootstrap interval of the case-level mean; paired rows: of the paired difference) with n beside; a metric whose scorer is
a stub prints `pending`; one that is undefined for every case prints `n/a (n=0)`. Captions say what the numbers are: a dev slice is a "preliminary dev
result", offline stand-in models are named as such, and the label source and its coverage are always stated (plan 5.5, 6.0).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.scoring.engine import FAMILIES, METRICS, MIN_SLICE_N

PENDING = "pending"
_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


@dataclass
class Table:
    """One table: a name (file stem), a title, a caption, column headers, string rows and footnotes."""

    name: str
    title: str
    caption: str
    columns: list[str]
    rows: list[list[str]]
    notes: list[str] = field(default_factory=list)


def tex_escape(s: str) -> str:
    return "".join(_TEX.get(ch, ch) for ch in str(s))


def to_markdown(t: Table) -> str:
    lines = [f"### {t.title}", "", f"*{t.caption}*", "", "| " + " | ".join(t.columns) + " |", "|" + "|".join("---" for _ in t.columns) + "|"]
    lines += ["| " + " | ".join(c.replace("|", "/") for c in r) + " |" for r in t.rows]
    lines += ["", *[f"- {n}" for n in t.notes]] if t.notes else []
    return "\n".join(lines) + "\n"


def to_latex(t: Table) -> str:
    spec = "l" + "r" * (len(t.columns) - 1)
    out = ["% booktabs fragment: \\usepackage{booktabs} in the preamble", "\\begin{table}[t]", "\\centering", "\\small",
           f"\\caption{{{tex_escape(t.caption)}}}", f"\\label{{tab:{t.name}}}", f"\\begin{{tabular}}{{{spec}}}", "\\toprule",
           " & ".join(tex_escape(c) for c in t.columns) + " \\\\", "\\midrule"]
    out += [" & ".join(tex_escape(c) for c in r) + " \\\\" for r in t.rows]
    out += ["\\bottomrule", "\\end{tabular}"]
    out += [f"% note: {n}" for n in t.notes]
    out.append("\\end{table}")
    return "\n".join(out) + "\n"


def to_csv(t: Table, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(t.columns)
        w.writerows(t.rows)


def write_table(t: Table, directory: Path) -> list[Path]:
    """Write `<name>.md`, `.tex` and `.csv` into the directory."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{t.name}.md", directory / f"{t.name}.tex", directory / f"{t.name}.csv"]
    paths[0].write_text(to_markdown(t), encoding="utf-8")
    paths[1].write_text(to_latex(t), encoding="utf-8")
    to_csv(t, paths[2])
    return paths


# ---------------------------------------------------------------------------------------------------------------- cells
def fmt(x: float | None, digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def cell(summary: dict[str, Any], *, pending: bool = False, digits: int = 3, show_n: bool = True) -> str:
    """`mean [lo, hi] n=k`; `pending` when the scorer is a stub; `n/a (n=0)` when no case defines it."""
    if pending:
        return PENDING
    if not summary or not summary.get("n"):
        return "n/a (n=0)"
    s = f"{summary['mean']:.{digits}f} [{summary['lo']:.{digits}f}, {summary['hi']:.{digits}f}]"
    return s + (f" n={summary['n']}" if show_n else "")


def order_systems(names: list[str], reference: str) -> list[str]:
    """Reference first, then baselines (b0, b1, ...), then the rest, each group in natural order."""
    def key(s: str) -> tuple[int, str]:
        low = s.lower()
        return (0 if low == reference.lower() else 1 if low.startswith("b") and low[1:2].isdigit() else 2, low)

    return sorted(names, key=key)


def caption_prefix(res: dict[str, Any]) -> str:
    meta = res["meta"]
    sl = meta["slice"]
    kind = {"dev": "Preliminary dev result", "open": "Open-slice result (exploratory until the blind slice is opened)", "blind": "Blind-slice result"}[sl]
    offline = "offline" in (meta.get("models_modes") or []) or any((s["manifest"].get("llm_backend") == "offline") for s in res["systems"].values())
    extra = " Offline stand-in models: the numbers test the plumbing and say nothing about hosted or fine-tuned models." if offline else ""
    return f"{kind}: {sl} slice ({meta['n_gold_cases']} orders; the n of each system is in the table), gold source {meta['gold_source']}.{extra}"


def _pending(res: dict[str, Any], metric: str) -> bool:
    return metric in res["meta"]["pending"]


# ---------------------------------------------------------------------------------------------------------------- tables
def table_main(res: dict[str, Any]) -> Table:
    """Table 1 (plan 6.1): the headline metrics per system."""
    meta, systems = res["meta"], res["systems"]
    rights = (res.get("rights") or {}).get("arms") or {}
    cols = ["System", "Evaluated object", "n / runs", "Factor recall (M1)", "Precision, lenient (M2)", "F1 (M3)", "Unsupported-fact rate (M6)",
            "Recall@10 G2 (M10) [coverage]", "Objection recall G4", "pass^k", "Tokens/case"]
    rows = []
    for name in order_systems(list(systems), meta["reference"]):
        s = systems[name]
        m = s["metrics"]
        g2 = s["g2"]
        cov = f"{g2['n_cases_with_gold']} of {s['n_cases']} orders with a resolved citation" + (f", {g2['resolved_share']:.0%} resolved" if g2["resolved_share"] is not None else "")
        passed = s["pass"]
        pk = "n/a" if passed["pass_hat_k"] is None else f"pass^{passed['k']}={passed['pass_hat_k']:.2f} (n={passed['n']})"
        rows.append([name, str(s["manifest"].get("variant") or ""), f"{s['n_cases']} / {len(s['runs'])}", cell(m["factor_recall"]), cell(m["factor_precision_lenient"]),
                     cell(m["factor_f1"]), cell(m["unsupported_fact_rate"], pending=_pending(res, "unsupported_fact_rate")),
                     cell(m["recall_at_10"]) + f" [{cov}]", cell(m["objection_recall"]), pk, cell(m["tokens"], digits=0, show_n=False)])
    notes = [f"Label source: {meta['gold_source']} (hash {str(meta['gold_sha256'])[:12]}). n beside a metric is the number of orders where it is defined: M1 needs an agreed answerable "
             "factor, recall@10 a resolved court-cited precedent, objection recall an agreed objection. Runs are averaged within a case; the interval resamples cases.",
             f"pass^k bar: factor recall >= {meta['config']['pass_bar']} with no stage error (provisional; the bar is frozen in the pre-registration)."]
    if meta["pending"]:
        notes.append("pending: " + "; ".join(f"{k} waits for {v}" for k, v in meta["pending"].items()))
    if rights:
        notes.append("Rights Radar (T4) accuracy: " + ", ".join(f"{a} {v['accuracy']:.3f} [{v['lo']:.3f}, {v['hi']:.3f}] n={v['n']}" for a, v in rights.items()))
    low = [n for n, s in systems.items() if s["n_cases"] < MIN_SLICE_N]
    if low:
        notes.append(f"Systems scored on fewer than {MIN_SLICE_N} orders ({', '.join(low)}): too few for a claim (plan 5.5).")
    return Table("table1_main", "Table 1: main results (preliminary)", caption_prefix(res) + " Mean [95% bootstrap CI over cases].", cols, rows, notes)


def table_cost(res: dict[str, Any]) -> Table:
    """Table 9 (plan 6.9): tokens, store calls, time, cost."""
    cols = ["System", "Tokens/case [mean, p90]", "Store calls/case", "Seconds/case", "USD/case", "USD per passed case (M31)", "Backend"]
    rows = []
    for name in order_systems(list(res["systems"]), res["meta"]["reference"]):
        s = res["systems"][name]
        m = s["metrics"]
        rows.append([name, f"{fmt(m['tokens']['mean'], 0)}, {fmt(m['tokens'].get('p90'), 0)}", fmt(m["store_calls"]["mean"], 1), fmt(m["seconds"]["mean"], 1),
                     fmt(m["cost_usd"]["mean"], 4) if m["cost_usd"]["n"] else "n/a (no price)", fmt(s["cost_per_passed_case"], 4), str(s["manifest"].get("llm_backend"))])
    return Table("table9_cost", "Table 9: cost and latency (preliminary)", caption_prefix(res) + " USD is 0 on the offline stand-ins and priced on OpenAI only; Ada (Qwen) and Sarvam runs have no USD price.", cols, rows)


def table_paired(res: dict[str, Any]) -> Table:
    """Paired comparisons of the reference with every other system, with the Holm decision of the registered family."""
    cols = ["Comparison", "Metric", "n", "Difference [95% CI]", "p (test)", "d_z / odds ratio", "Family (Holm)"]
    rows = []
    ref = res["meta"]["reference"]
    for p in sorted(res["paired"], key=lambda r: (r["comparator"].lower(), r["metric"])):
        label = f"{p['reference']} minus {p['comparator']}"
        if p["status"] != "ok":
            rows.append([label, p["metric"], str(p["n"]), PENDING if p["status"] == "pending" else p["status"], "", "", ""])
            continue
        ci = f"{p['diff']:+.3f} [{p['lo']:+.3f}, {p['hi']:+.3f}]" if "lo" in p else f"{p['diff']:+.3f}"
        eff = fmt(p.get("dz"), 2) if "dz" in p else (fmt(p.get("odds_ratio"), 2) if p.get("odds_ratio") is not None else "inf" if p.get("b10") else "n/a")
        fam = "exploratory (uncorrected)" if p["family"] is None else f"{p['family']}: " + ("reject" if p["holm_reject"] else "not rejected")
        rows.append([label, p["metric"], str(p["n"]), ci, f"{p['p']:.4f} ({p['p_source']})", eff, fam])
    notes = [f"Difference is {ref} minus the comparator; for the unsupported-fact rate, tokens and store calls lower is better. Binary rows: exact McNemar on discordant pairs; "
             "pooled factor hits: cluster bootstrap over cases. Holm only inside the registered primary families (plan 5.3), on this gold; everything else is exploratory."]
    return Table("table_paired", "Paired comparisons with the reference (preliminary)", caption_prefix(res), cols, rows, notes)


def table_holm(res: dict[str, Any]) -> Table:
    """The registered primary families and what was run in each."""
    cols = ["Family", "Claims", "Registered tests (m)", "Comparator", "Metric", "Difference", "p", "Holm decision"]
    rows = []
    for name, fam in res["families"].items():
        for t in fam["tests"]:
            if t.get("reject") is not None:
                dec = ("reject" if t["reject"] else "not rejected") + ("" if t["sign_favours_reference"] else " (sign against reference)")
                rows.append([name, fam["claims"], str(fam["m_registered"]), t["comparator"], t["metric"], f"{t['diff']:+.3f}", f"{t['p']:.4f}", dec])
            else:
                rows.append([name, fam["claims"], str(fam["m_registered"]), t["comparator"], t["metric"], "", "", t.get("status", "not run")])
    notes = [f"Holm-Bonferroni with alpha {res['meta']['alpha']} and the registered family size m (a test not run counts as p = 1). Families: " +
             "; ".join(f"{k} = {','.join(v['comparators'])} on {','.join(v['metrics'])}" for k, v in FAMILIES.items())]
    return Table("table_holm", "Holm decisions by registered family (preliminary)", caption_prefix(res), cols, rows, notes)


def table_rights(res: dict[str, Any]) -> Table | None:
    r = res.get("rights")
    if not r or not r["arms"]:
        return None
    rules = sorted({rule for a in r["arms"].values() for rule in a["per_rule"]})
    cols = ["Arm", "n", "Accuracy [95% Wilson]", *[f"Accuracy: {x}" for x in rules], "False-ELIGIBLE", "CHECK rate"]
    rows = []
    for arm, a in r["arms"].items():
        fe = f"{a['false_eligible']} of {a['n']}" + (f" (upper 95% bound {a['false_eligible_upper_95']:.3f})" if a["false_eligible_upper_95"] is not None else "")
        rows.append([arm, str(a["n"]), f"{a['accuracy']:.3f} [{a['lo']:.3f}, {a['hi']:.3f}]", *[fmt(a["per_rule"].get(x, {}).get("accuracy")) for x in rules], fe, fmt(a["check_rate"])])
    notes = [f"McNemar {m['a']} vs {m['b']}: n={m['n']}, discordant {m['b10']}/{m['b01']}, p={m['p']:.4f}" for m in r["mcnemar"]]
    notes.append("T4 designed answers come from the bare-act rule text, not from the Radar. G7 on T1 has too few labelled orders to support a claim (plan 5.9).")
    return Table("table_rights", "Rights Radar accuracy on T4 (preliminary)", "Constructed T4 scenarios; designed answers derived independently of the Radar.", cols, rows, notes)


def table_coverage(res: dict[str, Any]) -> Table:
    """Label coverage beside every G-based number (plan 5.5 rule 5)."""
    cols = ["System", "Orders scored", "G1 and answerable (M1)", "G2 resolved (M10)", "Mean G2 gold size", "G4 agreed (objection)", "G7 labelled", "G2 retrieved from"]
    rows = []
    for name in order_systems(list(res["systems"]), res["meta"]["reference"]):
        s = res["systems"][name]
        rows.append([name, str(s["n_cases"]), str(s["metrics"]["factor_recall"]["n"]), str(s["g2"]["n_cases_with_gold"]), fmt(s["g2"]["mean_gold_size"], 2), str(s["g4_n"]),
                     str(s["g7_n"]), ", ".join(s["g2"]["retrieved_source"])])
    return Table("table_label_coverage", "Label coverage (preliminary)", caption_prefix(res), cols, rows,
                 ["Gold counts are orders with at least one label among the orders scored. G7 on T1 is nearly empty: the Rights Radar claim C30 rests on T4."])


def table_sweep(sweep: dict[str, Any]) -> list[Table]:
    """The gold-source sensitivity tables: system metrics on both golds with the delta, and robustness of each family test."""
    cap = f"Gold-source sensitivity sweep, {sweep['slice']} slice: the same outputs scored against the agreed (primary) and the rule-only (secondary) gold; no model call. Preliminary."
    rows = []
    for name, entry in sorted(sweep["systems"].items(), key=lambda kv: kv[0].lower()):
        for m, v in entry.items():
            if v["agreed"]["n"] == 0 and v["rule"]["n"] == 0:
                continue
            d = v["delta"]
            rows.append([name, METRICS[m][0], cell(v["agreed"]), cell(v["rule"]), "n/a" if d is None else f"{d:+.3f}"])
    t1 = Table("table_sweep_metrics", "Gold-source sweep: metrics on both golds", cap, ["System", "Metric", "Agreed gold (primary)", "Rule-only gold", "Delta (agreed minus rule)"], rows,
               [f"agreed gold hash {str(sweep['agreed']['gold_sha256'])[:12]}, rule gold hash {str(sweep['rule']['gold_sha256'])[:12]}; the case ids are identical, only labels differ."])
    rrows = []
    for t in sweep["family_tests"]:
        a, r = t["agreed"], t["rule"]
        rrows.append([t["family"], t["comparator"], METRICS[t["metric"]][0], f"{a['diff']:+.3f}", "reject" if a["reject"] else "not rejected", f"{r['diff']:+.3f}",
                      "reject" if r["reject"] else "not rejected", "robust" if t["robust"] else "differs (primary stays the headline)"])
    t2 = Table("table_sweep_robustness", "Gold-source sweep: robustness of the registered tests", cap,
               ["Family", "Comparator", "Metric", "Diff, agreed", "Holm, agreed", "Diff, rule", "Holm, rule", "Verdict"], rrows,
               ["Robust means the sign and the Holm decision are the same on both golds (plan 5.9). The sweep is one declared sensitivity analysis and adds no test to any family."])
    return [t1, t2]


# ---------------------------------------------------------------------------------------------------------------- figures
def figure_data(res: dict[str, Any], directory: Path) -> dict[str, Path]:
    """CSV behind each figure (always written)."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    p = directory / "fig2_frontier.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "tokens_per_case", "recall", "recall_lo", "recall_hi", "n"])
        for name, s in res["systems"].items():
            r = s["metrics"]["factor_recall"]
            if r["n"]:
                w.writerow([name, s["metrics"]["tokens"]["mean"], r["mean"], r["lo"], r["hi"], r["n"]])
    paths["fig2_frontier"] = p
    p = directory / "fig_per_factor.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "factor", "recall", "gold_items"])
        for name, s in res["systems"].items():
            for f, d in sorted(s["per_factor"].items()):
                w.writerow([name, f, d["hits"] / d["n"] if d["n"] else "", d["n"]])
    paths["fig_per_factor"] = p
    return paths


def render_figures(res: dict[str, Any], directory: Path) -> list[Path]:
    """Cost-quality scatter and per-factor bars as PDF and PNG; [] (after writing the CSVs) when matplotlib is not installed."""
    figure_data(res, directory)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    out: list[Path] = []
    title_tail = f"({res['meta']['slice']} slice, {res['meta']['gold_source']} gold; preliminary)"
    fig, ax = plt.subplots(figsize=(5, 3.6))
    for name in order_systems(list(res["systems"]), res["meta"]["reference"]):
        s = res["systems"][name]
        r = s["metrics"]["factor_recall"]
        if not r["n"]:
            continue
        x = max(s["metrics"]["tokens"]["mean"] or 0.0, 1.0)
        ax.errorbar([x], [r["mean"]], yerr=[[r["mean"] - r["lo"]], [r["hi"] - r["mean"]]], fmt="o", capsize=3, label=name)
    ax.set_xscale("log")
    ax.set_xlabel("tokens per case (log)")
    ax.set_ylabel("factor recall (M1)")
    ax.set_title("Cost against quality " + title_tail, fontsize=8)
    ax.legend(fontsize=7)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        p = directory / f"fig2_frontier.{ext}"
        fig.savefig(p)
        out.append(p)
    plt.close(fig)
    factors = sorted({f for s in res["systems"].values() for f in s["per_factor"]})
    if factors:
        names = order_systems(list(res["systems"]), res["meta"]["reference"])
        fig, ax = plt.subplots(figsize=(7, 3.6))
        width = 0.8 / max(len(names), 1)
        for i, name in enumerate(names):
            pf = res["systems"][name]["per_factor"]
            ax.bar([j + i * width for j in range(len(factors))], [(pf[f]["hits"] / pf[f]["n"]) if f in pf and pf[f]["n"] else 0.0 for f in factors], width, label=name)
        ax.set_xticks([j + 0.4 - width / 2 for j in range(len(factors))])
        ax.set_xticklabels(factors, rotation=40, ha="right", fontsize=7)
        ax.set_ylabel("recall of gold factors")
        ax.set_title("Per-factor recall " + title_tail, fontsize=8)
        ax.legend(fontsize=7)
        fig.tight_layout()
        for ext in ("pdf", "png"):
            p = directory / f"fig_per_factor.{ext}"
            fig.savefig(p)
            out.append(p)
        plt.close(fig)
    return out


def write_report(scores_dir: str, out: str | None = None, gold_source: str | None = None) -> dict[str, list[str]]:
    """Read `score_<gold>.json` (and `sweep.json`) from `scores_dir` and write `tables/` and `figures/` under `out` (default: `scores_dir`).

    The headline gold is `gold_source`, else `agreed`, else whatever exists; when both exist the other gold's tables go to `tables/<gold>/` and the sweep tables to `tables/`.
    """
    base = Path(scores_dir)
    dest = Path(out) if out else base
    available = {g: base / f"score_{g}.json" for g in ("agreed", "rule") if (base / f"score_{g}.json").is_file()}
    if not available:
        raise FileNotFoundError(f"no score_agreed.json or score_rule.json in {base}: run `score` first")
    main = gold_source or ("agreed" if "agreed" in available else next(iter(available)))
    if main not in available:
        raise FileNotFoundError(f"no score_{main}.json in {base}")
    written: dict[str, list[str]] = {"tables": [], "figures": []}
    for g, path in available.items():
        res = json.loads(path.read_text(encoding="utf-8"))
        tdir = dest / "tables" if g == main else dest / "tables" / g
        tables = [table_main(res), table_cost(res), table_paired(res), table_holm(res), table_coverage(res)]
        rt = table_rights(res)
        if rt:
            tables.append(rt)
        for t in tables:
            written["tables"] += [str(p) for p in write_table(t, tdir)]
        if g == main:
            written["figures"] += [str(p) for p in render_figures(res, dest / "figures")]
    sweep = base / "sweep.json"
    if sweep.is_file():
        for t in table_sweep(json.loads(sweep.read_text(encoding="utf-8"))):
            written["tables"] += [str(p) for p in write_table(t, dest / "tables")]
    return written
