"""Agreement machinery for gold G1 and G3 to G7 (VI-04, EV-05): rule labeler x span-grounded non-Qwen LLM labeler, kappa, coverage, rule-only comparison.

Per order and per gold type the record holds: the rule labels, the labeler's span-validated labels, the AGREED labels (the
intersection, the plan's rule: agreed labels only), the rule-only and labeler-only labels, and a disagreement flag. Over the
orders it computes Cohen's kappa with a bootstrap interval (resampling orders), a coverage table, a disagreement breakdown and the
rule-only comparison the plan asks for (what gold would be with the rules alone, evaluation plan 5.9: rule-only, labeler-only, agreed).

Everything is computed on public court text. No label is written by hand and no score comes from a model judging anything: the
labeler's output is a set of labels of stated facts, each grounded by a verbatim span (`span_labeler`).

Candidates are written to `data/interim/gold_candidate/` next to the existing T1 files, never over them. CLI:

    python -m vakeel_sahayak.pipelines.gold.agreement run     --labeler openai --n 20 --out data/interim/gold_candidate
    python -m vakeel_sahayak.pipelines.gold.agreement report  --out data/interim/gold_candidate [--second sarvam-mimo-v2.6-flash]
    python -m vakeel_sahayak.pipelines.gold.agreement apply   --out data/interim/gold_candidate --testset data/testsets/t1 --dest data/testsets/t1_gold_candidate

`run` calls a hosted model (public text only, behind the spend ledger); `report` and `apply` are offline.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.factor_tagger import tag_factors
from vakeel_sahayak.pipelines.gold import span_labeler as sl
from vakeel_sahayak.pipelines.gold.common import agreed_labels, cohen_kappa, part_text
from vakeel_sahayak.pipelines.gold.g3_dossier_fields import flatten
from vakeel_sahayak.pipelines.gold.g6_conditions import _COMPILED as _CONDITION_RE
from vakeel_sahayak.pipelines.gold.g6_conditions import CONDITION_TYPES
from vakeel_sahayak.pipelines.gold.g7_rights_computations import _COMPILED as _RIGHTS_RE
from vakeel_sahayak.pipelines.gold.g7_rights_computations import RIGHTS_KEYWORDS
from vakeel_sahayak.pipelines.order_facts import dossier_fields, extract_dates
from vakeel_sahayak.pipelines.order_splitter import PART_ORDER, infer_outcome
from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl
from vakeel_sahayak.schemas.enums import OrderPart

DERIVED_PREFIXES = ("custody_days=",)  # arithmetic on stated dates: kept as rule-derived, not offered to the labeler
TASKS = ("g1", "g3", "g4", "g5", "g6", "g7")
DEFAULT_OUT = "data/interim/gold_candidate"


# ------------------------------------------------------------------------------------------------ rule labels


def rule_g1(parts: dict[OrderPart, str]) -> list[str]:
    """The rule labeler's G1 labels: factors the keyword rules find in the defense submissions (no model is called)."""
    return [f.value for f in tag_factors(parts.get(OrderPart.DEFENSE, ""))]


def rule_g3(parts: dict[OrderPart, str]) -> tuple[list[str], list[str]]:
    """The rule labeler's G3 labels of the whole order, split into (labels offered to agreement, rule-derived labels)."""
    text = part_text(parts, *PART_ORDER)
    labels = flatten(dossier_fields(text), sorted({m.iso for m in extract_dates(text)}))
    derived = [x for x in labels if x.startswith(DERIVED_PREFIXES)]
    return [x for x in labels if x not in derived], derived


def rule_g4(parts: dict[OrderPart, str]) -> list[str]:
    """The rule labeler's G4 labels: factors the keyword rules find in the prosecution submissions."""
    return [f.value for f in tag_factors(parts.get(OrderPart.PROSECUTION, ""))]


def rule_g5(parts: dict[OrderPart, str]) -> list[str]:
    """The rule labeler's G5 labels: factors the keyword rules find in the court's reasoning."""
    return [f.value for f in tag_factors(parts.get(OrderPart.REASONING, ""))]


def is_grant(parts: dict[OrderPart, str]) -> bool:
    """True when the operative part grants bail (the only orders that carry conditions, G6)."""
    return infer_outcome(parts.get(OrderPart.OPERATIVE, "")) == "granted"


