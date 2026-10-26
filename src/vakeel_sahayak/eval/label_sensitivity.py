"""M5, label-source sensitivity (evaluation plan 4.1 M5 and 5.9): M1 to M4 recomputed under each way of building the gold, and agreement between the labelers.

The T1 gold rows (`pipelines.gold.agreement`) carry, per gold type, the three label sets the plan names: `rule_labels` (keyword rules only), `llm_labels` (one
span-grounded non-Qwen labeler only, today gpt-6-luna) and `labels` (agreed: the intersection, the primary gold). This module re-scores saved run outputs against
each, with no model call and no new label:

* sources `rule`, `labeler`, `agreed`, and `labeler2` (a second labeler, for example Sarvam-105B, read from its `raw_<slug>_g<k>.jsonl` files; only G1 and only the orders it
  answered, so the cell carries its own n);
* metrics: factor recall (M1), precision strict and lenient (M2), F1 (M3), G5 court-discussed recall (M4) on the answerable factors, exactly as the headline table
  (`scoring/case_metrics`);
* `ranking`: the systems ordered by factor recall under each source, and whether the order equals the agreed one (the question M5 asks: does the conclusion survive a
  different label source?);
* `kappa`: Cohen's kappa per factor between the rule labels and the labeler (and labeler against labeler2) on the scored orders, with a bootstrap interval.

Everything is deterministic. A gold row without `rule_labels` / `llm_labels` (a rule-only gold file, test fixtures) simply has no such source: the table says so.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import stats_extra as sx

SOURCES = ("rule", "labeler", "agreed", "labeler2")
SOURCE_LABELS = {"rule": "keyword rules only", "labeler": "one labeler only (LLM, span-grounded)", "agreed": "agreed only (primary)", "labeler2": "second labeler only"}
TASKS = ("G1", "G4", "G5")
METRICS = ("factor_recall", "factor_precision_strict", "factor_precision_lenient", "factor_f1", "court_discussed_recall")
METRIC_LABELS = {"factor_recall": "M1 factor recall", "factor_precision_strict": "M2 precision (strict)", "factor_precision_lenient": "M2 precision (lenient)",
                 "factor_f1": "M3 F1", "court_discussed_recall": "M4 G5 recall"}
N_BOOT = 2000
_FIELD = {"rule": "rule_labels", "labeler": "llm_labels", "agreed": "labels"}


def load_second_labeler(directory: str | Path, slug: str | None = None, task: str = "g1") -> dict[str, list[str]]:
    """doc_id -> labels accepted by a second labeler, from `raw_<slug>_<task>.jsonl` in `directory` ({} when absent; `slug` None picks the first slug that is not openai)."""
    base = Path(directory)
    files = sorted(base.glob(f"raw_*_{task.lower()}.jsonl"))
    if slug:
        files = [f for f in files if f.name == f"raw_{slug}_{task.lower()}.jsonl"]
    else:
        files = [f for f in files if "openai" not in f.name] or []
    if not files:
        return {}
    out: dict[str, list[str]] = {}
    for line in files[0].read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("error") or not row.get("doc_id"):
            continue
        out[str(row["doc_id"])] = list(dict.fromkeys(str(a[0]) for a in row.get("accepted") or []))
    return out


def source_labels(case: dict[str, Any], task: str, source: str, second: dict[str, list[str]] | None = None) -> list[str] | None:
    """The labels of one gold type under one source; None when the source does not exist for this order (the order then drops out of that source's cell)."""
    if source == "labeler2":
        if task != "G1" or second is None or str(case.get("doc_id")) not in second:
            return None
        return second[str(case["doc_id"])]
    g = (case.get("gold") or {}).get(task)
    if not isinstance(g, dict):
        return None
    field = _FIELD[source]
    if source != "agreed" and field not in g:
        return None  # a rule-only or fixture gold has no separate labeler column
    if g.get("status") not in (None, "agreed") and source != "rule":
        return None  # the labeler failed on this order (status rule_only): no labeler or agreed label exists
    return [str(x) for x in g.get(field) or []]


def case_values(case: dict[str, Any], record: dict[str, Any], source: str, cfg: cm.ScoreConfig, second: dict[str, list[str]] | None = None) -> dict[str, float | None] | None:
    """M1 to M4 of one record under one label source; None when the source has no G1 label set for the order."""
    g1 = source_labels(case, "G1", source, second)
    if g1 is None:
        return None
    g5 = source_labels(case, "G5", source, second) or []  # a second labeler has no G5 column: M4 is then n/a and lenient precision equals strict
    ans = cm.answerable_of(case)
    pred = cm.argued_factors(record.get("brief") or {}, cfg.stances)
    g1f, g5f = cm._factors(g1), cm._factors(g5)
    recall, strict, _ = cm._prf(pred, g1f, ans)
    _, lenient, _ = cm._prf(pred, list(dict.fromkeys(g1f + g5f)), ans)
    g5_recall, _, _ = cm._prf(pred, g5f, ans)
    if recall is None:
        f1 = None
    elif lenient is None or recall + lenient == 0:
        f1 = 0.0
    else:
        f1 = 2 * recall * lenient / (recall + lenient)
    return {"factor_recall": recall, "factor_precision_strict": strict, "factor_precision_lenient": lenient, "factor_f1": f1,
            "court_discussed_recall": g5_recall}


def _summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    mean, lo, hi = sx.bootstrap_mean_ci(list(values), N_BOOT)
    return {"mean": mean, "lo": lo, "hi": hi, "n": len(values)}


def binary_kappa(a: Sequence[bool], b: Sequence[bool]) -> float | None:
    """Cohen's kappa of two binary labelings of the same items (None with no items; 1.0 when both are constant and equal)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def _kappa_ci(fa: list[bool], fb: list[bool], n_boot: int = 500, seed: int = 0) -> list[float] | None:
    if len(fa) < 2:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        idx = [rng.randrange(len(fa)) for _ in fa]
        k = binary_kappa([fa[i] for i in idx], [fb[i] for i in idx])
        if k is not None:
            vals.append(k)
    if len(vals) < max(10, n_boot // 10):
        return None
    vals.sort()
    return [vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]]


def labeler_kappa(cases: list[dict[str, Any]], task: str = "G1", a: str = "rule", b: str = "labeler", second: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Cohen's kappa per label (factor) between two label sources over the orders where both exist, with the number of orders and of labels each source gave."""
    pairs = []
    for c in cases:
        la, lb = source_labels(c, task, a, second), source_labels(c, task, b, second)
        if la is not None and lb is not None:
            pairs.append((set(la), set(lb)))
    labels = sorted({x for p in pairs for s in p for x in s})
    per = {}
    for lab in labels:
        fa, fb = [lab in p[0] for p in pairs], [lab in p[1] for p in pairs]
        per[lab] = {"n_a": sum(fa), "n_b": sum(fb), "both": sum(x and y for x, y in zip(fa, fb, strict=True)), "kappa": binary_kappa(fa, fb), "ci95": _kappa_ci(fa, fb)}
    # pooled: every (order, label) cell is one binary item
    flat_a = [lab in p[0] for p in pairs for lab in labels]
    flat_b = [lab in p[1] for p in pairs for lab in labels]
    return {"task": task, "a": a, "b": b, "n_orders": len(pairs), "per_label": per, "pooled_kappa": binary_kappa(flat_a, flat_b),
            "n_labels_a": sum(len(p[0]) for p in pairs), "n_labels_b": sum(len(p[1]) for p in pairs)}


def compute(runs: list[Any], cases: list[dict[str, Any]], cfg: cm.ScoreConfig | None = None, second_labeler_dir: str | Path | None = None) -> dict[str, Any]:
    """The M5 block for `score_<gold>.json`: per source and system the M1 to M4 summaries, the system ranking per source, and the labeler kappas.

    Args:
        runs: loaded run sets (`scoring.loader.RunSet`)
        cases: T1 gold rows of the slice (the primary gold: they carry `rule_labels`, `llm_labels`, `labels`)
        cfg: scoring choices (stances)
        second_labeler_dir: directory with `raw_<slug>_g1.jsonl` of a second labeler (optional)
    """
    cfg = cfg or cm.ScoreConfig()
    second = load_second_labeler(second_labeler_dir) if second_labeler_dir else None
    by_case = {str(c["case_id"]): c for c in cases}
    available = {s: any(source_labels(c, "G1", s, second) is not None for c in cases) for s in SOURCES}
    out: dict[str, Any] = {"sources": {}, "available": available, "ranking": {}, "metrics": list(METRICS)}
    for source in SOURCES:
        if not available[source]:
            continue
        per_system: dict[str, dict[str, Any]] = {}
        grouped: dict[str, dict[str, list[dict[str, float | None]]]] = {}
        for rs in runs:
            for cid, rec in rs.records.items():
                if cid not in by_case:
                    continue
                v = case_values(by_case[cid], rec, source, cfg, second)
                if v is not None:
                    grouped.setdefault(rs.system, {}).setdefault(cid, []).append(v)
        for system, percase in grouped.items():
            cell: dict[str, Any] = {}
            for m in METRICS:
                means = []
                for vs in percase.values():
                    xs = [v[m] for v in vs if v[m] is not None]
                    if xs:
                        means.append(sum(xs) / len(xs))
                cell[m] = _summary(means)
            per_system[system] = cell
        out["sources"][source] = {"label": SOURCE_LABELS[source], "systems": per_system,
                                  "n_orders_with_labels": sum(1 for c in cases if source_labels(c, "G1", source, second) is not None)}
        order = sorted((s for s, c in per_system.items() if c["factor_recall"]["n"]), key=lambda s: (-per_system[s]["factor_recall"]["mean"], s.lower()))
        out["ranking"][source] = order
    agreed = out["ranking"].get("agreed")
    for source, order in out["ranking"].items():
        out["sources"][source]["same_ranking_as_agreed"] = None if agreed is None else order == agreed
    kap: dict[str, Any] = {}
    for task in TASKS:
        if any(source_labels(c, task, "rule") is not None and source_labels(c, task, "labeler") is not None for c in cases):
            kap[f"{task} rule vs labeler"] = labeler_kappa(cases, task, "rule", "labeler")
    if second:
        kap["G1 labeler vs labeler2"] = labeler_kappa(cases, "G1", "labeler", "labeler2", second)
    out["kappa"] = kap
    out["note"] = ("Same saved outputs, four label sources, no model call. The labelers are LLMs whose labels are kept only when a verbatim span grounds them; "
                   "'rule' is the keyword method. Where a source does not exist for an order the order is left out of that cell (n shows how many remain).")
    return out


def run(out_dir: str) -> dict[str, float]:
    """The flat M5 numbers of a scoring output directory: `<source>.<metric>` mean of the first system with data, read from `score_agreed.json` (written by `scoring score`).

    Args:
        out_dir: the directory `eval.scoring score --out` wrote

    Returns:
        `{"<source>.<metric>": mean}` for the reference system plus `kappa.<task>` (pooled rule vs labeler kappa); {} when the score file has no M5 block.
    """
    path = Path(out_dir) / "score_agreed.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found: run `python -m vakeel_sahayak.eval.scoring score` first")
    block = json.loads(path.read_text(encoding="utf-8")).get("label_sensitivity")
    if not block:
        return {}
    flat: dict[str, float] = {}
    for source, entry in block["sources"].items():
        for system, cell in entry["systems"].items():
            for m, s in cell.items():
                if s["mean"] is not None:
                    flat[f"{source}.{system}.{m}"] = s["mean"]
    for name, k in block.get("kappa", {}).items():
        if k["pooled_kappa"] is not None:
            flat[f"kappa.{name}"] = k["pooled_kappa"]
    return flat
