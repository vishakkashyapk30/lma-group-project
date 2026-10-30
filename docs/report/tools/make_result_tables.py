"""Build the report's result tables and plots from the scorer's per_case CSVs (standard library only).

usage: python3 make_result_tables.py OUT_DIR family=CSV [family=CSV ...]   (a CSV may be a comma list of files; rows are concatenated)
Writes OUT_DIR/{main_<family>.tex, ablate_<family>.tex, fig_<family>.tex}. All numbers come from the CSVs; nothing is typed in.
"""
import csv, random, sys, statistics as st
from collections import defaultdict
from pathlib import Path

METRICS = [("objection_recall", "Obj. recall", True), ("answerable_coverage", "Ans. cov.", True), ("coverage", "Coverage", True),
           ("unsupported_fact_rate", "Unsupp. facts", False), ("fabricated_citation_rate", "Fabr. cit.", False),
           ("citation_precision", "Cit. prec.", True), ("factor_recall", "Factor rec.", True)]
BASE = ["b0", "b1", "b2", "b3", "b4", "b5", "b6"]


def load(paths):
    rows = []
    for p in paths.split(","):
        rows += list(csv.DictReader(open(p)))
    for r in rows:
        r["system"] = r["system"].lower()
    return rows


def fl(r, m):
    v = r.get(m, "")
    return float(v) if v not in ("", "nan", None) else None


