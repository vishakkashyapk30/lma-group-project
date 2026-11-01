"""Bold the best and underline the second-best value in each comparable column of the scorer's .tex tables (idempotent; run after `scoring report`).

usage: python3 mark_tables.py docs/results/dev-sweep/tables
Columns are matched by header words; direction: lower is better for cost, calls, seconds, risk, AURC, fabricated, violations, confident-wrong."""
import re, sys
from pathlib import Path

LOW = ("usd", "store calls", "seconds", "tokens", "risk", "aurc", "fabricated", "violation", "confident", "over-search")
HIGH = ("precision", "recall", "coverage")
SKIP = ("backend", "can decline", "claims", "known treatment", "court reasoning", "supreme", "dated before", "stopped", "changed by")


def direction(h):
    h = h.lower()
    if any(k in h for k in SKIP):
        return None
    if any(k in h for k in LOW):
        return False
    if any(k in h for k in HIGH):
        return True
    return None


def lead(c):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", c)
    return float(m.group(1)) if m else None


def run(path):
    L = path.read_text().split("\n")
    if any("\\textbf{" in l for l in L):
        return
    hi = next(i for i, l in enumerate(L) if l.strip().startswith("System"))
    heads = [h.strip() for h in L[hi].rstrip("\\ ").split("&")]
    rows = []
    for i in range(hi + 1, len(L)):
        if L[i].strip().startswith("\\bottomrule"):
            break
        if "&" in L[i]:
            rows.append(i)
    cells = {i: [c.strip() for c in L[i].rstrip().rstrip("\\").split("&")] for i in rows}
    for j, h in enumerate(heads):
        d = direction(h)
        if d is None:
            continue
        vals = {i: lead(cells[i][j]) for i in rows if j < len(cells[i])}
        dist = sorted({round(v, 4) for v in vals.values() if v is not None}, reverse=d)
        for i, v in vals.items():
            if v is None:
                continue
            r = round(v, 4)
            if dist and r == dist[0]:
                cells[i][j] = "\\textbf{" + cells[i][j] + "}"
            elif len(dist) > 1 and r == dist[1]:
                cells[i][j] = "\\underline{" + cells[i][j] + "}"
    for i in rows:
        L[i] = " & ".join(cells[i]) + " \\\\"
    t = "\n".join(L)
    t = re.sub(r"(\\caption\{[^\n]*?)\n", lambda m: m.group(1).rstrip("} ") + " Bold: best in the column; underlined: second best.\n" if False else m.group(0), t, count=1)
    path.write_text(t)


if __name__ == "__main__":
    for stem in ("table9_cost", "table_citations", "table_abstention"):
        run(Path(sys.argv[1]) / f"{stem}.tex")
