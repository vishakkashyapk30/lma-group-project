"""Consistency checks in place of a reading by hand: the pre-registration against its inputs, and the Rights table against its data.

Pre-registration (`docs/preregistration.md`):
* hypotheses: the ids of its hypothesis table equal those of `configs/eval/hypotheses.yaml`; `margin_vs_p4` is the same number in both;
  every registration status the yaml names for a hypothesis (dev-contradicted, dev-supported, no dev data, provisional) is in its row.
* dev evidence: every number of the table "Dev evidence, Full minus comparator" (mean difference, interval, n; the Full/B4 token and
  store-call ratios; Full's fabricated-citation and unsupported-fact levels; "not run") equals `docs/results/prereg/dev_stats.json` at
  the printed precision.
* thresholds: the delta of every claim row (`delta N pts`, `reduction >= N pts`, `epsilon N pts`) equals the per-metric delta frozen
  in the thresholds table, and the C4 ratios (0.90, 0.60) and their dev ranges agree across the H1b row, the thresholds table, the C4
  row and the dev statistics.
Rights:
* `docs/report/generated/table_rights.tex` is exactly what `make_table_rights.py` writes from `docs/results/rights/per_scenario.csv`
  and `t4_manifest.json`; the manifest's per-rule counts equal the CSV's; every number of the report's Rights paragraph
  (`sections/results.tex`) is one the CSV gives.
* every sentence of the report that counts verified or unverified rules ("<n> of (the) seven rules ...", "(<n> of 7 match)") agrees
  with `docs/results/rights/rule_check.json` (scripts/check_rights_rules.py).

Usage: `python3 scripts/check_consistency.py` (standard library only). Prints one line per check; exits 1 if any fails.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "docs" / "preregistration.md"
HYP = ROOT / "configs" / "eval" / "hypotheses.yaml"
DEV = ROOT / "docs" / "results" / "prereg" / "dev_stats.json"
RIGHTS = ROOT / "docs" / "results" / "rights"
REPORT = ROOT / "docs" / "report"

FAMILY = {"v1": "v1", "openai": "openai", "sarvam": "sarvam", "gemini": "gemini"}
METRIC = {"objection recall": "objection_recall", "answerable coverage": "answerable_coverage", "unsupported-fact rate": "unsupported_fact_rate",
          "factor recall": "factor_recall", "lenient precision": "factor_precision_lenient", "fabricated-citation rate": "fabricated_citation_rate"}
WORDS = {w: i for i, w in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven"])}
NUM = r"[+-]?\d+\.\d+"


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, ok: bool, what: str) -> None:
        print(("ok    " if ok else "FAIL  ") + what)
        self.failed += not ok


def md_rows(text: str, header_start: str) -> tuple[list[str], list[list[str]]]:
    """Header cells and body rows of the markdown table whose header line starts with `header_start`."""
    lines = text.split("\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith(header_start))
    cells = lambda ln: [c.strip() for c in ln.strip().strip("|").split("|")]  # noqa: E731
    rows = []
    for ln in lines[i + 2 :]:
        if not ln.startswith("|"):
            break
        rows.append(cells(ln))
    return cells(lines[i]), rows


# ---------------------------------------------------------------- pre-registration


def hypotheses(rep: Report, prereg: str) -> None:
    raw = HYP.read_text(encoding="utf-8")
    yaml_ids = {m.group(1): m.group(2).lower() for m in re.finditer(r"^(H\w+):\s*(.*)$", raw, re.M)}
    margin = re.search(r"^margin_vs_p4:\s*(\d+)", raw, re.M)
    _, rows = md_rows(prereg, "| Id | Text today")
    table = {re.match(r"(H\w+)", r[0]).group(1): " ".join(r).lower() for r in rows if re.match(r"H\w+", r[0])}
    rep.check(set(yaml_ids) == set(table), f"hypothesis ids: yaml {sorted(yaml_ids)} = pre-registration {sorted(table)}")
    m = re.search(r"margin_vs_p4 = (\d+) points", prereg)
    rep.check(bool(margin and m and margin.group(1) == m.group(1)), f"margin_vs_p4: yaml {margin and margin.group(1)} = pre-registration {m and m.group(1)}")
    synonyms = {"dev-contradicted": ["dev-contradicted"], "dev-supported": ["dev-supported"], "no dev data": ["not fixable on dev", "no dev"],
                "provisional": ["provisional"]}
    for h, line in yaml_ids.items():
        for status, alts in synonyms.items():
            if status in line and h in table:
                rep.check(any(a in table[h] for a in alts), f"{h}: status '{status}' of the yaml is in its pre-registration row")


def _close(a: float, b: float, places: int = 3) -> bool:
    return abs(round(a, places) - b) <= 0.6 * 10 ** -places + 1e-12


def _cell_numbers(cell: str) -> tuple[list[tuple[float, float | None, float | None]], list[int]]:
    """([(value, lo, hi)], [n]) from a cell such as '+0.017, +0.095 [+0.026, +0.162]' or '-0.306, -0.262 (n 6, 7)'."""
    ns: list[int] = []
    for m in re.finditer(r"\(?\bn (\d+(?:,\s*\d+)*)\)?", cell):
        ns += [int(x) for x in re.findall(r"\d+", m.group(1))]
    body = re.sub(r"\(?\bn \d+(?:,\s*\d+)*\)?", "", cell)
    vals = [(float(m.group(1)), float(m.group(2)) if m.group(2) else None, float(m.group(3)) if m.group(3) else None)
            for m in re.finditer(rf"({NUM})(?:\s*\[({NUM}),\s*({NUM})\])?", body)]
    return vals, ns


def _comparators(text: str, present: set[str]) -> list[str]:
    if re.fullmatch(r"B0 to B3 \(B6\)", text):
        return [c for c in ["b0", "b1", "b2", "b3", "b6"] if c in present]
    return [c.lower() for c in re.findall(r"B\d", text)]


def dev_evidence(rep: Report, prereg: str, dev: dict) -> None:
    header, rows = md_rows(prereg, "| Test | v1")
    fams = [FAMILY[re.match(r"(\w+)", h).group(1).lower()] for h in header[1:]]
    for row in rows:
        label, cells = row[0], row[1:]
        for fam, cell in zip(fams, cells, strict=True):
            metrics = dev[fam]["metrics"]
            where = f"dev evidence '{label}' [{fam}]"
            if label.startswith("Tokens Full/B4"):
                tok, sc = metrics["tokens"].get("b4"), metrics["store_calls"].get("b4")
                if "not run" in cell:
                    rep.check(tok is None, f"{where}: B4 not run")
                    continue
                a, b = (float(x) for x in re.findall(r"\d+\.\d+", cell)[:2])
                rep.check(_close(tok["full"] / tok["comp"], a) and _close(sc["full"] / sc["comp"], b), f"{where}: {a} ({b}) = Full/B4 ratios")
                continue
            m_level = re.match(r"(.+) of Full", label)
            if m_level:
                key = METRIC[re.sub(r"\s*\(level\)", "", m_level.group(1)).lower()]
                full = metrics[key]["full_overall"]
                v = float(re.search(r"\d+\.\d+", cell).group(0))
                n = re.search(r"over (\d+)", cell)
                ok = _close(full["mean"], v) and (n is None or int(n.group(1)) == full["n"])
                rep.check(ok, f"{where}: {cell} = Full mean {full['mean']:.3f} over {full['n']}")
                continue
            m = re.match(r"(.+?) vs (.+)$", label)
            key = METRIC[m.group(1).lower()]
            comps = _comparators(m.group(2), set(metrics[key]))
            if "not run" in cell and not re.search(NUM, cell):
                named = [c.lower() for c in re.findall(r"B\d", cell)] or comps
                rep.check(all(c not in metrics[key] for c in named), f"{where}: {cell}")
                continue
            if "too small" in cell:
                continue
            vals, ns = _cell_numbers(cell)
            if "all baselines" in cell or (len(vals) == 1 and len(comps) > 1):  # one value printed for several comparators: the same for each
                d = vals[0][0]
                rep.check(all(_close(metrics[key][c]["diff"], d) for c in comps), f"{where}: {d:+.3f} against each of {comps}")
                continue
            if len(vals) != len(comps):
                rep.check(False, f"{where}: {len(vals)} values for comparators {comps}")
                continue
            for i, (c, (v, lo, hi)) in enumerate(zip(comps, vals, strict=True)):
                s = metrics[key].get(c)
                if s is None:
                    rep.check(False, f"{where}: {c} not in dev_stats.json")
                    continue
                ok = _close(s["diff"], v) and (lo is None or (_close(s["lo"], lo) and _close(s["hi"], hi)))
                n = ns[i] if len(ns) == len(comps) else (ns[0] if len(ns) == 1 else None)
                ok = ok and (n is None or n == s["n"])
                rep.check(ok, f"{where} {c}: {cell} = {s['diff']:+.3f} [{s['lo']:+.3f}, {s['hi']:+.3f}], n {s['n']}")


def thresholds(rep: Report, prereg: str, dev: dict) -> None:
    _, trows = md_rows(prereg, "| Symbol | Meaning")
    delta_row = next(r for r in trows if r[0] == "delta")[3]
    rule = {phrase.strip().lower(): int(n) for n, phrase in re.findall(r"(\d+) points for ([^(;]+)", delta_row)}
    rep.check(bool(rule), f"frozen deltas read from the thresholds table: {rule}")

    def frozen_for(text: str) -> int | None:
        t = text.lower()
        for phrase, n in rule.items():
            if any(part.strip() and part.strip() in t for part in re.split(r" and |,", phrase)):
                return n
        return None

    _, crows = md_rows(prereg, "| Id | Claim in one line")
    for r in crows:
        cid, metric_col, frozen = r[0], r[3], r[-1]
        for m in re.finditer(r"(?:delta|epsilon) (\d+) pts(?: on ([a-z -]+?)(?: and|;|,|$))?|reduction >= (\d+) pts", frozen):
            n = int(m.group(1) or m.group(3))
            target = m.group(2) or (metric_col if m.group(3) is None else "unsupported-fact rate")
            want = frozen_for(target)
            if want is None:
                continue  # a metric the thresholds table does not fix (recall@10, flip rate): plan default
            rep.check(n == want, f"{cid}: {m.group(0)} = frozen delta {want} for '{target.strip()}'")
    h1b = next(r for r in md_rows(prereg, "| Id | Text today")[1] if r[0] == "H1b")[2]
    c4 = next(r for r in crows if r[0] == "C4")[-1]
    other = next(r for r in trows if r[0].startswith("other dev-fixed"))[3]
    ratios = re.search(r"tokens Full/B4 <= (\d\.\d+).*store calls Full/B4 <= (\d\.\d+)", h1b)
    rep.check(bool(ratios) and f"C4 ratios {ratios.group(1)} and {ratios.group(2)}" in other and f"<= {ratios.group(1)}" in c4 and f"<= {ratios.group(2)}" in c4,
              "C4 ratios agree across H1b, the thresholds table and the C4 row")
    tok = [dev[f]["metrics"]["tokens"]["b4"] for f in dev if "b4" in dev[f]["metrics"]["tokens"]]
    sc = [dev[f]["metrics"]["store_calls"]["b4"] for f in dev if "b4" in dev[f]["metrics"]["store_calls"]]
    rt = sorted(t["full"] / t["comp"] for t in tok)
    rs = sorted(s["full"] / s["comp"] for s in sc)
    tok_txt, sc_txt = f"{rt[0]:.2f} to {rt[-1]:.2f}", f"{rs[0]:.2f} to {rs[-1]:.2f}"
    rep.check(tok_txt in h1b and tok_txt in c4, f"dev token ratio range {tok_txt} is printed in H1b and C4")
    rep.check(sc_txt in h1b and sc_txt in c4, f"dev store-call ratio range {sc_txt} is printed in H1b and C4")
    ok = all(r < float(ratios.group(1)) for r in rt) and all(r < float(ratios.group(2)) for r in rs)
    rep.check(ok, f"every dev ratio is below the frozen bounds {ratios.group(1)} and {ratios.group(2)}")


# ---------------------------------------------------------------- Rights


def rights_table(rep: Report) -> None:
    sys.path.insert(0, str(REPORT / "tools"))
    import make_table_rights as mtr

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "table_rights.tex"
        with contextlib.redirect_stdout(io.StringIO()):
            mtr.table(str(RIGHTS / "per_scenario.csv"), str(RIGHTS / "t4_manifest.json"), str(out))
        same = out.read_text(encoding="utf-8") == (REPORT / "generated" / "table_rights.tex").read_text(encoding="utf-8")
    rep.check(same, "table_rights.tex is what make_table_rights.py writes from per_scenario.csv and t4_manifest.json")
    rows = list(csv.DictReader((RIGHTS / "per_scenario.csv").open(encoding="utf-8")))
    man = json.loads((RIGHTS / "t4_manifest.json").read_text(encoding="utf-8"))
    radar = [r for r in rows if r["arm"] == "radar"]
    counts = Counter(r["rule"] for r in radar)
    per_rule = {k: v for k, v in man["details"]["per_rule"].items() if v}
    rep.check(dict(counts) == per_rule and len(radar) == man["size"], f"manifest per-rule counts and size {man['size']} = per_scenario.csv")
    stats = set()
    for arm in {r["arm"] for r in rows}:
        rs = [r for r in rows if r["arm"] == arm]
        k = sum(r["designed"] == r["predicted"] for r in rs)
        lo, hi = mtr.wilson(k, len(rs))
        stats |= {f"{k / len(rs):.3f}", f"{lo:.3f}", f"{hi:.3f}", f"{100 * sum(r['predicted'] == 'CHECK' for r in rs) / len(rs):.1f}"}
        stats |= {str(len(rs)), str(sum(r["predicted"] == "ELIGIBLE" and r["designed"] != "ELIGIBLE" for r in rs))}
    para = next(p for p in (REPORT / "sections" / "results.tex").read_text(encoding="utf-8").split("\n") if "Rights Radar on constructed scenarios" in p)
    for num in re.findall(r"\d+\.\d{3}|\d+\.\d(?=\\%)", para):
        rep.check(num in stats, f"results.tex Rights paragraph: {num} is computed from per_scenario.csv")
    for m in re.finditer(r"(\d+) false ELIGIBLE of (\d+)|all (\d+)\b", para):
        for g in m.groups():
            if g:
                rep.check(g in stats, f"results.tex Rights paragraph: count {g} is computed from per_scenario.csv")


def verification_counts(rep: Report) -> None:
    check = json.loads((RIGHTS / "rule_check.json").read_text(encoding="utf-8"))
    matched = sum(r["matched"] for r in check["rules"].values())
    unverified = len(check["rules"]) - matched
    pat = re.compile(r"\b(" + "|".join(WORDS) + r"|\d) of (?:the )?seven rules\b([^.;]*)", re.I)
    for tex in sorted((REPORT / "sections").glob("*.tex")):
        text = tex.read_text(encoding="utf-8")
        for m in pat.finditer(text):
            n = WORDS.get(m.group(1).lower(), None) if not m.group(1).isdigit() else int(m.group(1))
            tail = m.group(2).lower()
            if re.search(r"unverified|await|do(?:es)? not match|not yet", tail):
                rep.check(n == unverified, f"{tex.name}: '{m.group(0).strip()}' = {unverified} unverified in rule_check.json")
            elif re.search(r"\bmatch|verified", tail):
                rep.check(n == matched, f"{tex.name}: '{m.group(0).strip()}' = {matched} matched in rule_check.json")
        for m in re.finditer(r"\((\d) of 7 match\)", text):
            rep.check(int(m.group(1)) == matched, f"{tex.name}: '{m.group(0)}' = {matched} matched in rule_check.json")


def main() -> int:
    rep = Report()
    prereg = PREREG.read_text(encoding="utf-8")
    dev = json.loads(DEV.read_text(encoding="utf-8"))
    hypotheses(rep, prereg)
    dev_evidence(rep, prereg, dev)
    thresholds(rep, prereg, dev)
    rights_table(rep)
    verification_counts(rep)
    print(f"{rep.failed} failed")
    return 1 if rep.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
