"""Rights Radar table of the report (standard library only).

  python3 make_table_rights.py collect F3_RUN_DIR OUT_CSV     per-scenario CSV from the arm directories written by
                                                              `python -m vakeel_sahayak.eval.features.f3_rights_radar run --out F3_RUN_DIR`
  python3 make_table_rights.py table CSV MANIFEST_JSON OUT_TEX  writes generated/table_rights.tex (nothing is typed in)

CSV columns: id,rule,arm,designed,predicted. Wilson 95% intervals; best value bold and second best underlined in the comparable
columns (accuracy, higher is better; false-ELIGIBLE, lower is better); the CHECK rate is not comparable and is left plain.
"""
import csv, json, math, sys
from pathlib import Path

ARMS = [("radar", "Rights Radar (rules engine)"), ("llm_only", "Stand-in reader"), ("llm_date_calc", "Stand-in reader + date\\_calc")]
RULES = [("default_bail", "Default bail"), ("undertrial_limit", "Undertrial limit"), ("notice_of_appearance", "Notice of appearance"),
         ("production_24h", "Production 24 h"), ("antil_category", "Antil category"), ("statutory_bar", "Statutory bar")]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def collect(run_dir, out_csv):
    rows = []
    for arm, _ in ARMS:
        for f in sorted((Path(run_dir) / arm).glob("*.json")):
            d = json.loads(f.read_text())
            rows.append({"id": f.stem, "rule": d["rule"], "arm": arm, "designed": d["designed"], "predicted": d["predicted"]})
    with open(out_csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "rule", "arm", "designed", "predicted"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out_csv}")


def mark(vals, higher=True):
    """vals: list of float|None -> list of '', 'b', 'u' (ties share the rank; second best is the next distinct value)."""
    ds = sorted({v for v in vals if v is not None}, reverse=higher)
    return ["" if v is None or len(ds) < 2 else "b" if v == ds[0] else "u" if v == ds[1] else "" for v in vals]


def wrap(s, m):
    return f"\\textbf{{{s}}}" if m == "b" else f"\\underline{{{s}}}" if m == "u" else s


def table(csv_path, manifest_path, out_tex):
    rows = list(csv.DictReader(open(csv_path)))
    man = json.load(open(manifest_path))
    per_rule_n = man["details"]["per_rule"]
    stat = {}
    for arm, _ in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        n = len(rs)
        k = sum(r["designed"] == r["predicted"] for r in rs)
        pr = {}
        for rule, _ in RULES:
            q = [r for r in rs if r["rule"] == rule]
            pr[rule] = sum(r["designed"] == r["predicted"] for r in q) / len(q) if q else None
        fe = sum(r["predicted"] == "ELIGIBLE" and r["designed"] != "ELIGIBLE" for r in rs)
        ck = sum(r["predicted"] == "CHECK" for r in rs)
        stat[arm] = dict(n=n, acc=k / n, ci=wilson(k, n), pr=pr, fe=fe, fer=fe / n, ck=ck / n)
    ns = {s["n"] for s in stat.values()}
    assert ns == {man["size"]}, (ns, man["size"])
    cols = [[stat[a]["acc"] for a, _ in ARMS]] + [[stat[a]["pr"][r] for a, _ in ARMS] for r, _ in RULES]
    marks = [mark(c, True) for c in cols]
    fe_marks = mark([stat[a]["fer"] for a, _ in ARMS], False)
    hdr = ["Arm", "$n$", "Accuracy [95\\% Wilson]"] + [f"{lab} ({per_rule_n[r]})" for r, lab in RULES] + ["False-ELIGIBLE", "CHECK rate"]
    L = ["\\begin{table*}[t]", "\\centering\\footnotesize", "\\begin{adjustbox}{max width=\\textwidth}", "\\begin{tabular}{@{}lrl" + "r" * len(RULES) + "lr@{}}", "\\toprule",
         " & ".join(hdr) + " \\\\", "\\midrule"]
    for i, (a, lab) in enumerate(ARMS):
        s = stat[a]
        cells = [lab, str(s["n"]), wrap(f"{s['acc']:.3f} [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]", marks[0][i])]
        cells += [wrap(f"{s['pr'][r]:.3f}", marks[1 + j][i]) for j, (r, _) in enumerate(RULES)]
        cells += [wrap(f"{s['fe']} of {s['n']}", fe_marks[i]), f"{s['ck']:.3f}"]
        L.append(" & ".join(cells) + " \\\\")
    L += ["\\bottomrule", "\\end{tabular}", "\\end{adjustbox}",
          "\\caption{Rights Radar on the constructed test set T4 ($n=" + str(man["size"]) + "$ scenarios; the number after each rule is its scenario count). "
          "The designed answer of each scenario is derived from the rule text by a spec writer that does not import the Radar, so the Radar's score is a consistency check of code against rule text, "
          "not a legal validation. The two stand-in rows are a deliberately naive offline reader, not a language model, and say nothing about any real model. "
          "T4 has scenarios for six of the seven rules; grounds of arrest is not scored. False-ELIGIBLE: predicted ELIGIBLE where the designed answer is not. "
          "Bold: best value in the column; underlined: second best (ties share a rank); the CHECK rate is not comparable.}",
          "\\label{tab:rights}", "\\end{table*}"]
    Path(out_tex).write_text("\n".join(L) + "\n")
    print("wrote", out_tex, {a: round(s["acc"], 3) for a, s in stat.items()})


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "collect":
        collect(*sys.argv[2:])
    elif len(sys.argv) == 5 and sys.argv[1] == "table":
        table(*sys.argv[2:])
    else:
        sys.exit(__doc__)
