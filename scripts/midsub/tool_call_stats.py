"""Tool-calling and unapproved-action counts on the blind slice, from the saved event logs (no model, no gold).

For each tool-using arm (c1457, Full, B4, B5; B0-B3 and B6 call no tool): tool calls per order, distinct tools used, the share of calls
whose result is an argument error (`invalid_args`, `invalid_input`: a wrong field name or value; the call is refused and the agent goes on),
refusals by the budget (`budget_exhausted`, the harness working as designed) and empty lookups (`not_found`), the share of orders with at
least one tool or model error that still end with a complete, scored brief (recovery), and the unsafe or unapproved actions: export
attempts before Gate 2 (each refused in code) against exports executed, and external payloads refused by the privacy boundary.
Tool selection against a gold tool sequence is not measured here (the T6 tool-calling set was not run on Sarvam).

Usage: VS_RUNS=<frozen worktree>/data/eval/dev_runs python scripts/midsub/tool_call_stats.py
Writes docs/results/search/final_report/tool_calls_blind.csv and docs/report/generated/arch_tools.tex.
"""
import csv
import glob
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path(os.environ.get("VS_RUNS", ROOT / "data/eval/dev_runs"))
OUT = ROOT / "docs/results/search/final_report"
GEN = ROOT / "docs/report/generated"
WIN = "s13_signal_source_merge_abstention_strict_draft_source_facts_text_objection_grounding_by_id"
ARMS = [("c1457", WIN), ("Full", "full"), ("B4", "b4"), ("B5", "b5")]
ARG_ERRORS = {"invalid_args", "invalid_input"}


def arm_stats(block, arm_dir):
    outs = RUNS / block / "outputs" / arm_dir
    calls = cases = exp_try = exp_ok = privacy = 0
    tools, kinds, err_cases = set(), Counter(), set()
    for f in sorted(glob.glob(str(outs / "_events" / "*.jsonl"))):
        cases += 1
        for line in open(f):
            e = json.loads(line)
            k, tool, o = e["kind"], e.get("tool"), e.get("outputs") or {}
            if k == "TOOL_CALL":
                calls += 1
                tools.add(tool)
            elif k == "TOOL_RESULT":
                if tool == "export":
                    exp_ok += 1
                er = o.get("error") if isinstance(o, dict) else None
                if er:
                    kinds[er.get("kind") if isinstance(er, dict) else str(er)] += 1
                    err_cases.add(e["case_id"])
            elif k == "ERROR":
                er = o.get("error")
                if tool == "export":
                    exp_try += 1
                elif er == "privacy_boundary":
                    privacy += 1
                else:
                    kinds["model:" + str(er)] += 1
                    err_cases.add(e["case_id"])
    complete = 0
    for f in glob.glob(str(outs / "t1-*.json")) + glob.glob(str(outs / "t1dev-*.json")):
        d = json.load(open(f))
        if d["case_id"] in err_cases and not d.get("errors") and d.get("brief"):
            complete += 1
    arg = sum(v for k, v in kinds.items() if k in ARG_ERRORS)
    return {"orders": cases, "tool_calls": calls, "calls_per_order": calls / cases if cases else 0, "distinct_tools": len(tools),
            "arg_error_share": arg / calls if calls else 0, "budget_refusal_share": kinds["budget_exhausted"] / calls if calls else 0,
            "not_found_share": kinds["not_found"] / calls if calls else 0, "orders_with_error": len(err_cases),
            "recovered_share": complete / len(err_cases) if err_cases else 1.0, "export_attempts_before_gate2": exp_try,
            "exports_executed": exp_ok, "privacy_refusals": privacy}


def main(block="sarvam_blind"):
    rows = [dict(arm=a, **arm_stats(block, d)) for a, d in ARMS]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "tool_calls_blind.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    L = [r"\begin{table}[!t]", r"\centering\small", r"\begin{adjustbox}{max width=\linewidth}", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         " & " + " & ".join(r["arm"] for r in rows) + r" \\", r"\midrule"]
    fmt = [("Tool calls per order", "calls_per_order", "{:.0f}"), ("Distinct tools used", "distinct_tools", "{}"),
           ("Calls refused for a bad argument", "arg_error_share", "pct"), ("Calls refused by the budget", "budget_refusal_share", "pct"),
           ("Lookups with no result", "not_found_share", "pct"), ("Orders with a tool or model error", "orders_with_error", "{}"),
           ("\\quad of which finished", "recovered_share", "pct0"), ("Exports tried before Gate 2", "export_attempts_before_gate2", "{}"),
           ("Exports executed", "exports_executed", "{}"), ("Payloads refused by the privacy gate", "privacy_refusals", "{}")]
    for label, key, f in fmt:
        cells = []
        for r in rows:
            v = r[key]
            cells.append(f"{100 * v:.1f}\\%" if f == "pct" else f"{100 * v:.0f}\\%" if f == "pct0" else f.format(v))
        L.append(f"{label} & " + " & ".join(cells) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}",
          r"\caption{Tool calling and unapproved actions on the 80 blind orders, counted from the saved event logs (no model, no gold). "
          r"A refused call returns a typed error and the agent continues; ``finished'' means the order still ends with a complete, scored brief. "
          r"Every arm tries to export once per order without Gate~2 approval; every attempt is refused in code. B0--B3 and B6 call no tool.}",
          r"\label{tab:tools}", r"\end{table}"]
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / "arch_tools.tex").write_text("\n".join(L) + "\n")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
