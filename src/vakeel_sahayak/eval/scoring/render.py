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
def _claims_cases(s: dict[str, Any]) -> str:
    """`k / n`: cases where the system made at least one factual claim (the cases M6 is averaged over) of all cases it was scored on."""
    u = s["metrics"]["unsupported_fact_rate"]
    return f"{u.get('n_claims_cases', u['n'])} / {u.get('n_cases', s['n_cases'])}"


def table_main(res: dict[str, Any]) -> Table:
    """Table 1 (plan 6.1): the headline metrics per system."""
    meta, systems = res["meta"], res["systems"]
    rights = (res.get("rights") or {}).get("arms") or {}
    cols = ["System", "Evaluated object", "n / runs", "Factor recall (M1)", "Precision, lenient (M2)", "F1 (M3)", "Unsupported-fact rate (M6)",
            "Cases with claims (M6)", "Claims/case", "Unsupported sentences/case", "Answerable-factor coverage",
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
                     _claims_cases(s), cell(m["n_claims"], digits=1, show_n=False), cell(m["unsupported_fact_count"], digits=2, show_n=False),
                     cell(m["answerable_coverage"]),
                     cell(m["recall_at_10"]) + f" [{cov}]", cell(m["objection_recall"]), pk, cell(m["tokens"], digits=0, show_n=False)])
    notes = ["Cases with no claims are excluded from M6 and counted in coverage: M6 is the mean over the cases with claims (k / n above); the unsupported-sentence count per case "
             "and the share of answerable factors with a supported argument are shown beside it, so a system that says nothing cannot win on M6.",
             f"Label source: {meta['gold_source']} (hash {str(meta['gold_sha256'])[:12]}). n beside a metric is the number of orders where it is defined: M1 needs an agreed answerable "
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
             "pooled factor hits: cluster bootstrap over cases. n is the number of paired cases; for the unsupported-fact rate only cases where both systems made claims are paired. Holm only inside the registered primary families (plan 5.3), on this gold; everything else is exploratory."]
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


def table_label_sensitivity(res: dict[str, Any]) -> list[Table]:
    """M5 (plan 4.1, 5.9): M1 to M4 per system under each label source, whether the system order survives, and the kappa between labelers per factor."""
    ls = res.get("label_sensitivity")
    if not ls or not ls.get("sources"):
        return []
    from vakeel_sahayak.eval.label_sensitivity import METRIC_LABELS, METRICS

    cols = ["System", "Label source", *[METRIC_LABELS[m] for m in METRICS]]
    rows = []
    systems = sorted({s for e in ls["sources"].values() for s in e["systems"]})
    for name in order_systems(systems, res["meta"]["reference"]):
        for entry in ls["sources"].values():
            cells = entry["systems"].get(name)
            if cells:
                rows.append([name, entry["label"], *[cell(cells[m]) for m in METRICS]])
    notes = []
    for source, order in ls["ranking"].items():
        same = ls["sources"][source].get("same_ranking_as_agreed")
        notes.append(f"{source}: systems by M1, best first: {' > '.join(order) or 'none'}" + ("" if same is None else " (same order as agreed)" if same else " (order differs from agreed)"))
    missing = [s for s, ok in ls["available"].items() if not ok]
    if missing:
        notes.append("Not available in this gold: " + ", ".join(missing) + ".")
    notes.append(ls["note"])
    tables = [Table("table_label_sensitivity", "Label-source sensitivity of M1 to M4 (M5, preliminary)", caption_prefix(res) + " Same outputs, different label sources; mean [95% CI] with n.", cols, rows, notes)]
    krows = []
    for name, k in ls.get("kappa", {}).items():
        for lab, v in k["per_label"].items():
            ci = "n/a" if not v["ci95"] else f"[{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}]"
            krows.append([name, lab, str(v["n_a"]), str(v["n_b"]), str(v["both"]), fmt(v["kappa"], 2), ci])
        krows.append([name, "all labels pooled", str(k["n_labels_a"]), str(k["n_labels_b"]), "", fmt(k["pooled_kappa"], 2), f"n={k['n_orders']} orders"])
    if krows:
        tables.append(Table("table_label_kappa", "Agreement between label sources, per factor (M5, preliminary)", caption_prefix(res),
                            ["Pair", "Label", "n first", "n second", "both", "Cohen kappa", "95% CI"], krows,
                            ["Per-label binary kappa over the scored orders; pooled kappa treats every (order, label) cell as one item."]))
    return tables


def _checker_note(res: dict[str, Any]) -> str:
    ck = res["meta"].get("checker")
    if not ck:
        return "No support checker was needed or run."
    return f"Support checker: {ck['name']}" + (" (offline stand-in: a deterministic lexical checker, a plumbing check, not a validated judge)" if ck["stand_in"] else "") + "."


def _pending_notes(res: dict[str, Any], keys: list[str]) -> list[str]:
    return [f"{k}: not computed, {res['meta']['pending'][k]}" for k in keys if k in res["meta"]["pending"]]


