"""Post-freeze, exploratory: sparring reserve on the 30 development search orders (docs/handoff/sparring-reserve-measurement.md).

Usage: python scripts/midsub/reserve_dev.py --r0 <out dir of arm R0> --r1 <out dir of arm R1> --s0 <per_case_agreed.csv of R0> --s1 <csv of R1>
           [--frozen-run <frozen worktree>/data/eval/dev_runs] [--ledger <spend.sqlite>] [--out docs/results/search/final_report]
Reads saved case events (`_events/<case>.jsonl`) and the scorer's per-case CSVs; writes reserve_dev.md and reserve_dev.csv.
The frozen D12 run 1 (`sarvam_var1`) and the frozen `sarvam_final` baselines B0-B6 are read only. The paired bootstrap is
`win_loss_tie.boot_p` (seeded, 10,000 resamples) and `win_loss_tie.compare` gives W/T/L; no claim is made beyond the intervals.
"""
import argparse
import csv
import json
import re
import sqlite3
import statistics as st
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "docs/report/tools"))
import win_loss_tie as wlt  # noqa: E402

UNJUDGED = "The reply could not be judged"
BASES = ["b0", "b1", "b2", "b3", "b4", "b5", "b6"]
CLASSES = ["answered", "partly", "not judged", "no supported reply", "statutory bar (NDPS s.37)", "restates / no facts or authority", "other"]


def classify_reason(verdict, reason):
    """Reason class of a verdict (keyword classes of the judge's text; 'not judged' is the fail-safe text of a refused call)."""
    r = reason or ""
    if r.startswith(UNJUDGED):
        return "not judged"
    if verdict == "ANSWERED":
        return "answered"
    if verdict == "PARTLY":
        return "partly"
    if "NO_REPLY" in r or "no supported reply" in r.lower():
        return "no supported reply"
    if re.search(r"s\.?\s*37|statutory bar|twin condition", r, re.I):
        return "statutory bar (NDPS s.37)"
    if re.search(r"restat|merely|no (case[- ])?(specific )?(facts|authority|evidence)|general|does not (provide|address|cite)|without", r, re.I):
        return "restates / no facts or authority"
    return "other"


def objection_table(outdir):
    """Counts of one arm: orders, objections raised, verdict classes, replies, failed sparring calls, reserve use."""
    c, judge_fail, reserve_spent, reserve_hit = Counter(), Counter(), [], 0
    for f in sorted(Path(outdir, "_events").glob("t1dev-*.jsonl")):
        evs = [json.loads(line) for line in open(f) if line.strip()]
        raised, verdict, reply, spent = {}, {}, {}, None
        for e in evs:
            t, o = e.get("tool"), e.get("outputs") or {}
            if e["kind"] == "AGENT_MESSAGE":
                if t == "objection":
                    raised[o["objection"]] = o
                elif t == "verdict":
                    verdict[o["objection"]] = o  # the last verdict of an objection stands
                elif t == "reply":
                    reply[o["objection"]] = o
                elif t == "model_failed" and o.get("task", "").startswith(("abhiyojak.judge_reply", "vakeel.reply_objection")):
                    judge_fail[(o["task"], o.get("error"))] += 1
                elif t == "sparring_reserve":
                    spent = max(spent or 0, o.get("spent", 0))
            elif e["kind"] == "BUDGET_HIT" and o.get("scope") == "sparring":
                reserve_hit += 1
        if spent is not None:
            reserve_spent.append(spent)
        c["orders"] += 1
        c["raised"] += len(raised)
        for oid in raised:
            v = verdict.get(oid)
            cls = classify_reason(v["verdict"], v.get("reason")) if v else "not judged"
            c["verdict:" + (v["verdict"] if v and cls != "not judged" else "NOT_JUDGED")] += 1
            c["class:" + cls] += 1
            r = reply.get(oid)
            c["reply drafted" if r and r.get("drafted") else "reply not drafted"] += 1
    return c, judge_fail, reserve_spent, reserve_hit


def case_rows(csvpath):
    return {r["case_id"]: r for r in csv.DictReader(open(csvpath)) if int(float(r.get("n_errors") or 0)) == 0}


