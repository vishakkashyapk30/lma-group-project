"""Win/loss/tie of every arm against every baseline on every metric: the table that decides "beats every baseline" (team to-do, 2 Nov).

usage: python3 win_loss_tie.py OUT_DIR CSV_DIR family=CSV [family=CSV ...] [--cases t1dev-000..029] [--holm-scope metric|arm] [--min-n 5]
Reads the scorer's per_case CSVs (a CSV may be a comma list of files, as in make_result_tables.py). Writes OUT_DIR/wlt_<family>.tex
(per arm: wins, ties and losses against each baseline, and the verdict) and CSV_DIR/<family>.csv (every comparison).

Per family (one backend), arm and baseline: the cases both answered without error where the metric is defined for both; the paired
difference arm minus baseline; a seeded paired bootstrap (10,000 resamples of cases, seed 0, as in docs/preregistration.md) gives the
two-sided p-value (2 x the smaller tail, with the +1 correction). Holm-Bonferroni at alpha 0.05 runs within each family of comparisons:
by default one family per (arm, metric) over the baselines, as the pre-registered families are one metric over the comparators
(`--holm-scope arm` puts all baselines and metrics of an arm in one family). A comparison with fewer than `--min-n` paired cases is
"too few" and enters Holm with p = 1. The interval printed is the percentile interval at the comparison's Holm level (alpha / (m - i)),
so it excludes zero exactly when Holm rejects. A WIN is a rejection in the arm's favour (the metric's direction), a LOSS a rejection
against it, a TIE no rejection. A metric that is undefined for the arm or the baseline on every shared case is "undefined" (for
example citation precision for a baseline that cites nothing) and is listed, not counted. An arm beats every baseline only when every
counted cell is a win and no cell is too few.
Metric directions are the scorer's (`eval/scoring/engine.METRICS`; `tests/unit/eval/test_win_loss_tie.py` keeps them equal). Tokens,
store calls, seconds, cost and the sentence count describe the run, not its quality, and do not decide.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_result_tables import esc, fam_label, fit, load  # noqa: E402

# metric key -> (label, higher is better); the scorer's quality metrics, plus M6a when the scorer output carries it
DECIDING = {
    "factor_recall": ("Factor recall", True), "factor_precision_strict": ("Factor prec. (strict)", True),
    "factor_precision_lenient": ("Factor prec. (lenient)", True), "factor_f1": ("Factor F1", True),
    "court_discussed_recall": ("Court-discussed recall", True), "unsupported_fact_rate": ("Unsupported facts (M6)", False),
    "unsupported_case_fact_rate": ("Unsupported case facts (M6a)", False),
    "unsupported_fact_count": ("Unsupported facts, count", False), "answerable_coverage": ("Answerable coverage", True),
    "recall_at_10": ("Recall@10", True), "objection_recall": ("Objection recall", True), "objection_precision": ("Objection precision", True),
    "coverage": ("Coverage", True), "fabricated_citation_rate": ("Fabricated citations", False),
    "authority_reasoning_share": ("Authorities: reasoning", True), "authority_sc_share": ("Authorities: SC", True),
    "authority_before_share": ("Authorities: before order", True), "good_law_violation_rate": ("Good-law violations", False),
    "known_treatment_share": ("Known treatment", True), "citation_precision": ("Citation precision", True),
    "citation_recall": ("Citation recall", True), "citation_removal_change": ("Removal changes claim", True),
    "over_search_rate": ("Over-search", False), "unfinished_factor_share": ("Unfinished factors", False),
    "confident_wrong_rate": ("Confident wrong", False),
}
DESCRIPTIVE = {"n_claims", "tokens", "store_calls", "seconds", "cost_usd"}
BASELINES = ["b0", "b0l", "b1", "b2", "b3", "b4", "b5", "b6"]
ALPHA, N_BOOT, SEED = 0.05, 10000, 0


def value(row, metric):
    v = row.get(metric, "")
    return float(v) if v not in ("", "nan", None) else None


def answered(rows, cases=None):
    """system -> case -> row, only cases answered without error (and in `cases` when given)."""
    out = defaultdict(dict)
    for r in rows:
        if int(float(r.get("n_errors") or 0)) == 0 and (cases is None or r["case_id"] in cases):
            out[r["system"]].setdefault(r["case_id"], r)
    return out


_IDX = {}


def boot_p(diffs):
    """(mean difference, sorted bootstrap means, two-sided p) for paired differences; seeded, resample indices shared per n."""
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    if n not in _IDX:
        _IDX[n] = np.random.default_rng(SEED).integers(0, n, size=(N_BOOT, n))
    means = np.sort(d[_IDX[n]].mean(axis=1))
    if np.all(d == 0):
        return 0.0, means, 1.0
    le, ge = int((means <= 0).sum()), int((means >= 0).sum())
    return float(d.mean()), means, min(1.0, 2 * min(le + 1, ge + 1) / (N_BOOT + 1))


def holm(pvals, alpha=ALPHA):
    """key -> (rejected, the Holm level used for that key: alpha / (m - i) at its rank)."""
    ordered = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, going = len(ordered), {}, True
    for i, (k, p) in enumerate(ordered):
        level = alpha / (m - i)
        going = going and p <= level
        out[k] = (going, level)
    return out


def compare(by_sys, arms, bases, metrics, min_n=5, scope="metric"):
    """Every (arm, baseline, metric) comparison with its outcome."""
    cells, families = [], defaultdict(dict)
    for a in arms:
        for m in metrics:
            for b in bases:
                pairs = [(value(r, m), value(by_sys[b][c], m)) for c, r in by_sys[a].items() if c in by_sys[b]]
                pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
                cell = {"arm": a, "baseline": b, "metric": m, "higher_better": DECIDING[m][1], "n": len(pairs)}
                if not pairs:
                    cell["outcome"] = "undefined"
                    cells.append(cell)
                    continue
                diffs = [x - y for x, y in pairs]
                cell.update(arm_mean=sum(x for x, _ in pairs) / len(pairs), base_mean=sum(y for _, y in pairs) / len(pairs))
                if len(pairs) < min_n:
                    cell.update(diff=sum(diffs) / len(diffs), p=1.0, outcome="too_few")
                else:
                    cell["diff"], cell["_boot"], cell["p"] = boot_p(diffs)
                cells.append(cell)
                families[(a, m) if scope == "metric" else (a,)][len(cells) - 1] = cell["p"]
    for fam in families.values():
        for i, (rej, level) in holm(fam).items():
            c = cells[i]
            c["holm_level"], c["holm_m"] = level, len(fam)
            boot = c.pop("_boot", None)
            if boot is not None:
                c["lo"], c["hi"] = float(np.quantile(boot, level / 2)), float(np.quantile(boot, 1 - level / 2))
            if c.get("outcome") == "too_few":
                continue
            good = (c["diff"] > 0) == c["higher_better"]
            c["outcome"] = "tie" if not rej else ("win" if good else "loss")
    return cells


def verdicts(cells, arms, bases):
    """arm -> {baseline: {win, tie, loss, too_few, undefined}, 'beats_all': bool}."""
    out = {}
    for a in arms:
        row = {b: defaultdict(int) for b in bases}
        for c in cells:
            if c["arm"] == a:
                row[c["baseline"]][c["outcome"]] += 1
        counted = sum(v["win"] + v["tie"] + v["loss"] + v["too_few"] for v in row.values())
        row["beats_all"] = counted > 0 and all(v["tie"] == v["loss"] == v["too_few"] == 0 for v in row.values())
        out[a] = row
    return out


FIELDS = ["arm", "baseline", "metric", "higher_better", "n", "arm_mean", "base_mean", "diff", "lo", "hi", "p", "holm_level", "holm_m", "outcome"]


def write_csv(path, cells):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for c in cells:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in c.items()})


def tex(fam, verdict, arms, bases, metrics, scope):
    head = " & ".join(b.upper() for b in bases)
    L = [r"\begin{table*}[!t]", r"\centering\small", r"\begin{tabular}{@{}l" + "c" * len(bases) + r"c@{}}", r"\toprule",
         f"Arm & {head} & Beats all \\\\", r"\midrule"]
    for a in arms:
        cells = []
        for b in bases:
            v = verdict[a][b]
            n = v["win"] + v["tie"] + v["loss"] + v["too_few"]
            cells.append("--" if n == 0 else f"{v['win']}/{v['tie']}/{v['loss']}" + (f"+{v['too_few']}" if v["too_few"] else ""))
        L.append(f"{esc(a.upper())} & " + " & ".join(cells) + f" & {'yes' if verdict[a]['beats_all'] else 'no'} \\\\")
    fam_text = "one family per arm and metric over the baselines" if scope == "metric" else "one family per arm"
    L += [r"\bottomrule", r"\end{tabular}",
          r"\caption{" + f"Family {fam_label(fam)}: wins/ties/losses of each arm against each baseline over {len(metrics)} metrics "
          f"(paired bootstrap, 10,000 resamples, Holm at 0.05, {fam_text}; a win only when the Holm-level interval excludes zero in the "
          "arm's favour). +n: comparisons with fewer than five paired cases (not a win). A dash: no metric defined for both. "
          "Beats all: every counted comparison is a win. Every comparison, with its interval, is in docs/results/wlt." + r"}",
          r"\label{tab:wlt_" + fam + "}", r"\end{table*}"]
    return fit("\n".join(L) + "\n")


def parse_cases(spec):
    if not spec:
        return None
    lo, hi = spec.split("..")
    pre = lo.rstrip("0123456789")
    width = len(lo) - len(pre)
    top = hi[len(pre):] if hi.startswith(pre) else hi  # "t1dev-000..029" or "t1dev-000..t1dev-029"
    return {f"{pre}{i:0{width}d}" for i in range(int(lo[len(pre):]), int(top) + 1)}


def main(argv):
    opts = {"--cases": None, "--holm-scope": "metric", "--min-n": "5"}
    args = []
    it = iter(argv)
    for a in it:
        if a in opts:
            opts[a] = next(it)
        else:
            args.append(a)
    out_dir, csv_dir, specs = Path(args[0]), Path(args[1]), args[2:]
    cases, scope, min_n = parse_cases(opts["--cases"]), opts["--holm-scope"], int(opts["--min-n"])
    for spec in specs:
        fam, paths = spec.split("=", 1)
        rows = load(paths)
        by_sys = answered(rows, cases)
        bases = [b for b in BASELINES if b in by_sys]
        arms = sorted(s for s in by_sys if s not in BASELINES)
        if not bases or not arms:
            print(f"{fam}: skipped (baselines {bases or 'none'}, arms {arms or 'none'})")
            continue
        columns = set(rows[0]) if rows else set()
        metrics = [m for m in DECIDING if m in columns]
        cells = compare(by_sys, arms, bases, metrics, min_n, scope)
        verdict = verdicts(cells, arms, bases)
        write_csv(csv_dir / f"{fam}.csv", cells)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"wlt_{fam}.tex").write_text(tex(fam, verdict, arms, bases, metrics, scope), encoding="utf-8")
        winners = [a for a in arms if verdict[a]["beats_all"]]
        print(f"{fam}: {len(arms)} arms x {len(bases)} baselines x {len(metrics)} metrics; beats every baseline: {', '.join(winners) or 'none'}")


if __name__ == "__main__":
    main(sys.argv[1:])