def rule_g6(parts: dict[OrderPart, str]) -> list[str]:
    """The rule labeler's G6 labels: condition types the regexes find in the operative part of a grant (nothing for other orders)."""
    operative = parts.get(OrderPart.OPERATIVE, "")
    return [k for k in CONDITION_TYPES if _CONDITION_RE[k].search(operative)] if is_grant(parts) else []


def rule_g7(parts: dict[OrderPart, str]) -> list[str]:
    """The rule labeler's G7 labels: rights computations whose keywords the court's reasoning uses."""
    reasoning = parts.get(OrderPart.REASONING, "")
    return [c.value for c in RIGHTS_KEYWORDS if _RIGHTS_RE[c].search(reasoning)]


# the part each task reads, the rule labeler, and the labeler call (G3 reads the whole order)
TASK_PART: dict[str, OrderPart | None] = {"g1": OrderPart.DEFENSE, "g3": None, "g4": OrderPart.PROSECUTION, "g5": OrderPart.REASONING, "g6": OrderPart.OPERATIVE, "g7": OrderPart.REASONING}
TASK_LABELER: dict[str, Callable[..., sl.LabelerOutput]] = {"g1": sl.label_g1, "g3": sl.label_g3, "g4": sl.label_g4, "g5": sl.label_g5, "g6": sl.label_g6, "g7": sl.label_g7}
TASK_RULE: dict[str, Callable[[dict[OrderPart, str]], list[str]]] = {"g1": rule_g1, "g4": rule_g4, "g5": rule_g5, "g6": rule_g6, "g7": rule_g7}


def task_orders(task: str, orders: dict[str, dict[OrderPart, str]]) -> dict[str, dict[OrderPart, str]]:
    """The orders a task labels: all of them, except G6 which labels only orders whose operative part grants bail."""
    return {d: p for d, p in orders.items() if is_grant(p)} if task == "g6" else orders


def task_text(task: str, parts: dict[OrderPart, str]) -> str:
    """The text a task's labeler reads."""
    part = TASK_PART[task]
    return part_text(parts, *PART_ORDER) if part is None else parts.get(part, "")


# ------------------------------------------------------------------------------------------------ per-item agreement


def agree_item(gold: str, doc_id: str, rule: list[str], out: sl.LabelerOutput | None, derived: list[str] | None = None) -> dict[str, Any]:
    """One gold record: rule labels, labeler labels, agreed labels, the two one-sided lists and the disagreement flag.

    `status` is 'agreed' when the labeler answered (even with no label), 'rule_only' (provisional, not gold) when it did not.
    """
    ok = out is not None and out.error is None
    llm = out.labels if ok and out is not None else None
    agreed = agreed_labels(rule, llm) if llm is not None else []
    rule_only = [x for x in dict.fromkeys(rule) if llm is not None and x not in llm]
    llm_only = [x for x in (llm or []) if x not in rule]
    rec: dict[str, Any] = {
        "doc_id": doc_id, "gold": gold.upper(), "rule_labels": list(dict.fromkeys(rule)), "llm_labels": llm,
        "labels": agreed if llm is not None else list(dict.fromkeys(rule)),
        "status": "agreed" if ok else ("no_input" if out is not None and out.error == "no_input" else "rule_only"),
        "rule_only_labels": rule_only, "llm_only_labels": llm_only, "disagreement": bool(rule_only or llm_only) if llm is not None else None,
        "llm_spans": {p.label: p.span for p in out.accepted} if out is not None else {},
        "rejected": out.rejected if out is not None else [], "error": out.error if out is not None else "not_run",
    }  # fmt: skip
    if derived:
        rec["rule_derived"] = derived
    return rec


# ------------------------------------------------------------------------------------------------ statistics


def binary_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa of two binary labelings of the same items; None when undefined (no items). 1.0 when both are constant and equal."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    both = sum(x and y for x, y in zip(a, b, strict=True))
    neither = sum((not x) and (not y) for x, y in zip(a, b, strict=True))
    po = (both + neither) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def dice(a: list[list[str]], b: list[list[str]]) -> float | None:
    """Set agreement 2|A and B| / (|A| + |B|) pooled over items (the kappa of sparse label spaces tends to this); None when both are empty everywhere."""
    both = sum(len(set(x) & set(y)) for x, y in zip(a, b, strict=True))
    total = sum(len(set(x)) for x in a) + sum(len(set(y)) for y in b)
    return None if total == 0 else 2 * both / total