def boot(vals, n=2000, seed=7):
    if len(vals) < 2:
        return (None, None)
    rnd = random.Random(seed)
    ms = sorted(sum(rnd.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return ms[int(0.025 * n)], ms[int(0.975 * n)]


def mean_ci(vals):
    if not vals:
        return None
    lo, hi = boot(vals)
    return sum(vals) / len(vals), lo, hi, len(vals)


def cell(x, d=2):
    if x is None:
        return "--"
    m, lo, hi, n = x
    return f"{m:.{d}f}" + (f" [{lo:.{d}f}, {hi:.{d}f}]" if lo is not None else "") + f" ({n})"


def per_system(rows):
    d = defaultdict(dict)
    for r in rows:
        d[r["system"]].setdefault(r["case_id"], r)
    return d


def esc(s):
    return s.replace("_", r"\_")


def main(out, specs):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        fam, paths = spec.split("=", 1)
        S = per_system(load(paths))
        ok = {s: {c for c, r in cs.items() if int(float(r.get("n_errors") or 0)) == 0} for s, cs in S.items()}
        ref = [s for s in ["full"] + BASE if s in S]
        common = set.intersection(*[ok[s] for s in ref if s in ok]) if ref else set()
        # table 1: each baseline beside Full on the cases both answered (arm / Full)
        full = S.get("full", {})
        KEY = [m for m in METRICS if m[0] in ("objection_recall", "answerable_coverage", "coverage", "unsupported_fact_rate", "citation_precision", "factor_recall")]
        lines = [r"\begin{table*}[t]", r"\centering\footnotesize", r"\begin{tabular}{@{}lr" + "r" * len(KEY) + r"@{}}", r"\toprule",
                 "Arm & Cases & " + " & ".join(m[1] + " (arm / Full)" for m in KEY) + r" \\", r"\midrule"]
        for s_ in [x for x in BASE if x in S]:
            cs = sorted(c for c in S[s_] if c in full and c in ok[s_] and c in ok.get("full", set()))
            cells = [str(len(cs))]
            for m, _, _ in KEY:
                pr = [(fl(S[s_][c], m), fl(full[c], m)) for c in cs]
                pr = [(a_, b_) for a_, b_ in pr if a_ is not None and b_ is not None]
                cells.append(f"{sum(a_ for a_, _ in pr) / len(pr):.2f} / {sum(b_ for _, b_ in pr) / len(pr):.2f} ({len(pr)})" if pr else "--")
            lines.append(esc(s_.upper()) + " & " + " & ".join(cells) + r" \\")
        lines += [r"\bottomrule", r"\end{tabular}",
                  r"\caption{" + f"Family {esc(fam)}: each baseline beside Full on the cases both answered without error. A cell is the arm's mean, then Full's mean on the same cases, over the cases where the metric is defined for both (the count in brackets). Unsupported facts: lower is better; the others: higher is better. A dash means the metric is undefined for the arm (for example, a baseline that cites no authority has no citation precision)." + r"}",
                  r"\label{tab:main_" + fam + "}", r"\end{table*}"]
        (out / f"main_{fam}.tex").write_text("\n".join(lines))
        # table 2: each other arm against Full on the cases both answered (paired difference of means)
        rows = [r"\begin{table*}[t]", r"\centering\footnotesize", r"\begin{tabular}{@{}lr" + "r" * len(METRICS) + r"@{}}", r"\toprule",
                "Arm & Cases & " + " & ".join("$\\Delta$ " + m[1] for m in METRICS) + r" \\", r"\midrule"]
        for s in sorted(S):
            if s == "full":
                continue
            cs = sorted(c for c in S[s] if c in full and c in ok[s] and c in ok.get("full", set()))
            cells = [str(len(cs))]
            for m, _, _ in METRICS:
                d = [fl(S[s][c], m) - fl(full[c], m) for c in cs if fl(S[s][c], m) is not None and fl(full[c], m) is not None]
                t = mean_ci(d)
                cells.append(f"{t[0]:+.2f}" + (f" [{t[1]:+.2f}, {t[2]:+.2f}]" if t[1] is not None else "") if t else "--")
            rows.append(esc(s.upper()) + " & " + " & ".join(cells) + r" \\")
        rows += [r"\bottomrule", r"\end{tabular}",
                 r"\caption{" + f"Family {esc(fam)}: each arm minus Full on the cases both answered (mean difference, 95\\% bootstrap interval). A positive difference favours the arm for the higher-is-better metrics and Full for unsupported facts and fabricated citations. Intervals that include zero are not resolved at this sample size." + r"}",
                 r"\label{tab:ablate_" + fam + "}", r"\end{table*}"]
        (out / f"ablate_{fam}.tex").write_text("\n".join(rows))
        # figures: per metric, mean over each arm's own answered cases with a 95% bootstrap interval; Full highlighted
        figm = [("objection_recall", "objection recall"), ("answerable_coverage", "answerable coverage"), ("unsupported_fact_rate", "unsupported-fact rate")]
        order = ["full"] + [x for x in BASE + sorted(k for k in S if k not in BASE and k != "full") if x in S][:8]
        order = [x for x in order if x in S][:9]
        xs = ",".join(esc(x.upper()) for x in order)
        body = [r"\begin{figure*}[t]", r"\centering", r"\begin{tikzpicture}"]
        for k, (m, lab) in enumerate(figm):
            body.append(r"\begin{axis}[vsplot, at={(" + f"{0.34 * k:.2f}" + r"\textwidth,0)}, width=0.33\textwidth, title={" + lab + r"}, ymin=0, ymax=1.1, symbolic x coords={" + xs + r"}, xtick={" + xs + r"}, xticklabel style={font=\scriptsize, rotate=45, anchor=east}, bar width=6pt, nodes near coords={}, enlarge x limits=0.08, error bars/y dir=both, error bars/y explicit, error bars/error bar style={line width=0.4pt, gray!70}]")
            for who, col in (("full", "cB"), ("rest", "cA")):
                coords = []
                for x in order:
                    if (x == "full") != (who == "full"):
                        continue
                    t = mean_ci([v for v in (fl(S[x][c], m) for c in sorted(ok[x])) if v is not None])
                    if t:
                        lo, hi = (t[1], t[2]) if t[1] is not None else (t[0], t[0])
                        coords.append(f"({esc(x.upper())},{t[0]:.3f}) += (0,{hi - t[0]:.3f}) -= (0,{t[0] - lo:.3f})")
                if coords:
                    body.append(r"\addplot[fill=" + col + r", draw=none, bar shift=0pt] coordinates {" + " ".join(coords) + "};")
            body.append(r"\end{axis}")
        body += [r"\end{tikzpicture}", r"\caption{" + f"Family {esc(fam)}: Full (orange) and the other arms (blue), mean over the cases each arm answered without error and the metric is defined for, with a 95\\% bootstrap interval. Cases per arm are in the generated table of the appendix; intervals on a handful of cases are wide and some collapse to a point when every case gives the same value. Unsupported-fact rate: lower is better." + r"}", r"\label{fig:main_" + fam + "}", r"\end{figure*}"]
        (out / f"fig_{fam}.tex").write_text("\n".join(body))
        # cost figure: tokens per case, log scale
        cb = [r"\begin{figure}[t]", r"\centering", r"\begin{tikzpicture}", r"\begin{axis}[vsplot, width=\linewidth, height=4.4cm, ymode=log, ymin=1000, title={tokens per case}, symbolic x coords={" + xs + r"}, xtick={" + xs + r"}, xticklabel style={font=\scriptsize, rotate=45, anchor=east}, bar width=6pt, nodes near coords={}, enlarge x limits=0.08]"]
        for who, col in (("full", "cB"), ("rest", "cA")):
            coords = []
            for x in order:
                if (x == "full") != (who == "full"):
                    continue
                v = [fl(r, "tokens") for r in S[x].values()]
                v = [t for t in v if t]
                if v:
                    coords.append(f"({esc(x.upper())},{sum(v) / len(v):.0f})")
            if coords:
                cb.append(r"\addplot[fill=" + col + r", draw=none, bar shift=0pt] coordinates {" + " ".join(coords) + "};")
        cb += [r"\end{axis}", r"\end{tikzpicture}", r"\caption{" + f"Family {esc(fam)}: mean tokens per case (log scale); Full in orange." + r"}", r"\label{fig:cost_" + fam + "}", r"\end{figure}"]
        (out / f"cost_{fam}.tex").write_text("\n".join(cb))
        # forest plot: each arm minus Full on the cases both answered, objection recall and unsupported-fact rate
        arms = [x for x in sorted(S) if x != "full"]
        if arms:
            fb = [r"\begin{figure*}[t]", r"\centering", r"\begin{tikzpicture}"]
            for k, (m, lab) in enumerate([("objection_recall", "objection recall"), ("unsupported_fact_rate", "unsupported-fact rate")]):
                tick = ",".join(esc(x.upper()) for x in arms)
                fb.append(r"\begin{axis}[vsbase, xbar, at={(" + f"{0.50 * k:.2f}" + r"\textwidth,0)}, width=0.46\textwidth, height=" + f"{max(4.5, 0.55 * len(arms) + 1.8):.1f}" + r"cm, title={" + lab + r": arm minus Full}, ytick=\empty, symbolic y coords={" + tick + r"}, ytick=data, yticklabel style={font=\scriptsize}, xmajorgrids, ymajorgrids=false, nodes near coords={}, xmin=-1.1, xmax=1.1, enlarge y limits=0.04, bar width=4pt, error bars/x dir=both, error bars/x explicit, error bars/error bar style={line width=0.4pt, gray!70}, extra x ticks={0}, extra x tick style={grid=major, grid style={black, line width=0.4pt}}]")
                coords = []
                for x in arms:
                    cs = sorted(c for c in S[x] if c in full and c in ok[x] and c in ok.get("full", set()))
                    d = [fl(S[x][c], m) - fl(full[c], m) for c in cs if fl(S[x][c], m) is not None and fl(full[c], m) is not None]
                    t = mean_ci(d)
                    if t:
                        lo, hi = (t[1], t[2]) if t[1] is not None else (t[0], t[0])
                        coords.append(f"({t[0]:.3f},{esc(x.upper())}) += ({hi - t[0]:.3f},0) -= ({t[0] - lo:.3f},0)")
                fb.append(r"\addplot[fill=cC, draw=none] coordinates {" + " ".join(coords) + "};")
                fb.append(r"\end{axis}")
            fb += [r"\end{tikzpicture}", r"\caption{" + f"Family {esc(fam)}: each arm minus Full on the cases both answered, mean difference with a 95\\% bootstrap interval; the line at zero is no difference. Right of zero favours the arm on objection recall and Full on the unsupported-fact rate." + r"}", r"\label{fig:forest_" + fam + "}", r"\end{figure*}"]
            (out / f"forest_{fam}.tex").write_text("\n".join(fb))
        print(fam, "arms", len(S), "common", len(common))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