def table_citations(res: dict[str, Any]) -> Table:
    """M9, M13, M15, M16, M17 per system (plan 4.2, 4.3): fabricated citations, authority quality, good law, ALCE-style citation precision and recall, removal faithfulness."""
    keys = ["fabricated_citation_rate", "authority_reasoning_share", "authority_sc_share", "authority_before_share", "good_law_violation_rate", "known_treatment_share",
            "citation_precision", "citation_recall", "citation_removal_change"]
    cols = ["System", "Fabricated citations (M9)", "Court reasoning (M13)", "Supreme Court (M13)", "Dated before order (M13)", "Good-law violations (M15)", "Known treatment (M15)",
            "Citation precision (M16)", "Citation recall (M16)", "Claims changed by removal (M17)"]
    rows = []
    for name in order_systems(list(res["systems"]), res["meta"]["reference"]):
        m = res["systems"][name]["metrics"]
        rows.append([name, *[cell(m[k], pending=k in res["meta"]["pending"]) if k in m else "n/a" for k in keys]])
    notes = [_checker_note(res),
             "M9: share of citations whose paragraph is not in the index or whose quotation is not in it (whitespace removed). M15: overruled precedents cited without a warning; 'known treatment' is "
             "the share of cited precedents with at least one labelled citing treatment (unknown is not good). M16 precision: cited paragraph supports the citing sentence; recall: authority-claim "
             "sentences with a supported citation. M17 needs the `m17_removal` arm (a redraft without the cited paragraph) and is a lower bound; n/a (n=0) means the arm was not run.",
             "A system that cites nothing has no defined value (n counts the orders with at least one citation)."]
    return Table("table_citations", "Citations and authority quality (preliminary)", caption_prefix(res), cols, rows, [*notes, *_pending_notes(res, keys)])


def table_abstention(res: dict[str, Any]) -> Table:
    """M33 (coverage-risk curve and AURC), M35 (confident-wrong) and M18 (stopping quality) per system (plan 4.6, 4.3)."""
    cols = ["System", "Can decline", "Claims", "Coverage at the cut (M33)", "Risk at the cut (M33)", "Coverage, all emitted", "Risk, all emitted (M6)", "AURC [95% CI]",
            "Confident-wrong (M35)", "Over-search (M18)", "Stopped with a slot unfilled (M18)"]
    rows = []
    for name in order_systems(list(res["systems"]), res["meta"]["reference"]):
        s = res["systems"][name]
        c = s.get("curve") or {"can_decline": False, "n_claims": 0, "aurc": None, "operating": None, "one_point": None}
        op, one = c.get("operating") or {}, c.get("one_point") or {}
        aurc = "one point (cannot decline)" if not c["can_decline"] and c["n_claims"] else fmt(c["aurc"])
        if c.get("aurc_ci"):
            aurc += f" [{c['aurc_ci'][0]:.3f}, {c['aurc_ci'][1]:.3f}]"
        m = s["metrics"]
        rows.append([name, "yes" if c["can_decline"] else "no", str(c["n_claims"]), fmt(op.get("coverage")), fmt(op.get("risk")), fmt(one.get("coverage")), fmt(one.get("risk")), aurc,
                     cell(m.get("confident_wrong_rate") or {}, pending="confident_wrong_rate" in res["meta"]["pending"]), cell(m.get("over_search_rate") or {}), cell(m.get("unfinished_factor_share") or {})])
    notes = [_checker_note(res),
             "Claims are the factual sentences of the brief. A claim is emitted at threshold tau when its ground passed the gate and its support score is at least tau; coverage is emitted claims over "
             "all claims, risk the share of emitted claims below the unsupported-fact cut. 'At the cut' keeps the claims the checker itself supports; 'all emitted' keeps every claim the gate emitted. "
             "Because risk is defined with the same score, it is 0 at tau = cut by construction; what the curve shows is how much coverage is lost to reach zero risk.",
             "M35: emitted claims that are unfaithful (not supported by the facts given) and uncorroborated (not supported by the rest of the order). It needs the order parts "
             "(`data/interim/t1_work/parts.jsonl`). M18 is event-based: over-search is the share of retrieval calls after the first round where no required slot was missing or weak; "
             "the replay to the 16-call budget for 'stopped too early' needs a re-run and is not computed.", *_pending_notes(res, ["confident_wrong_rate"])]
    return Table("table_abstention", "Abstention, confident-wrong and stopping quality (preliminary)", caption_prefix(res), cols, rows, notes)


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
    p = directory / "fig_coverage_risk.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["system", "tau", "coverage", "risk"])
        for name, s in res["systems"].items():
            for tau, cov, risk in (s.get("curve") or {}).get("points") or []:
                w.writerow([name, tau, cov, risk])
    paths["fig_coverage_risk"] = p
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
        tables = [table_main(res), table_cost(res), table_paired(res), table_holm(res), table_coverage(res), table_citations(res), table_abstention(res)]
        rt = table_rights(res)
        if rt:
            tables.append(rt)
        tables += table_label_sensitivity(res)
        for t in tables:
            written["tables"] += [str(p) for p in write_table(t, tdir)]
        if g == main:
            written["figures"] += [str(p) for p in render_figures(res, dest / "figures")]
    sweep = base / "sweep.json"
    if sweep.is_file():
        for t in table_sweep(json.loads(sweep.read_text(encoding="utf-8"))):
            written["tables"] += [str(p) for p in write_table(t, dest / "tables")]
    return written
