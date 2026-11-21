"""Poster plots and tables: VS-Final against baselines, ablations and architecture candidates.

Reads the frozen result tables under docs/results/search and writes PNG, PDF, CSV and Markdown
files to docs/results/poster. Run: .venv/bin/python scripts/poster/make_plots.py
"""
import csv
import re
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "docs/results/search"
OUT = ROOT / "docs/results/poster"
OUT.mkdir(parents=True, exist_ok=True)

PURPLE, GREY, ORANGE, INK, MUTED = "#4B2A85", "#D9D5E4", "#C8642B", "#1E1E2A", "#6B6B78"
VSF = "s13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"

sns.set_theme(style="white", font="Lato", rc={
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#9A98A6",
    "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK,
    "font.size": 10, "axes.labelsize": 10, "xtick.labelsize": 9.5, "ytick.labelsize": 10,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def write_table(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    (OUT / f"{name}.md").write_text("\n".join(lines) + "\n")


def wlt(path, arm_key, other_key):
    """Count wins, ties and losses per (arm, other) pair; too-few and undefined cells are left out."""
    counts = {}
    for r in csv.DictReader(open(path)):
        if r["outcome"] not in ("win", "tie", "loss"):
            continue
        counts.setdefault((r[arm_key], r[other_key]), Counter())[r["outcome"]] += 1
    return counts


def stacked(ax, labels, w, t, l, bold=()):
    y = range(len(labels))
    ax.barh(y, w, color=PURPLE, height=0.62, label="wins")
    ax.barh(y, t, left=w, color=GREY, height=0.62, label="ties")
    ax.barh(y, l, left=[a + b for a, b in zip(w, t)], color=ORANGE, height=0.62, label="losses")
    for i, (a, b, c) in enumerate(zip(w, t, l)):
        if a:
            ax.text(a / 2, i, str(a), ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        if b:
            ax.text(a + b / 2, i, str(b), ha="center", va="center", color=INK, fontsize=9)
        if c:
            ax.text(a + b + c + 0.6, i, str(c), ha="left", va="center", color=ORANGE, fontsize=9, fontweight="bold")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    for tick, lab in zip(ax.get_yticklabels(), labels):
        if lab in bold:
            tick.set_fontweight("bold")
            tick.set_color(PURPLE)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)


# ---------- 1. Results on the 80 sealed orders ----------
def num(s):
    s = (s or "").split(" ")[0]
    return float(s) if s not in ("", "nan") else None

means = {r["arm"]: r for r in csv.DictReader(open(RES / "final_report/means_blind.csv"))}
names = {VSF: "VS-Final", **{f"b{i}": f"B{i}" for i in range(7)}}
metrics = [
    ("objection_recall", "Objection recall", True),
    ("answerable_coverage", "Answerable coverage", True),
    ("citation_precision", "Citation precision", True),
    ("fabricated_citation_rate", "Fabricated citations", False),
    ("unsupported_fact_rate", "Unsupported-fact rate", False),
    ("confident_wrong_rate", "Doubly unsupported rate", False),
]
rows = []
for arm, name in names.items():
    for key, label, up in metrics:
        v = num(means[arm][key])
        rows.append({"system": name, "metric": f"{label} {'↑' if up else '↓'}", "value": v})
dots = pd.DataFrame(rows)

tab1 = dots.pivot(index="system", columns="metric", values="value").reindex(list(names.values()))
tab1 = tab1[[f"{l} {'↑' if u else '↓'}" for _, l, u in metrics]].round(2)
tab1 = tab1.apply(lambda col: col.map(lambda v: f"{v:.2f}" if pd.notna(v) else "n/a"))
tab1["Store calls"] = [int(round(num(means[a]["store_calls"]))) for a in names]
tab1 = tab1.reset_index()
write_table(tab1, "table_results_against_baselines_metrics")

fig, ax = plt.subplots(figsize=(7.2, 3.4))
order = [f"{l} {'↑' if u else '↓'}" for _, l, u in metrics]
base = dots[dots.system.str.startswith("B")].dropna()
sns.stripplot(data=base, y="metric", x="value", order=order, color="#A9A6B8", size=6, jitter=0.12,
              ax=ax, zorder=2, label="B0 to B6")
vsf = dots[dots.system == "VS-Final"].dropna()
sns.stripplot(data=vsf, y="metric", x="value", order=order, color=PURPLE, marker="D", size=9,
              jitter=False, ax=ax, zorder=4)
for i, m in enumerate(order):
    v = vsf[vsf.metric == m].value.iloc[0]
    ax.text(v, i - 0.32, f"{v:.2f}", ha="center", va="bottom", color=PURPLE, fontsize=8.5, fontweight="bold")
ax.set_xlim(-0.03, 1.05)
ax.set_xlabel("score (↑ higher is better, ↓ lower is better)")
ax.set_ylabel("")
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#ECEAF2", lw=0.8)
from matplotlib.lines import Line2D
ax.legend(handles=[
    Line2D([], [], marker="D", ls="", color=PURPLE, ms=8, label="VS-Final"),
    Line2D([], [], marker="o", ls="", color="#A9A6B8", ms=6, label="Baselines B0 to B6"),
], loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=2, frameon=False, fontsize=9.5)
save(fig, "results_against_baselines_metrics")

# 1b. wins, ties and losses against each baseline
c = wlt(RES / "final_report/wlt_blind.csv", "arm", "baseline")
labels, W, T, L, trows = [], [], [], [], []
for b in [f"b{i}" for i in range(7)]:
    for arm, name in ((VSF, "VS-Final"),):
        k = c[(arm, b)]
        labels.append(f"vs {b.upper()}")
        W.append(k["win"]); T.append(k["tie"]); L.append(k["loss"])
        trows.append({"system": name, "baseline": b.upper(), "wins": k["win"], "ties": k["tie"], "losses": k["loss"]})
for name, arm in (("VS-Final", VSF),):
    tot = sum((c[(arm, f"b{i}")] for i in range(7)), Counter())
    trows.append({"system": name, "baseline": "total", "wins": tot["win"], "ties": tot["tie"], "losses": tot["loss"]})
write_table(pd.DataFrame(trows), "table_results_against_baselines_wlt")

fig, ax = plt.subplots(figsize=(6.6, 3.2))
stacked(ax, labels, W, T, L)
ax.set_xlabel("VS-Final's wins, ties and losses over the quality metrics\n"
              "win: 95% paired-bootstrap interval of the difference excludes 0 in VS-Final's favour (Holm)")
ax.legend(loc="upper center", bbox_to_anchor=(0.4, 1.08), ncol=3, frameon=False, fontsize=9.5)
save(fig, "results_against_baselines_wlt")

# ---------- 2. Ablations on the 30 search orders ----------
abl_names = {
    "s13:abstention=strict,draft_source=facts_text,objection_grounding=by_id": "minus X1 (gap-filling)",
    "s13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id": "minus X4 (abstention)",
    "s13:signal_source=merge,abstention=strict,objection_grounding=by_id": "minus X5 (draft from facts)",
    "s13:signal_source=merge,abstention=strict,draft_source=facts_text": "minus X7 (objections by id)",
    VSF + ",no_tools=true": "A3 no tools",
    VSF + ",plain_retrieval=true": "A4 plain retrieval",
    VSF + ",fixed_router=true": "A6 fixed router",
    VSF + ",free_planner=true": "A7 free planner",
    "s13:abstention=strict,objection_grounding=by_id,no_dossier=true": "A1 no dossier",
    "s13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id,no_check_repair=true": "A2 no check and repair",
    "s13:signal_source=merge,abstention=strict,draft_source=facts_text,no_sparring=true": "A8 no sparring",
    "s13:signal_source=merge,draft_source=facts_text,no_sparring=true,no_check_repair=true": "A9 no sparring, no check",
}
c = wlt(RES / "final_report/wlt_ablate.csv", "arm", "baseline")
arows = []
for key, name in abl_names.items():
    k = c[(VSF, key)]
    arows.append({"ablation": name, "VS-Final better": k["win"], "tie": k["tie"], "ablation better": k["loss"]})
abl = pd.DataFrame(arows)
write_table(abl, "table_results_against_ablations")

fig, ax = plt.subplots(figsize=(6.4, 4.2))
y = range(len(abl))
ax.barh(y, abl["VS-Final better"], color=PURPLE, height=0.6)
ax.barh(y, -abl["ablation better"], color=ORANGE, height=0.6)
for i, r in abl.iterrows():
    if r["VS-Final better"]:
        ax.text(r["VS-Final better"] + 0.12, i, str(r["VS-Final better"]), va="center", color=PURPLE, fontsize=9, fontweight="bold")
    if r["ablation better"]:
        ax.text(-r["ablation better"] - 0.12, i, str(r["ablation better"]), va="center", ha="right", color=ORANGE, fontsize=9, fontweight="bold")
    ax.text(7.4, i, str(r["tie"]), va="center", ha="center", color=MUTED, fontsize=9)
ax.text(7.4, -1.0, "ties", ha="center", va="center", color=MUTED, fontsize=9)
ax.axvline(0, color="#9A98A6", lw=1)
ax.axhline(3.5, color="#ECEAF2", lw=0.8)
ax.axhline(7.5, color="#ECEAF2", lw=0.8)
ax.set_yticks(list(y)); ax.set_yticklabels(abl["ablation"]); ax.invert_yaxis()
ax.set_xlim(-5.5, 8)
ax.set_xticks(range(-5, 7)); ax.set_xticklabels([str(abs(t)) for t in range(-5, 7)])
ax.set_xlabel("metrics where the ablation is better (left) or VS-Final is better (right)")
ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
save(fig, "results_against_ablations")

# ---------- 3. Architectures tried on the 30 search orders ----------
text = (RES / "candidate_pool/summary.md").read_text().split("## A.")[1].split("###")[0]
skip = ("no_dossier", "no_sparring", "no_check_repair", "no_tools", "plain_retrieval", "fixed_router")
crow = []
for line in text.splitlines():
    m = re.match(r"\| (.+?) \| (\d+)/(\d+)/(\d+) .*?\| ([\d.]+) \| ([\d,]+) \|", line)
    if not m or any(s in m.group(1) for s in skip):
        continue
    raw = m.group(1)
    if raw.startswith("c1457"):
        name = "VS-Final (Base + X1 X4 X5 X7)"
    elif "free_planner" in raw:
        name = "VS-Final, free planner"
    elif raw == "FULL":
        name = "Base harness"
    elif raw == "A7":
        name = "Base harness, free planner"
    elif raw == "X1+X4+X5+X6+X7":
        name = "VS-Final + X6"
    elif raw == "X1+X4+X5+X7+X8":
        name = "VS-Final + X8"
    else:
        name = "Base + " + raw.replace("+", " ")
    claims = float(m.group(5))
    crow.append({"architecture": name, "wins": int(m.group(2)), "ties": int(m.group(3)), "losses": int(m.group(4)),
                 "claims per order": claims, "writes less": "yes" if claims < 6 else "no"})
cand = pd.DataFrame(crow).sort_values(["losses", "wins"], ascending=[True, False]).reset_index(drop=True)
write_table(cand, "table_results_against_experiments")

fig, ax = plt.subplots(figsize=(6.8, 5.4))
labs = [a + ("  (writes less)" if w == "yes" else "") for a, w in zip(cand.architecture, cand["writes less"])]
stacked(ax, labs, cand.wins.tolist(), cand.ties.tolist(), cand.losses.tolist(), bold=[labs[cand.index[cand.architecture.str.startswith("VS-Final (")][0]]])
for tick, w in zip(ax.get_yticklabels(), cand["writes less"]):
    if w == "yes":
        tick.set_color(MUTED)
ax.set_xlabel("wins, ties and losses against B0 to B6 over the quality metrics (paired bootstrap, Holm)")
ax.legend(loc="upper center", bbox_to_anchor=(0.35, 1.06), ncol=3, frameon=False, fontsize=9.5)
save(fig, "results_against_experiments")

# 3b. literature variants against Full
c = wlt(RES / "candidate_pool/wlt_sweep.csv", "arm", "baseline")
srow = []
for (arm, b), k in c.items():
    if b == "full" and arm.startswith("s"):
        lab = arm.upper().replace("S13:STOPPING=LLM", "S13")
        srow.append({"variant": lab, "wins": k["win"], "ties": k["tie"], "losses": k["loss"]})
sw = pd.DataFrame(srow)
sw["key"] = sw.variant.map(lambda v: (v[0], int(re.sub(r"\D", "", v)), v))
sw = sw.sort_values("key").drop(columns="key").reset_index(drop=True)
write_table(sw, "table_results_literature_variants_against_base")

fig, ax = plt.subplots(figsize=(6.4, 4.4))
stacked(ax, sw.variant.tolist(), sw.wins.tolist(), sw.ties.tolist(), sw.losses.tolist())
ax.set_xlim(0, 16.5)
ax.set_xlabel("comparisons against the base harness (10 search orders)")
ax.legend(loc="upper center", bbox_to_anchor=(0.4, 1.06), ncol=3, frameon=False, fontsize=9.5)
save(fig, "results_literature_variants_against_base")

# ---------- How a win is decided ----------
fig = plt.figure(figsize=(6.6, 2.3))
lines = [
    (0.92, r"For each metric $m$ and baseline $B$, on the same $n$ orders:", 11, INK),
    (0.74, r"$\Delta = \frac{1}{n}\sum_{i=1}^{n}\left(m_i^{\mathrm{VS\text{-}Final}} - m_i^{B}\right)$", 15, PURPLE),
    (0.52, r"95% interval of $\Delta$: resample the $n$ orders 10,000 times (seeded bootstrap),", 10.5, INK),
    (0.40, r"at the Holm-adjusted level over the 7 baselines", 10.5, INK),
    (0.25, r"win: interval excludes 0 in VS-Final's favour     loss: excludes 0 against it     tie: contains 0", 10, MUTED),
]
for y, t, fs, col in lines:
    fig.text(0.02, y, t, fontsize=fs, color=col, va="center")
save(fig, "how_a_win_is_decided")
print("written to", OUT)