def ledger_inr(path, run_id):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    q = ("SELECT COALESCE(SUM(CASE status WHEN 'settled' THEN cost_micro WHEN 'reserved' THEN reserved_micro "
         "WHEN 'unknown' THEN reserved_micro ELSE 0 END),0), COUNT(*) FROM calls WHERE run_id = ?")
    micro, n = con.execute(q, (run_id,)).fetchone()
    return micro / 1e6, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r0", required=True)
    ap.add_argument("--r1", required=True)
    ap.add_argument("--s0", required=True)
    ap.add_argument("--s1", required=True)
    ap.add_argument("--frozen-run")
    ap.add_argument("--ledger")
    ap.add_argument("--runids", default="reserve-dev-r0,reserve-dev-r1")
    ap.add_argument("--out", default=str(ROOT / "docs/results/search/final_report"))
    a = ap.parse_args()
    out = Path(a.out)
    csv_rows = []
    md = ["# Sparring reserve on the 30 development search orders (post-freeze, exploratory, not registered)", ""]
    arms = {"R0": a.r0, "R1": a.r1}
    frozen = "frozen D12 run 1"
    if a.frozen_run:
        arms[frozen] = str(next((Path(a.frozen_run) / "sarvam_var1/outputs").glob("s13_signal_source_merge_abstention_strict_draft_source_facts_text_objection_grounding_by_id")))
    stats = {k: objection_table(v) for k, v in arms.items()}
    md += ["## Objections by outcome (shares of objections raised)", "",
           "| arm | orders | raised | judged | ANSWERED | PARTLY | UNANSWERED (judged) | not judged | reply drafted |", "|---|---|---|---|---|---|---|---|---|"]
    for k, (c, jf, rs, rh) in stats.items():
        n = c["raised"] or 1
        nj = c["verdict:NOT_JUDGED"]
        judged = c["raised"] - nj
        csv_rows.append({"table": "objections", "arm": k, "orders": c["orders"], "raised": c["raised"], "judged": judged, "answered": c["verdict:ANSWERED"],
                         "partly": c["verdict:PARTLY"], "unanswered_judged": c["verdict:UNANSWERED"], "not_judged": nj, "reply_drafted": c["reply drafted"]})
        pct = lambda x, n=n: f"{x} ({x / n:.0%})"  # noqa: E731
        md.append(f"| {k} | {c['orders']} | {c['raised']} | {pct(judged)} | {pct(c['verdict:ANSWERED'])} | {pct(c['verdict:PARTLY'])} | "
                  f"{pct(c['verdict:UNANSWERED'])} | {pct(nj)} | {pct(c['reply drafted'])} |")
    md += ["", "Reason classes of the verdicts (keyword classes of the judge's reason text; 'not judged' is the fail-safe text of a refused reply or judge call):", "",
           "| arm | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES)]
    for k, (c, jf, rs, rh) in stats.items():
        md.append(f"| {k} | " + " | ".join(str(c["class:" + x]) for x in CLASSES) + " |")
        csv_rows.append({"table": "reason_classes", "arm": k, **{x: c["class:" + x] for x in CLASSES}})
    md += ["", "Failed sparring calls (task, error: count) and reserve use:", ""]
    for k, (c, jf, rs, rh) in stats.items():
        fails = "; ".join(f"{t} {e}: {n}" for (t, e), n in sorted(jf.items())) or "none"
        extra = (f"; reserve spent per order: mean {st.mean(rs):.0f}, max {max(rs)}; BUDGET_HIT of the reserve in {rh} order(s)") if rs else ""
        md.append(f"- {k}: {fails}{extra}")
        csv_rows.append({"table": "failed_calls", "arm": k, "detail": fails, "reserve_orders": len(rs), "reserve_mean": f"{st.mean(rs):.0f}" if rs else "", "reserve_budget_hits": rh})

    r0, r1 = case_rows(a.s0), case_rows(a.s1)
    cases = sorted(set(r0) & set(r1))
    metrics = [m for m in wlt.DECIDING if cases and m in r0[cases[0]]]
    md += ["", f"## Quality metrics: means and paired R1 minus R0 ({len(cases)} orders answered without error in both arms)", "",
           "Interval: 95% percentile interval of the seeded paired bootstrap (10,000 resamples), not adjusted for the metrics; the Holm column says whether the metric "
           "also survives Holm over all metrics (alpha 0.05). Exploratory.", "",
           "| metric | better | R0 mean | R1 mean | R1 - R0 | 95% interval | p | excludes 0 | Holm |", "|---|---|---|---|---|---|---|---|---|"]
    cells = []
    for m in metrics:
        pairs = [(wlt.value(r1[c], m), wlt.value(r0[c], m)) for c in cases]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        if len(pairs) < 5:
            continue
        d, boot, p = wlt.boot_p([x - y for x, y in pairs])
        cells.append(dict(metric=m, n=len(pairs), r0=st.mean(y for _, y in pairs), r1=st.mean(x for x, _ in pairs), diff=d,
                          lo=float(np.quantile(boot, 0.025)), hi=float(np.quantile(boot, 0.975)), p=p))
    hol = wlt.holm({c["metric"]: c["p"] for c in cells})
    for c in cells:
        label, hb = wlt.DECIDING[c["metric"]]
        ex = c["lo"] > 0 or c["hi"] < 0
        exs = ("yes, " + ("better" if (c["diff"] > 0) == hb else "worse")) if ex else "no"
        md.append(f"| {label} | {'higher' if hb else 'lower'} | {c['r0']:.4f} | {c['r1']:.4f} | {c['diff']:+.4f} | [{c['lo']:+.4f}, {c['hi']:+.4f}] | "
                  f"{c['p']:.3f} | {exs} | {'yes' if hol[c['metric']][0] else 'no'} |")
        csv_rows.append({"table": "paired_metrics", "metric": c["metric"], "n": c["n"], "r0_mean": f"{c['r0']:.5g}", "r1_mean": f"{c['r1']:.5g}", "diff": f"{c['diff']:.5g}",
                         "lo": f"{c['lo']:.5g}", "hi": f"{c['hi']:.5g}", "p": f"{c['p']:.4g}", "excludes_zero": ex, "holm": hol[c["metric"]][0], "higher_better": hb})

    md += ["", "## Tokens and spend", "", "| arm | orders | tokens per order (mean, scorer; R1 includes the reserve) | INR total (ledger) | Sarvam ledger rows | INR per order |", "|---|---|---|---|---|---|"]
    ids = dict(zip(("R0", "R1"), a.runids.split(",")))
    rowsets = {"R0": r0, "R1": r1}
    if a.frozen_run:
        rowsets[frozen] = case_rows(next((Path(a.frozen_run) / "sarvam_var1/scores").glob("s13*/per_case_agreed.csv")))
    for k, rows in rowsets.items():
        toks = [float(r["tokens"]) for r in rows.values() if r.get("tokens") not in ("", "nan", None)]
        inr, n = ledger_inr(a.ledger, ids[k]) if (a.ledger and k in ids) else (None, None)
        md.append(f"| {k} | {len(rows)} | {st.mean(toks):.0f} | {'%.1f' % inr if inr is not None else 'not read'} | {n if n is not None else ''} | {'%.2f' % (inr / len(rows)) if inr is not None else ''} |")
        csv_rows.append({"table": "cost", "arm": k, "orders": len(rows), "tokens_per_order": f"{st.mean(toks):.0f}", "inr_total": f"{inr:.2f}" if inr is not None else "", "calls": n or ""})

    if a.frozen_run:
        base_rows = []
        for f in sorted((Path(a.frozen_run) / "sarvam_final/scores").glob("*/per_case_agreed.csv")):
            base_rows += [dict(r, system=r["system"].lower()) for r in csv.DictReader(open(f)) if r["system"].lower() in BASES]
        allrows = base_rows + [dict(r, system=k.lower()) for k, rs in (("R0", r0), ("R1", r1)) for r in rs.values()]
        by = wlt.answered(allrows)
        cc = wlt.compare(by, ["r1", "r0"], [b for b in BASES if b in by], [m for m in wlt.DECIDING if m in allrows[0]])
        md += ["", "## W/T/L against B0-B6 (the frozen `sarvam_final` baseline runs on the same 30 orders; Holm within each arm and metric, as in the report)", "",
               "| arm | " + " | ".join(b.upper() for b in BASES) + " | total W/T/L (+too few, undefined) |", "|---|" + "---|" * (len(BASES) + 1)]
        for arm in ("r1", "r0"):
            per = []
            for b in BASES:
                t = Counter(c["outcome"] for c in cc if c["arm"] == arm and c["baseline"] == b)
                per.append(f"{t['win']}/{t['tie']}/{t['loss']}")
                csv_rows.append({"table": "wlt_vs_baselines", "arm": arm.upper(), "baseline": b.upper(), "win": t["win"], "tie": t["tie"], "loss": t["loss"],
                                 "too_few": t["too_few"], "undefined": t["undefined"]})
            t = Counter(c["outcome"] for c in cc if c["arm"] == arm)
            md.append(f"| {arm.upper()} | " + " | ".join(per) + f" | {t['win']}/{t['tie']}/{t['loss']} (+{t['too_few']}, {t['undefined']}) |")
        for arm in ("r1", "r0"):
            ls = sorted(f"{wlt.DECIDING[c['metric']][0]} vs {c['baseline'].upper()}" for c in cc if c["arm"] == arm and c["outcome"] == "loss")
            md += ["", f"Losses {arm.upper()}: " + ("; ".join(ls) or "none")]
    md += ["", "Exploratory and post-freeze. One run per arm; the model is not deterministic (the D12 spread of c1457 against B0-B6 between reruns was 30/31/3 and 35/28/3); "
           "R0 runs the current code, not the frozen code."]
    out.mkdir(parents=True, exist_ok=True)
    (out / "reserve_dev.md").write_text("\n".join(md) + "\n")
    keys = []
    for r in csv_rows:
        keys += [k for k in r if k not in keys]
    with open(out / "reserve_dev.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(csv_rows)
    print("\n".join(md))


if __name__ == "__main__":
    main()