def bootstrap_ci(stat: Callable[[list[int]], float | None], n_items: int, *, n_boot: int = 1000, seed: int = 0, level: float = 0.95) -> tuple[float, float] | None:
    """Percentile bootstrap interval of `stat(indices)` over resampled items (orders). None when fewer than 2 items or the statistic is undefined."""
    if n_items < 2:
        return None
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(n_boot):
        v = stat([rng.randrange(n_items) for _ in range(n_items)])
        if v is not None:
            vals.append(v)
    if len(vals) < max(10, n_boot // 10):
        return None
    vals.sort()
    lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
    return vals[int(lo * (len(vals) - 1))], vals[int(hi * (len(vals) - 1))]


def kappa_with_ci(a: list[list[str]], b: list[list[str]], *, n_boot: int = 1000, seed: int = 0) -> dict[str, Any]:
    """Pooled multi-label kappa of two labelings with its bootstrap interval, plus Dice agreement and the label counts."""
    k = cohen_kappa(a, b) if a else None
    ci = bootstrap_ci(lambda idx: cohen_kappa([a[i] for i in idx], [b[i] for i in idx]), len(a), n_boot=n_boot, seed=seed)
    return {
        "n_items": len(a), "kappa": k, "ci95": list(ci) if ci else None, "dice": dice(a, b),
        "n_labels_a": sum(len(set(x)) for x in a), "n_labels_b": sum(len(set(x)) for x in b),
    }  # fmt: skip


def per_label_kappa(a: list[list[str]], b: list[list[str]], labels: Iterable[str], *, n_boot: int = 500, seed: int = 0) -> dict[str, dict[str, Any]]:
    """Binary kappa (with bootstrap interval) per label over the items."""
    out: dict[str, dict[str, Any]] = {}
    for lab in labels:
        fa, fb = [lab in set(x) for x in a], [lab in set(y) for y in b]
        ci = bootstrap_ci(lambda idx, fa=fa, fb=fb: binary_kappa([fa[i] for i in idx], [fb[i] for i in idx]), len(fa), n_boot=n_boot, seed=seed)
        out[lab] = {
            "n_a": sum(fa), "n_b": sum(fb), "both": sum(x and y for x, y in zip(fa, fb, strict=True)),
            "kappa": binary_kappa(fa, fb), "ci95": list(ci) if ci else None,
        }  # fmt: skip
    return out


def label_type(gold: str, label: str) -> str:
    """The group a label is reported under: the label itself (a factor, a condition type, a right), or the field name ('sections', 'event', ...) for G3."""
    return label.split("=", 1)[0] if gold.upper() == "G3" else label


# ------------------------------------------------------------------------------------------------ report


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Coverage of one gold type: how many orders got an input, a labeler answer, an agreed label, a full concordance."""
    ok = [r for r in records if r["status"] == "agreed"]
    return {
        "orders": len(records),
        "labeler_answered": len(ok),
        "no_input": sum(1 for r in records if r["status"] == "no_input"),
        "labeler_failed": sum(1 for r in records if r["status"] == "rule_only"),
        "with_agreed_label": sum(1 for r in ok if r["labels"]),
        "both_find_nothing": sum(1 for r in ok if not r["rule_labels"] and not r["llm_labels"]),
        "fully_concordant": sum(1 for r in ok if not r["disagreement"]),
        "with_disagreement": sum(1 for r in ok if r["disagreement"]),
        "mean_rule_labels": _mean([len(r["rule_labels"]) for r in ok]),
        "mean_llm_labels": _mean([len(r["llm_labels"]) for r in ok]),
        "mean_agreed_labels": _mean([len(r["labels"]) for r in ok]),
        "rule_only_provisional": sum(1 for r in records if r["status"] == "rule_only"),
    }


def rule_only_comparison(records: list[dict[str, Any]]) -> dict[str, Any]:
    """What the gold would be with the rules alone, next to the agreed gold (over the orders the labeler answered)."""
    ok = [r for r in records if r["status"] == "agreed"]
    n_rule = sum(len(r["rule_labels"]) for r in ok)
    n_llm = sum(len(r["llm_labels"]) for r in ok)
    n_agreed = sum(len(r["labels"]) for r in ok)
    return {
        "orders": len(ok),
        "rule_only_labels": n_rule, "labeler_only_labels": n_llm, "agreed_labels": n_agreed,
        "rule_labels_kept_by_agreement": n_agreed / n_rule if n_rule else None,
        "labeler_labels_kept_by_agreement": n_agreed / n_llm if n_llm else None,
        "orders_with_label_rule_only": sum(1 for r in ok if r["rule_labels"]),
        "orders_with_label_labeler_only": sum(1 for r in ok if r["llm_labels"]),
        "orders_with_label_agreed": sum(1 for r in ok if r["labels"]),
        "orders_where_rule_gold_differs_from_agreed": sum(1 for r in ok if set(r["rule_labels"]) != set(r["labels"])),
    }  # fmt: skip


def disagreement_types(gold: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts of one-sided labels by group and direction, and the reasons the labeler's labels were rejected."""
    rule_only: Counter[str] = Counter()
    llm_only: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    rejected_by_type: Counter[str] = Counter()
    for r in records:
        if r["status"] != "agreed":
            continue
        rule_only.update(label_type(gold, x) for x in r["rule_only_labels"])
        llm_only.update(label_type(gold, x) for x in r["llm_only_labels"])
        for rej in r["rejected"]:
            rejected[rej["reason"]] += 1
            rejected_by_type[label_type(gold, rej["label"])] += 1
    return {
        "rule_only_by_type": dict(rule_only.most_common()), "labeler_only_by_type": dict(llm_only.most_common()),
        "rejected_by_reason": dict(rejected.most_common()), "rejected_by_type": dict(rejected_by_type.most_common()),
    }  # fmt: skip


def gold_report(gold: str, records: list[dict[str, Any]], *, n_boot: int = 1000) -> dict[str, Any]:
    """The full agreement report of one gold type over its records (only the orders the labeler answered enter the kappa)."""
    ok = [r for r in records if r["status"] == "agreed"]
    a, b = [r["rule_labels"] for r in ok], [r["llm_labels"] for r in ok]
    types = sorted({label_type(gold, x) for r in ok for x in (*r["rule_labels"], *r["llm_labels"])})
    by_type: dict[str, Any] = {}
    for t in types:
        ta = [[x for x in lst if label_type(gold, x) == t] for lst in a]
        tb = [[x for x in lst if label_type(gold, x) == t] for lst in b]
        if gold.upper() != "G3":
            by_type[t] = per_label_kappa(ta, tb, [t], n_boot=min(n_boot, 500))[t] | {"dice": dice(ta, tb)}
        else:
            by_type[t] = kappa_with_ci(ta, tb, n_boot=min(n_boot, 500))
    return {
        "gold": gold.upper(),
        "coverage": coverage(records),
        "kappa_pooled": kappa_with_ci(a, b, n_boot=n_boot),
        "kappa_by_type": by_type,
        "rule_only_comparison": rule_only_comparison(records),
        "disagreements": disagreement_types(gold, records),
    }


def inter_labeler(gold: str, rule: dict[str, dict[str, Any]], first: dict[str, dict[str, Any]], second: dict[str, dict[str, Any]], *, n_boot: int = 1000) -> dict[str, Any]:
    """Kappa between two LLM labelers (and each with the rules) on the orders both answered. Inputs map doc_id to a gold record."""
    common = sorted(d for d in first if d in second and first[d]["status"] == "agreed" and second[d]["status"] == "agreed")
    a = [first[d]["llm_labels"] for d in common]
    b = [second[d]["llm_labels"] for d in common]
    r = [rule[d]["rule_labels"] for d in common]
    return {
        "gold": gold.upper(), "n_common_orders": len(common),
        "labeler1_vs_labeler2": kappa_with_ci(a, b, n_boot=n_boot),
        "rule_vs_labeler1": kappa_with_ci(r, a, n_boot=n_boot),
        "rule_vs_labeler2": kappa_with_ci(r, b, n_boot=n_boot),
    }  # fmt: skip


def _f(x: float | None, d: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def _ci(ci: list[float] | None) -> str:
    return "n/a" if not ci else f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def render_markdown(reports: dict[str, dict[str, Any]], inter: dict[str, dict[str, Any]] | None = None) -> str:
    """Summary tables (coverage, kappa with interval, rule-only comparison, disagreement types) for the handoff note."""
    lines = ["| gold | orders | labeler answered | with agreed label | fully concordant | with disagreement | mean labels rule / labeler / agreed |", "|---|---|---|---|---|---|---|"]
    for g, rep in reports.items():
        c = rep["coverage"]
        lines.append(
            f"| {g} | {c['orders']} | {c['labeler_answered']} | {c['with_agreed_label']} | {c['fully_concordant']} | {c['with_disagreement']} | "
            f"{c['mean_rule_labels']:.2f} / {c['mean_llm_labels']:.2f} / {c['mean_agreed_labels']:.2f} |"
        )
    lines += ["", "| gold | pooled kappa (rule vs labeler) | 95% bootstrap CI | Dice | labels rule / labeler |", "|---|---|---|---|---|"]
    for g, rep in reports.items():
        k = rep["kappa_pooled"]
        lines.append(f"| {g} | {_f(k['kappa'])} | {_ci(k['ci95'])} | {_f(k['dice'])} | {k['n_labels_a']} / {k['n_labels_b']} |")
    lines += ["", "| gold | rule-only labels | labeler-only labels | agreed labels | share of rule labels kept | orders with label: rule / labeler / agreed |", "|---|---|---|---|---|---|"]
    for g, rep in reports.items():
        r = rep["rule_only_comparison"]
        lines.append(
            f"| {g} | {r['rule_only_labels']} | {r['labeler_only_labels']} | {r['agreed_labels']} | {_f(r['rule_labels_kept_by_agreement'], 2)} | "
            f"{r['orders_with_label_rule_only']} / {r['orders_with_label_labeler_only']} / {r['orders_with_label_agreed']} |"
        )
    for g, rep in reports.items():
        lines += ["", f"{g} by {'field' if g == 'G3' else 'label'}:", "", "| group | n rule | n labeler | both | kappa | 95% CI | Dice |", "|---|---|---|---|---|---|---|"]
        for t, v in rep["kappa_by_type"].items():
            if g != "G3":
                lines.append(f"| {t} | {v['n_a']} | {v['n_b']} | {v['both']} | {_f(v['kappa'])} | {_ci(v['ci95'])} | {_f(v['dice'])} |")
            else:
                both = round((v["dice"] or 0) * (v["n_labels_a"] + v["n_labels_b"]) / 2)
                lines.append(f"| {t} | {v['n_labels_a']} | {v['n_labels_b']} | {both} | {_f(v['kappa'])} | {_ci(v['ci95'])} | {_f(v['dice'])} |")
        d = rep["disagreements"]
        lines += ["", f"{g} rule-only by group: {d['rule_only_by_type']}; labeler-only: {d['labeler_only_by_type']}; rejected spans by reason: {d['rejected_by_reason']}"]
    if inter:
        lines += ["", "| gold | common orders | kappa labeler1 vs labeler2 | CI | rule vs labeler1 | rule vs labeler2 |", "|---|---|---|---|---|---|"]
        for g, i in inter.items():
            lines.append(
                f"| {g} | {i['n_common_orders']} | {_f(i['labeler1_vs_labeler2']['kappa'])} | {_ci(i['labeler1_vs_labeler2']['ci95'])} | "
                f"{_f(i['rule_vs_labeler1']['kappa'])} | {_f(i['rule_vs_labeler2']['kappa'])} |"
            )
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ orders and the runner


def t1_orders(testset: str | Path = "data/testsets/t1") -> list[dict[str, str]]:
    """The T1 orders to label: `cases.jsonl` (the 200) then `dev.jsonl` (the 50), as {doc_id, split}."""
    rows: list[dict[str, str]] = []
    for split, name in (("test", "cases.jsonl"), ("dev", "dev.jsonl")):
        rows += [{"doc_id": str(r["doc_id"]), "split": split} for r in read_jsonl(Path(testset) / name)]
    return rows


def load_parts(parts_path: str | Path, doc_ids: set[str]) -> dict[str, dict[OrderPart, str]]:
    """Order parts of the wanted documents from the splitter's JSONL (streamed; the file is large)."""
    valid = {p.value for p in OrderPart}
    out: dict[str, dict[OrderPart, str]] = {}
    for row in read_jsonl(parts_path):
        d = str(row.get("doc_id"))
        if d in doc_ids and isinstance(row.get("parts"), dict):
            out[d] = {OrderPart(k): str(v) for k, v in row["parts"].items() if k in valid}
    return out


def raw_path(out: str | Path, labeler: str, task: str) -> Path:
    """Where one labeler's raw, span-validated output for one task is kept (one JSON line per order; resumable)."""
    return Path(out) / f"raw_{labeler}_{task}.jsonl"


def _out_to_json(doc_id: str, out: sl.LabelerOutput) -> dict[str, Any]:
    return {"doc_id": doc_id, "accepted": [[p.label, p.span] for p in out.accepted], "rejected": out.rejected, "error": out.error}


def _out_from_json(row: dict[str, Any]) -> sl.LabelerOutput:
    return sl.LabelerOutput([sl.Proposal(a, b) for a, b in row.get("accepted", [])], list(row.get("rejected", [])), row.get("error"))


def load_raw(path: str | Path) -> dict[str, sl.LabelerOutput]:
    """Saved labeler outputs by doc_id (the latest line of a doc wins)."""
    return {str(r["doc_id"]): _out_from_json(r) for r in read_jsonl(path)}


def run_labeler(
    task: str, orders: dict[str, dict[OrderPart, str]], client: sl.ChatClient, raw_file: str | Path, *, workers: int = 4,
    scope: Callable[[], Any] | None = None, log: Callable[[str], None] = print,
) -> dict[str, sl.LabelerOutput]:
    """Label every order not yet done (a done order is one with no error in `raw_file`), appending each result as it arrives.

    Args:
        task: 'g1' or 'g3' to 'g7'
        orders: doc_id -> parts
        client: anything with `chat(messages, max_tokens=, temperature=, json_schema=)`
        raw_file: JSONL of results (resumable)
        workers: parallel calls (the spend ledger is thread-safe)
        scope: a context-manager factory entered around each call in its own thread (the privacy scope, `public_scope`)
        log: progress sink

    Stops submitting new work after a budget refusal (a `BudgetExceeded` error), so a capped run ends instead of failing on every order.
    """
    path = Path(raw_file)
    done = {d: o for d, o in load_raw(path).items() if o.error is None or o.error == "no_input"}
    todo = [d for d in orders if d not in done]
    path.parent.mkdir(parents=True, exist_ok=True)

    def work(doc_id: str) -> tuple[str, sl.LabelerOutput]:
        parts = orders[doc_id]
        ctx = scope() if scope else None
        if ctx is not None:
            ctx.__enter__()
        try:
            return doc_id, TASK_LABELER[task](client, task_text(task, parts))
        finally:
            if ctx is not None:
                ctx.__exit__(None, None, None)

    t0, stopped = time.time(), False
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool, path.open("a", encoding="utf-8") as fh:
        pending = {pool.submit(work, d) for d in todo[: workers * 2]}
        queue = todo[workers * 2 :]
        while pending:
            for fut in as_completed(list(pending)):
                pending.discard(fut)
                doc_id, out = fut.result()
                done[doc_id] = out
                fh.write(json.dumps(_out_to_json(doc_id, out), ensure_ascii=False) + "\n")
                fh.flush()
                if out.error and ("BudgetExceeded" in out.error or "Budget" in out.error or "QuotaExceeded" in out.error):
                    stopped = True  # a spend cap or a free tier's daily quota: stop; the next run resumes (failed orders are redone)
                if queue and not stopped:
                    pending.add(pool.submit(work, queue.pop(0)))
                if len(done) % 10 == 0:
                    log(f"{task}: {len(done)}/{len(orders)} orders, {time.time() - t0:.0f}s")
                break
    if stopped:
        failed = sum(1 for o in done.values() if o.error and o.error != "no_input")
        log(f"{task}: stopped after a budget or daily-quota refusal; {len(orders) - len(done) + failed} orders still to label (run the same command again to resume)")
    return done


def build_records(gold: str, orders: dict[str, dict[OrderPart, str]], outputs: dict[str, sl.LabelerOutput]) -> list[dict[str, Any]]:
    """Gold records of the orders that have a labeler result (the others are not part of this run)."""
    recs = []
    for doc_id, parts in orders.items():
        if doc_id not in outputs:
            continue
        if gold.upper() == "G3":
            rule, derived = rule_g3(parts)
            recs.append(agree_item("G3", doc_id, rule, outputs[doc_id], derived))
        else:
            recs.append(agree_item(gold, doc_id, TASK_RULE[gold.lower()](parts), outputs[doc_id]))
    return recs


def make_client(backend: str, model: str | None = None) -> Any:
    """The hosted non-Qwen labeler client (`EvalLabeler`: PUBLIC data class, the spend ledger, the privacy gate)."""
    from vakeel_sahayak.models.labeler import EvalLabeler

    return EvalLabeler(model=model, backend=backend).client()


def labeler_slug(backend: str, model: str | None) -> str:
    """File-name slug of a labeler ('openai-gpt-6-luna', 'sarvam-mimo-v2.6-flash')."""
    if model:
        return f"{backend}-{model}".replace("/", "_")
    if backend not in ("openai", "sarvam"):
        from vakeel_sahayak.models.registry import get_provider

        spec = get_provider(backend)
        return f"{backend}-{spec.model_for('labeler') if spec else 'default'}".replace("/", "_")
    from vakeel_sahayak.models.openai.config import openai_config

    return f"openai-{openai_config()['chat']['model']}" if backend == "openai" else "sarvam-sarvam-105b"


# ------------------------------------------------------------------------------------------------ apply to the test set


def apply_to_testset(out_dir: str | Path, testset: str | Path, dest: str | Path, slug: str) -> dict[str, int]:
    """Write copies of `cases.jsonl` and `dev.jsonl` into `dest` with G1 and G3 replaced by the agreed records (the originals are untouched).

    A case whose labeler result is missing or failed keeps its existing (rule-only, provisional) record. Replaced records keep any
    extra keys of the old record (such as G3 `fields` and `events`), and gain `gold_source`, the spans and the disagreement lists.
    """
    new = {t: {r["doc_id"]: r for r in read_jsonl(Path(out_dir) / f"{t}.jsonl")} for t in TASKS if (Path(out_dir) / f"{t}.jsonl").exists()}
    Path(dest).mkdir(parents=True, exist_ok=True)
    stats = {"cases": 0, "replaced_g1": 0, "replaced_g3": 0}
    for name in ("cases.jsonl", "dev.jsonl"):
        rows = []
        for row in read_jsonl(Path(testset) / name):
            stats["cases"] += 1
            for t in TASKS:
                rec = new.get(t, {}).get(row["doc_id"])
                if rec is None or rec["status"] != "agreed":
                    continue
                old = dict((row.get("gold") or {}).get(t.upper()) or {})
                keep = {k: v for k, v in rec.items() if k not in ("doc_id", "gold", "error")}
                row.setdefault("gold", {})[t.upper()] = {**old, **keep, "gold_source": f"rules+{slug} (span-grounded, agreed only)"}
                stats[f"replaced_{t}"] = stats.get(f"replaced_{t}", 0) + 1
            rows.append(row)
        write_jsonl(Path(dest) / name, rows)
    return stats


# ------------------------------------------------------------------------------------------------ CLI


def _read_records(out: Path, task: str) -> list[dict[str, Any]]:
    return list(read_jsonl(out / f"{task}.jsonl"))


def cmd_run(args: argparse.Namespace) -> int:
    """`run`: label the T1 orders with a hosted labeler, write raw outputs, candidate gold, the report."""
    from vakeel_sahayak.models.sarvam.policy import public_scope

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = t1_orders(args.testset)
    if args.n and args.n < len(rows):
        rows = random.Random(args.seed).sample(rows, args.n)
    orders = load_parts(args.parts, {r["doc_id"] for r in rows})
    orders = {r["doc_id"]: orders[r["doc_id"]] for r in rows if r["doc_id"] in orders}
    print(f"{len(orders)} orders with parts of {len(rows)} requested")
    from vakeel_sahayak.models.registry import provider_names

    if args.labeler not in provider_names() and args.labeler not in ("openai", "sarvam"):
        raise SystemExit(f"unknown labeler {args.labeler!r}: use openai, sarvam or a provider of configs/models.yaml providers: ({', '.join(provider_names())})")
    client = make_client(args.labeler, args.model)
    slug = labeler_slug(args.labeler, args.model)
    for task in args.task.split(","):
        sub = task_orders(task, orders)
        outputs = run_labeler(task, sub, client, raw_path(out, slug, task), workers=args.workers, scope=lambda t=task: public_scope(f"gold-{t}"))
        recs = build_records(task, sub, outputs)
        print(f"{task}: {len(recs)} records, failed {sum(1 for r in recs if r['status'] != 'agreed')} (saved in {raw_path(out, slug, task).name}; `report` builds the gold files)")
    _spend_line(args.labeler)
    return 0


def _spend_line(backend: str) -> None:
    try:
        if backend not in ("openai", "sarvam"):
            from vakeel_sahayak.models.hosted.quota import provider_report

            rep = provider_report(backend)
            print(f"{backend} quota today ({rep['day']} {rep['day_tz']}): {rep['requests']} requests used, {rep['remaining']} remaining over {len(rep['keys'])} key(s); "
                  f"tokens in/out {rep['input_tokens']}/{rep['output_tokens']} (make gemini-usage for the per-key table)")
        elif backend == "openai":
            from vakeel_sahayak.models.openai.ledger import Ledger

            rep = Ledger().report()
            print(f"OpenAI ledger: {rep['spent_usd']:.4f} USD of {rep['cap_usd']:.2f}; purposes {rep['by_purpose_usd']}")
        else:
            from vakeel_sahayak.models.sarvam.spend import SarvamLedger

            rep = SarvamLedger().report()
            print(f"Sarvam ledger: INR {rep['spent_inr']:.4f} of {rep['cap_inr']:.2f}; purposes {rep['by_purpose_inr']}")
    except Exception as exc:  # reporting must never fail a finished run
        print(f"(spend report unavailable: {type(exc).__name__})")


def cmd_report(args: argparse.Namespace) -> int:
    """`report`: recompute the agreement report from saved outputs (offline)."""
    out = Path(args.out)
    rows = t1_orders(args.testset)
    orders = load_parts(args.parts, {r["doc_id"] for r in rows})
    slug = args.primary_slug
    reports: dict[str, dict[str, Any]] = {}
    inter: dict[str, dict[str, Any]] = {}
    for task in args.task.split(","):
        raw = load_raw(raw_path(out, slug, task))
        sub = {d: p for d, p in task_orders(task, orders).items() if d in raw}
        recs = build_records(task, sub, raw)
        reports[task.upper()] = gold_report(task, recs, n_boot=args.boot)
        write_jsonl(out / f"{task}.jsonl", recs)
        if args.second:
            raw2 = load_raw(raw_path(out, args.second, task))
            sub2 = {d: p for d, p in task_orders(task, orders).items() if d in raw2}
            recs2 = build_records(task, sub2, raw2)
            inter[task.upper()] = inter_labeler(task, {r["doc_id"]: r for r in recs}, {r["doc_id"]: r for r in recs}, {r["doc_id"]: r for r in recs2}, n_boot=args.boot)
    payload = {"primary_labeler": slug, "second_labeler": args.second, "reports": reports, "inter_labeler": inter}
    (out / "agreement_report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render_markdown(reports, inter or None)
    (out / "agreement_report.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """`apply`: write test-set copies with the agreed G1 and G3 into `--dest` (originals untouched)."""
    print(json.dumps(apply_to_testset(args.out, args.testset, args.dest, args.primary_slug)))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point of `python -m vakeel_sahayak.pipelines.gold.agreement`."""
    ap = argparse.ArgumentParser(prog="gold-agreement", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--out", default=DEFAULT_OUT)
        p.add_argument("--testset", default="data/testsets/t1")
        p.add_argument("--parts", default="data/interim/t1_work/parts.jsonl")
        p.add_argument("--task", default="g1,g3")

    r = sub.add_parser("run", help="label with a hosted labeler (public text only; spend-capped)")
    common(r)
    r.add_argument("--labeler", default="openai", help="openai | sarvam (paid, locked unless VS_ALLOW_PAID) | a configured provider such as gemini (public text only)")
    r.add_argument("--model", default=None, help="model id (default: the backend's configured model)")
    r.add_argument("--n", type=int, default=0, help="random sample of this many orders (0 = all 250)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--workers", type=int, default=4)
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report", help="agreement report from saved outputs (offline)")
    common(p)
    p.add_argument("--primary-slug", required=True)
    p.add_argument("--second", default=None, help="slug of a second labeler for inter-labeler kappa")
    p.add_argument("--boot", type=int, default=1000)
    p.set_defaults(fn=cmd_report)
    a = sub.add_parser("apply", help="copy the T1 files with the agreed G1/G3 into --dest")
    common(a)
    a.add_argument("--primary-slug", required=True)
    a.add_argument("--dest", default="data/testsets/t1_gold_candidate")
    a.set_defaults(fn=cmd_apply)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    return int(args.fn(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
