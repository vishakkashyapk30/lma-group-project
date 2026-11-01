"""Build the report's result tables and plots from the scorer's per_case CSVs (standard library only).

usage: python3 make_result_tables.py OUT_DIR family=CSV [family=CSV ...]   (a CSV may be a comma list of files; rows are concatenated)
Writes OUT_DIR/{main_<family>.tex, ablate_<family>.tex, fig_<family>.tex}. All numbers come from the CSVs; nothing is typed in.
"""
import csv, random, re, sys, statistics as st
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


def fit(t):
    t = t.replace(r'\begin{tabular}', '\\begin{adjustbox}{max width=\\textwidth}\n\\begin{tabular}', 1)
    return t.replace(r'\end{tabular}', '\\end{tabular}\n\\end{adjustbox}', 1)


FAMNAME = {"shravani_gem": "Gemini block B", "shravani_off": "offline store knock-outs", "openai": "OpenAI", "gemini": "Gemini block A", "sarvam": "Sarvam", "v1": "superseded 50-case run"}


def fam_label(f):
    return FAMNAME.get(f, f)


def esc(s):
    return s.replace("_", r"\_")


LOWER = {"unsupported_fact_rate", "fabricated_citation_rate", "tokens", "cost_usd"}


def marks(vals, higher=True, dg=2):
    """Index -> 'b' (best) or 'u' (second best distinct value) over the non-None values, compared at display precision."""
    d = sorted({round(v, dg) for v in vals if v is not None}, reverse=higher)
    out = {}
    for i, v in enumerate(vals):
        if v is None:
            continue
        r = round(v, dg)
        if d and r == d[0]:
            out[i] = "b"
        elif len(d) > 1 and r == d[1]:
            out[i] = "u"
    n = len([v for v in vals if v is not None])
    if sum(1 for k in out.values() if k == "b") > max(3, n // 3):  # a column where many arms tie carries no ranking
        return {}
    return out


def style(txt, mk):
    return r"\textbf{" + txt + "}" if mk == "b" else (r"\underline{" + txt + "}" if mk == "u" else txt)


def armkey(x):
    if x == "full":
        return (0, 0, "")
    g = {"b": 1, "a": 2, "s": 3, "p": 4}.get(x[0], 5)
    n = re.sub(r"\D", "", x)
    return (g, int(n) if n else 0, x)


def armorder(S):
    return sorted(S, key=armkey)


def dotplot(fam, kind, arms, panels, stat, lo_, hi_, xlabel, caption, log=False, single=False):
    """Full-width horizontal dot-and-interval plot: one row per arm, one panel per metric, all arms listed (grouped by family of arm)."""
    labs = {x: esc(x.upper()) for x in arms}
    ys = ",".join(labs[x] for x in arms)
    h = max(5.0, 0.26 * len(arms) + 1.2)
    pw = 0.30 if len(panels) == 3 else (0.225 if len(panels) == 4 else 0.62)
    gap = 0.03
    L = [r"\begin{figure*}[!t]", r"\centering", r"\begin{tikzpicture}"]
    for k, (m, title, note) in enumerate(panels):
        x0 = 0.0 if k == 0 else (0.07 + k * (pw + gap)) if single is False else 0.0
        first = k == 0
        at = 0.0 if first else 0.07 + k * (pw + gap) - (0.0)
        opts = [r"vsbase", r"at={(" + f"{(0.0 if first else 0.075 + k * (pw + gap)):.3f}" + r"\textwidth,0)}", r"width=" + (f"{pw + (0.07 if first else 0):.3f}" if not single else f"{pw:.3f}") + r"\textwidth",
                r"height=" + f"{h:.1f}cm", r"title={" + title + r"\\{\scriptsize\mdseries " + note + r"}}", r"title style={font=\footnotesize\bfseries, align=center}", r"symbolic y coords={" + ys + r"}", r"ytick={" + ys + "}", r"y dir=reverse",
                r"xmin=" + str(lo_), r"xmax=" + str(hi_), r"xmajorgrids", r"grid style={gray!25}", r"enlarge y limits=0.03", r"enlarge x limits=0.04", r"nodes near coords={}", r"xticklabel style={font=\scriptsize}",
                r"error bars/x dir=both", r"error bars/x explicit", r"error bars/error bar style={line width=0.5pt, gray!70}", r"every axis plot/.append style={}"]
        if log:
            opts.append("xmode=log")
        opts.append(r"yticklabel style={font=\scriptsize}" if first else r"yticklabels={}")
        if kind != "forest" and not log and "full" in arms:
            t = stat("full", m)
            ref = t[0] if t else None
        else:
            ref = 0 if kind == "forest" else None
        L.append(r"\begin{axis}[" + ", ".join(opts) + "]")
        for grp, col in (("full", "cB"), ("base", "cA"), ("abl", "cD"), ("var", "cC")):
            co = []
            for x in arms:
                g = "full" if x == "full" else {"b": "base", "a": "abl"}.get(x[0], "var")
                if g != grp:
                    continue
                t = stat(x, m)
                if not t:
                    continue
                if t[1] is None:
                    co.append(f"({t[0]:.4f},{labs[x]}) += (0,0) -= (0,0)")
                else:
                    co.append(f"({t[0]:.4f},{labs[x]}) += ({t[2] - t[0]:.4f},0) -= ({t[0] - t[1]:.4f},0)")
            if co:
                L.append(r"\addplot[only marks, mark=*, mark size=2.1pt, color=" + col + r", fill=" + col + r"] coordinates {" + " ".join(co) + "};")
        if ref is not None and not log:
            L.append(r"\addplot[black, dashed, line width=0.5pt, mark=none, error bars/.cd, x dir=none] coordinates {(" + f"{ref:.4f}," + labs[arms[0]] + ") (" + f"{ref:.4f}," + labs[arms[-1]] + ")};")
        L.append(r"\end{axis}")
    present = {("full" if x == "full" else {"b": "base", "a": "abl"}.get(x[0], "var")) for x in arms}
    names = [("full", "cB", "Full"), ("base", "cA", "baselines (B)"), ("abl", "cD", "ablations (A)"), ("var", "cC", "variants (S, P)")]
    leg = r"\node[font=\scriptsize, anchor=north west] at (0,-1.3cm) {" + r" \quad ".join(r"\textcolor{" + c + r"}{$\bullet$} " + n for g, c, n in names if g in present) + "};"
    L += [leg, r"\end{tikzpicture}", r"\caption{" + caption + r"}", r"\label{fig:" + kind + "_" + fam + "}", r"\end{figure*}"]
    return "\n".join(L)


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
        bl = [x for x in BASE if x in S]
        mrows = {}
        for s_ in bl:
            cs = sorted(c for c in S[s_] if c in full and c in ok[s_] and c in ok.get("full", set()))
            row = []
            for m, _, _ in KEY:
                pr = [(fl(S[s_][c], m), fl(full[c], m)) for c in cs]
                pr = [(a_, b_) for a_, b_ in pr if a_ is not None and b_ is not None]
                row.append((sum(a_ for a_, _ in pr) / len(pr), sum(b_ for _, b_ in pr) / len(pr), len(pr)) if pr else None)
            mrows[s_] = (len(cs), row)
        mm = [marks([mrows[x][1][j][0] if mrows[x][1][j] else None for x in bl], KEY[j][0] not in LOWER) for j in range(len(KEY))]
        for xi, s_ in enumerate(bl):
            cells = [str(mrows[s_][0])]
            for j in range(len(KEY)):
                t = mrows[s_][1][j]
                cells.append("--" if not t else style(f"{t[0]:.2f}", mm[j].get(xi)) + f" / {t[1]:.2f} ({t[2]})")
            lines.append(esc(s_.upper()) + " & " + " & ".join(cells) + r" \\")
        lines += [r"\bottomrule", r"\end{tabular}",
                  r"\caption{" + f"Family {fam_label(fam)}: each baseline beside Full on the cases both answered without error. A cell is the arm's mean, then Full's mean on the same cases, over the cases where the metric is defined for both (the count in brackets). Unsupported facts: lower is better; the others: higher is better. The arm's value is bold for the best baseline in the column and underlined for the second best. A dash means the metric is undefined for the arm (for example, a baseline that cites no authority has no citation precision)." + r"}",
                  r"\label{tab:main_" + fam + "}", r"\end{table*}"]
        (out / f"main_{fam}.tex").write_text(fit("\n".join(lines)))
        # table 2: each other arm against Full on the cases both answered (paired difference of means)
        rows = [r"\begin{table*}[t]", r"\centering\footnotesize", r"\begin{tabular}{@{}lr" + "r" * len(METRICS) + r"@{}}", r"\toprule",
                "Arm & Cases & " + " & ".join("$\\Delta$ " + m[1] for m in METRICS) + r" \\", r"\midrule"]
        ab_arms = [x for x in armorder(S) if x != "full"]
        ab = {}
        for x in ab_arms:
            cs = sorted(c for c in S[x] if c in full and c in ok[x] and c in ok.get("full", set()))
            ab[x] = (cs, [mean_ci([fl(S[x][c], m) - fl(full[c], m) for c in cs if fl(S[x][c], m) is not None and fl(full[c], m) is not None]) for m, _, _ in METRICS])
        abm = [marks([ab[x][1][j][0] if ab[x][1][j] else None for x in ab_arms], METRICS[j][0] not in LOWER) for j in range(len(METRICS))]
        for xi, x in enumerate(ab_arms):
            cells = [str(len(ab[x][0]))]
            for j in range(len(METRICS)):
                t = ab[x][1][j]
                txt = (f"{t[0]:+.2f}" + (f" [{t[1]:+.2f}, {t[2]:+.2f}]" if t[1] is not None else "")) if t else "--"
                cells.append(style(txt, abm[j].get(xi)) if t else txt)
            rows.append(esc(x.upper()) + " & " + " & ".join(cells) + r" \\")
        rows += [r"\bottomrule", r"\end{tabular}",
                 r"\caption{" + f"Family {fam_label(fam)}: each arm minus Full on the cases both answered (mean difference, 95\\% bootstrap interval). A positive difference favours the arm for the higher-is-better metrics and Full for unsupported facts and fabricated citations. Intervals that include zero are not resolved at this sample size. Bold: the most favourable mean difference in the column; underlined: the second most favourable." + r"}",
                 r"\label{tab:ablate_" + fam + "}", r"\end{table*}"]
        (out / f"ablate_{fam}.tex").write_text(fit("\n".join(rows)))
        arms_all = armorder(S)
        # master table: every arm on every metric (mean over the arm's own answered cases; a dash = undefined)
        MM = [("objection_recall", "Obj. rec.", 2), ("answerable_coverage", "Ans. cov.", 2), ("coverage", "Cov.", 2), ("factor_recall", "Factor rec.", 2),
              ("citation_precision", "Cit. prec.", 2), ("fabricated_citation_rate", "Fabr. cit.", 2), ("unsupported_fact_rate", "Unsupp. facts", 2), ("tokens", "Tokens", 0), ("cost_usd", "USD", 4)]
        MM = [t for t in MM if any(fl(S[x][c], t[0]) is not None for x in arms_all for c in ok[x])]
        ML = [r"\begin{table*}[t]", r"\centering\footnotesize", r"\begin{tabular}{@{}llr" + "r" * len(MM) + r"@{}}", r"\toprule",
              "Group & Arm & Cases & " + " & ".join(m[1] for m in MM) + r" \\", r"\midrule"]
        mat = {x: [[q for q in (fl(S[x][c], m) for c in sorted(ok[x])) if q is not None] for m, _, _ in MM] for x in arms_all}
        avg = {x: [sum(v) / len(v) if v else None for v in mat[x]] for x in arms_all}
        mk = [marks([avg[x][j] for x in arms_all], MM[j][0] not in LOWER, MM[j][2]) for j in range(len(MM))]
        prev = None
        for xi, x in enumerate(arms_all):
            g = "Full" if x == "full" else {"b": "Baselines", "a": "Ablations"}.get(x[0], "Variants")
            if prev is not None and g != prev:
                ML.append(r"\midrule")
            cs = [str(len(ok[x]))]
            for j, (m, _, dg) in enumerate(MM):
                v = avg[x][j]
                cs.append(style(f"{v:.{dg}f}", mk[j].get(xi)) if v is not None else "--")
            ML.append((g if g != prev else "") + " & " + esc(x.upper()) + " & " + " & ".join(cs) + r" \\")
            prev = g
        ML += [r"\bottomrule", r"\end{tabular}", r"\caption{" + f"Family {fam_label(fam)}: every arm on every metric, mean over the cases the arm answered without error where the metric is defined (a dash means undefined, for example no citation by that arm). Cases: orders answered. Higher is better except unsupported facts and fabricated citations; tokens (and USD where priced) are per case. Arms run on different numbers of orders (the Cases column), so read near-equal rows with the paired tables of the appendix, which carry intervals. Bold: best in the column; underlined: second best." + r"}", r"\label{tab:master_" + fam + "}", r"\end{table*}"]
        (out / f"master_{fam}.tex").write_text(fit("\n".join(ML)))
        # figure 1: per metric, each arm on its own answered cases, mean with a 95% bootstrap interval; dashed line is Full
        fig_panels = [("objection_recall", "Objection recall", "higher is better"), ("answerable_coverage", "Answerable coverage", "higher is better"), ("unsupported_fact_rate", "Unsupported-fact rate", "lower is better")]
        def stat(x, m):
            return mean_ci([v for v in (fl(S[x][c], m) for c in sorted(ok[x])) if v is not None])
        (out / f"fig_{fam}.tex").write_text(dotplot(
            fam, "main", arms_all, fig_panels, stat, 0, 1.05, "Mean",
            f"Family {fam_label(fam)}: each arm on the cases it answered without error and where the metric is defined, mean with a 95\\% bootstrap interval (the number of cases per arm is in the appendix tables). The dashed line is Full; an arm without a mark has no defined value on this metric (no gold or no output of that kind). Unsupported-fact rate: lower is better."))
        # figure 2: each arm minus Full on the cases both answered
        full = S.get("full", {})
        def diff(x, m):
            cs = sorted(c for c in S[x] if c in full and c in ok[x] and c in ok.get("full", set()))
            return mean_ci([fl(S[x][c], m) - fl(full[c], m) for c in cs if fl(S[x][c], m) is not None and fl(full[c], m) is not None])
        farms = [x for x in arms_all if x != "full"]
        if farms:
            fpan = [("objection_recall", "Objection recall", "right favours the arm"), ("answerable_coverage", "Answerable coverage", "right favours the arm"), ("citation_precision", "Citation precision", "right favours the arm"), ("unsupported_fact_rate", "Unsupported-fact rate", "left favours the arm")]
            (out / f"forest_{fam}.tex").write_text(dotplot(
                fam, "forest", farms, fpan, diff, -1.05, 1.05, "Arm minus Full",
                f"Family {fam_label(fam)}: each arm minus Full on the cases both answered, mean difference with a 95\\% bootstrap interval. The line at zero is no difference; an interval that crosses it is not resolved at this sample size. On the unsupported-fact rate a negative difference favours the arm."))
        # cost figure: tokens per case, log scale, horizontal
        def toks(x, m):
            v = [t for t in (fl(r, "tokens") for r in S[x].values()) if t]
            return (sum(v) / len(v), None, None, len(v)) if v else None
        (out / f"cost_{fam}.tex").write_text(dotplot(
            fam, "cost", arms_all, [("tokens", "Tokens per case", "log scale")], toks, 1000, 400000, "Tokens", f"Family {fam_label(fam)}: mean tokens per case (log scale), each arm on its own cases.", log=True, single=True))
        # compact table 1 in two parts (each arm's own cases, mean [95% CI] (n))
        def part(name, cols, cap):
            L = [r"\begin{table}[htbp]", r"\centering\footnotesize", r"\begin{tabular}{@{}l" + "r" * len(cols) + r"@{}}", r"\toprule", "Arm & " + " & ".join(c[1] for c in cols) + r" \\", r"\midrule"]
            px = [y for y in ["full"] + BASE if y in S]
            st_ = {x: [mean_ci([q for q in (fl(r_, m) for r_ in S[x].values()) if q is not None]) for m, _, _ in cols] for x in px}
            pm = [marks([st_[x][j][0] if st_[x][j] else None for x in px], cols[j][0] not in LOWER, cols[j][2]) for j in range(len(cols))]
            for xi, x in enumerate(px):
                cs = []
                for j, (m, _, dg) in enumerate(cols):
                    t = st_[x][j]
                    txt = "--" if not t else (f"{t[0]:.{dg}f} [{t[1]:.{dg}f}, {t[2]:.{dg}f}] ({t[3]})" if t[1] is not None else f"{t[0]:.{dg}f} ({t[3]})")
                    cs.append(txt if not t else style(txt, pm[j].get(xi)))
                L.append(esc(x.upper()) + " & " + " & ".join(cs) + r" \\")
            L += [r"\bottomrule", r"\end{tabular}", r"\caption{" + cap + " Bold: best in the column; underlined: second best." + r"}", r"\label{tab:" + name + "_" + fam + "}", r"\end{table}"]
            (out / f"{name}_{fam}.tex").write_text(fit("\n".join(L)))
        part("table1a", [("factor_recall", "Factor recall", 2), ("factor_precision_lenient", "Precision (lenient)", 2), ("factor_f1", "F1", 2)], f"Family {fam_label(fam)}: factor-level metrics, mean [95\\% bootstrap interval] over the orders where the metric is defined (their number in brackets). Each arm on its own orders.")
        part("table1b", [("unsupported_fact_rate", "Unsupported facts", 2), ("objection_recall", "Objection recall", 2), ("answerable_coverage", "Answerable coverage", 2), ("coverage", "Coverage", 2), ("tokens", "Tokens", 0), ("cost_usd", "USD per case", 4)], f"Family {fam_label(fam)}: unsupported-fact rate (lower is better), objection recall, answerable coverage, coverage, tokens and cost per case, mean [95\\% bootstrap interval] (n). Each arm on its own orders.")
        print(fam, "arms", len(S), "common", len(common))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
