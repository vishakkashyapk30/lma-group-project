"""Score run directories: per-case rows, per-system summaries, paired comparisons, Holm over the registered primary families, T4 Rights Radar accuracy.

Statistics follow evaluation plan 5.1 to 5.4: runs are averaged within a case first, the case is the unit; a continuous paired metric gets a paired bootstrap
interval (`eval.stats.bootstrap`) and a Wilcoxon signed-rank p (`eval.stats.wilcoxon`; when scipy is missing the p comes from the bootstrap and `p_source`
says so); binary outcomes (pass^k per case, factor hits per item) get the exact McNemar test and a cluster bootstrap over cases (`stats_extra`); Holm
(`eval.stats.holm`) is applied within the registered primary families only, with the registered family size (a comparison not run counts as p = 1), on the
gold it is called for. Every other comparison is labelled exploratory and is not corrected.
"""

from __future__ import annotations

import statistics
from typing import Any

from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import stats_extra as sx
from vakeel_sahayak.eval.scoring.loader import RunSet, read_events
from vakeel_sahayak.eval.stats.bootstrap import paired_bootstrap_ci
from vakeel_sahayak.eval.stats.holm import holm_bonferroni
from vakeel_sahayak.eval.stats.wilcoxon import wilcoxon_signed_rank

ALPHA = 0.05
N_BOOT = 10000
MIN_SLICE_N = 20

# metric key -> (label, higher is better)
METRICS: dict[str, tuple[str, bool]] = {
    "factor_recall": ("Factor recall (M1)", True),
    "factor_precision_strict": ("Factor precision, strict (M2)", True),
    "factor_precision_lenient": ("Factor precision, lenient (M2)", True),
    "factor_f1": ("Factor F1 (M3)", True),
    "court_discussed_recall": ("Court-discussed factor recall, G5 (M4)", True),
    "unsupported_fact_rate": ("Unsupported-fact rate (M6)", False),
    "recall_at_10": ("Recall@10, G2 (M10)", True),
    "objection_recall": ("Objection recall, G4 (M4)", True),
    "objection_precision": ("Objection precision, G4 (M4)", True),
    "coverage": ("Coverage (M33)", True),
    "tokens": ("Tokens per case (M44)", False),
    "store_calls": ("Store calls per case", False),
    "seconds": ("Seconds per case", False),
    "cost_usd": ("USD per case", False),
}
PAIRED_METRICS = ["factor_recall", "factor_precision_lenient", "factor_f1", "unsupported_fact_rate", "recall_at_10", "objection_recall", "tokens", "store_calls"]

# Registered primary families (evaluation plan 5.3): metrics x comparators, tested as reference minus comparator. Lower-case system ids.
FAMILIES: dict[str, dict[str, Any]] = {
    "F-RQ1-recall": {"claims": "C1", "metrics": ["factor_recall"], "comparators": ["b0", "b0l", "b1", "b2", "b3", "b4"]},
    "F-RQ1-halluc": {"claims": "C2", "metrics": ["unsupported_fact_rate"], "comparators": ["b0", "b0l", "b1", "b2", "b3", "b4"]},
    "F-RQ1-guard": {"claims": "C3", "metrics": ["factor_precision_lenient", "factor_f1"], "comparators": ["b0", "b1", "b4", "b6"]},
    "F-ablate-recall": {"claims": "C10-C12", "metrics": ["factor_recall"], "comparators": ["a1", "a3", "a4", "a6", "a7"]},
    "F-sparring": {"claims": "C7, C8, C28", "metrics": ["objection_recall"], "comparators": ["s9", "s10", "a2", "a8", "a9"]},
    "F-retrieval": {"claims": "C5, C14", "metrics": ["recall_at_10"], "comparators": ["a4", "s4", "s5", "s16"]},
}


def _mean(values: list[float | None]) -> float | None:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    mean, lo, hi = sx.bootstrap_mean_ci(values, N_BOOT)
    return {"mean": mean, "lo": lo, "hi": hi, "n": len(values)}


def score_runs(runs: list[RunSet], cases: list[dict[str, Any]], cfg: cm.ScoreConfig) -> dict[str, Any]:
    """Per-case rows and per-system aggregates for every run set against the gold rows of one slice and one gold source.

    Args:
        runs: the loaded runs (several systems, several runs per system)
        cases: T1 gold rows of the slice
        cfg: scoring choices
    """
    by_case = {str(c["case_id"]): c for c in cases}
    pending: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    for rs in runs:
        for cid, rec in rs.records.items():
            if cid not in by_case:
                excluded[rs.system] = excluded.get(rs.system, 0) + 1
                continue
            row = cm.score_case(by_case[cid], rec, rs.manifest, read_events(rs, cid), cfg, pending)
            rows.append({"system": rs.system, "run": rs.run, **row})
    return {"rows": rows, "pending": pending, "excluded_records": excluded, "by_case": by_case}


def case_means(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float | None]]]:
    """system -> case_id -> metric -> mean over the runs that define it (plan 5.1: runs are averaged within a case first)."""
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        grouped.setdefault(r["system"], {}).setdefault(r["case_id"], []).append(r)
    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for system, cases in grouped.items():
        out[system] = {}
        for cid, rs in cases.items():
            out[system][cid] = {m: _mean([r.get(m) for r in rs]) for m in METRICS}
    return out


def _pass_stats(rows: list[dict[str, Any]], k: int) -> dict[str, Any]:
    runs_of: dict[str, dict[int, bool]] = {}
    for r in rows:
        if r.get("passed") is not None:
            runs_of.setdefault(r["case_id"], {})[r["run"]] = bool(r["passed"])
    n_runs = max((len(v) for v in runs_of.values()), default=0)
    k_eff = max(1, min(k, n_runs))
    results = [[v[i] for i in sorted(v)] for v in runs_of.values() if len(v) >= k_eff]
    flips = sum(1 for v in results if len(set(v)) > 1)
    return {"k": k_eff, "n": len(results), "pass_hat_k": cm.pass_hat_k(results, k_eff) if results else None,
            "pass_at_k": (sum(1 for v in results if any(v[:k_eff])) / len(results)) if results else None,
            "flip_share": (flips / len(results)) if results else None, "pass_rate": (sum(v[0] for v in results) / len(results)) if results else None,
            "per_case": {cid: all(v[i] for i in sorted(v)[:k_eff]) for cid, v in runs_of.items() if len(v) >= k_eff}}


def _run_sd(rows: list[dict[str, Any]]) -> float | None:
    """Mean over cases of the SD of factor recall across runs (run-to-run spread, plan 5.1); None with one run."""
    per: dict[str, list[float]] = {}
    for r in rows:
        if r.get("factor_recall") is not None:
            per.setdefault(r["case_id"], []).append(r["factor_recall"])
    sds = [statistics.stdev(v) for v in per.values() if len(v) > 1]
    return sum(sds) / len(sds) if sds else None


def _item_hits(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """case -> factor -> hit (1 when the factor was argued in at least half of the runs)."""
    acc: dict[str, dict[str, list[int]]] = {}
    for r in rows:
        for factor, hit in r.get("factor_items") or []:
            acc.setdefault(r["case_id"], {}).setdefault(factor, []).append(int(hit))
    return {c: {f: int(sum(v) / len(v) >= 0.5) for f, v in d.items()} for c, d in acc.items()}


def summarise_systems(rows: list[dict[str, Any]], runs: list[RunSet], n_cases: int, cfg: cm.ScoreConfig) -> dict[str, dict[str, Any]]:
    """Per-system block: runs, n, manifest facts, each metric's mean with its bootstrap interval and n, pass^k, G2 coverage, per-factor recall, cost."""
    means = case_means(rows)
    out: dict[str, dict[str, Any]] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for rs in runs:
        manifests.setdefault(rs.system, rs.manifest)
    for system, per_case in means.items():
        srows = [r for r in rows if r["system"] == system]
        metrics = {m: _summary([v[m] for v in per_case.values() if v[m] is not None]) for m in METRICS}
        tok = [v["tokens"] for v in per_case.values() if v["tokens"] is not None]
        metrics["tokens"]["p90"] = float(sorted(tok)[min(len(tok) - 1, int(0.9 * len(tok)))]) if tok else None
        g2_cases = {r["case_id"]: r for r in srows if r["g2_gold_n"]}
        raw_n = sum(r["g2_raw_n"] for r in {r["case_id"]: r for r in srows}.values())
        unres = sum(r["g2_unresolved_n"] for r in {r["case_id"]: r for r in srows}.values())
        per_factor: dict[str, dict[str, int]] = {}
        for factors in _item_hits(srows).values():
            for f, h in factors.items():
                d = per_factor.setdefault(f, {"hits": 0, "n": 0})
                d["hits"] += h
                d["n"] += 1
        man = manifests.get(system, {})
        passed = _pass_stats(srows, 3)
        ps = passed["pass_hat_k"]
        n_passed = sum(1 for v in passed["per_case"].values() if v)
        cost = metrics["cost_usd"]["mean"]
        out[system] = {
            "n_cases": len(per_case), "n_gold_cases": n_cases, "runs": sorted({r["run"] for r in srows}), "metrics": metrics,
            "pass": {k: v for k, v in passed.items() if k != "per_case"}, "run_sd_recall": _run_sd(srows),
            "g2": {"n_cases_with_gold": len(g2_cases), "mean_gold_size": _mean([float(r["g2_gold_n"]) for r in g2_cases.values()]),
                   "resolved_share": (1 - unres / raw_n) if raw_n else None, "retrieved_source": sorted({r["retrieved_source"] for r in srows})},
            "g4_n": len({r["case_id"] for r in srows if r["g4_n"]}), "g7_n": len({r["case_id"] for r in srows if r["g7_n"]}),
            "per_factor": per_factor,
            "cost_per_passed_case": (cost * len(per_case) / n_passed) if (cost is not None and n_passed) else None,
            "pass_hat_k": ps,
            "manifest": {k: man.get(k) for k in ("describe", "variant", "scope", "code_version", "prompt_hash", "config_hash", "gold_source", "gold_sha256", "seed")}
            | {"llm_backend": (man.get("models") or {}).get("llm_backend"), "models_mode": (man.get("models") or {}).get("models_mode"),
               "nli": (man.get("nli") or {}).get("label") or (man.get("nli") or {}).get("backend")},
        }
    return out


# ---------------------------------------------------------------------------------------------------------------- paired comparisons
def _p_value(ref: list[float], other: list[float]) -> tuple[float, str]:
    try:
        return wilcoxon_signed_rank(ref, other), "wilcoxon"
    except ImportError:
        return sx.bootstrap_p_value([a - b for a, b in zip(ref, other, strict=True)], N_BOOT), "bootstrap (scipy missing)"


def paired_comparisons(rows: list[dict[str, Any]], reference: str) -> list[dict[str, Any]]:
    """Reference minus each other system on every paired metric, over the cases both define: mean difference with its paired bootstrap interval, Wilcoxon p
    (or the labelled fallback), d_z; plus, for the pass^k flag and for the pooled gold-factor hits, the exact McNemar test and the cluster bootstrap."""
    means = case_means(rows)
    ref_key = next((s for s in means if s.lower() == reference.lower()), None)
    if ref_key is None:
        return []
    out: list[dict[str, Any]] = []
    by_sys = {s: [r for r in rows if r["system"] == s] for s in means}
    for other in sorted(means, key=str.lower):
        if other == ref_key:
            continue
        for metric in PAIRED_METRICS:
            common = sorted(c for c in means[ref_key] if c in means[other] and means[ref_key][c][metric] is not None and means[other][c][metric] is not None)
            rec: dict[str, Any] = {"reference": ref_key, "comparator": other, "metric": metric, "n": len(common), "higher_is_better": METRICS[metric][1]}
            if len(common) < 2:
                out.append({**rec, "status": "pending" if metric == "unsupported_fact_rate" and not common else "too few cases"})
                continue
            a = [means[ref_key][c][metric] for c in common]
            b = [means[other][c][metric] for c in common]
            mean, lo, hi = paired_bootstrap_ci(a, b, N_BOOT)
            p, src = _p_value(a, b)
            rec.update(status="ok", diff=mean, lo=lo, hi=hi, p=p, p_source=src, dz=sx.cohens_dz([x - y for x, y in zip(a, b, strict=True)]))
            out.append(rec)
        out.extend(_binary_comparisons(ref_key, other, by_sys[ref_key], by_sys[other]))
    return out


def _binary_comparisons(ref: str, other: str, ref_rows: list[dict[str, Any]], oth_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pa, pb = _pass_stats(ref_rows, 3)["per_case"], _pass_stats(oth_rows, 3)["per_case"]
    common = sorted(set(pa) & set(pb))
    if len(common) >= 2:
        m = sx.mcnemar_exact([pa[c] for c in common], [pb[c] for c in common])
        out.append({"reference": ref, "comparator": other, "metric": "pass_per_case (McNemar)", "n": len(common), "status": "ok", "higher_is_better": True,
                    "diff": m["diff"], "p": m["p"], "p_source": "mcnemar exact", "odds_ratio": m["odds_ratio"], "b10": m["b10"], "b01": m["b01"]})
    ha, hb = _item_hits(ref_rows), _item_hits(oth_rows)
    cases = sorted(c for c in ha if c in hb)
    items_a = [[ha[c][f] for f in sorted(ha[c]) if f in hb[c]] for c in cases]
    items_b = [[hb[c][f] for f in sorted(ha[c]) if f in hb[c]] for c in cases]
    flat_a = [x for v in items_a for x in v]
    flat_b = [x for v in items_b for x in v]
    if len(flat_a) >= 2:
        d, lo, hi = sx.cluster_bootstrap_diff(items_a, items_b, N_BOOT)
        m = sx.mcnemar_exact([bool(x) for x in flat_a], [bool(x) for x in flat_b])
        out.append({"reference": ref, "comparator": other, "metric": "factor_hits_pooled (McNemar, cluster bootstrap)", "n": len(flat_a), "n_cases": len(cases),
                    "status": "ok", "higher_is_better": True, "diff": d, "lo": lo, "hi": hi, "p": m["p"], "p_source": "mcnemar exact (items)",
                    "odds_ratio": m["odds_ratio"], "b10": m["b10"], "b01": m["b01"]})
    return out


def holm_families(paired: list[dict[str, Any]], alpha: float = ALPHA) -> dict[str, Any]:
    """Holm-Bonferroni within each registered primary family (plan 5.3), using the registered family size.

    A registered test whose comparator was not run, or whose metric is pending, counts with p = 1 (so the correction is the pre-registered one) and is
    reported as `not run` or `pending`. Each tested comparison gets `family` and `holm_reject`; comparisons outside every family keep `family = None`
    and are exploratory (not corrected). The paired rows are updated in place.
    """
    result: dict[str, Any] = {}
    for p in paired:
        p["family"], p["holm_reject"] = None, None
    for name, fam in FAMILIES.items():
        registered = [(m, c) for m in fam["metrics"] for c in fam["comparators"]]
        pvals: dict[str, float] = {}
        present: dict[str, dict[str, Any]] = {}
        for m, c in registered:
            key = f"{c}|{m}"
            hit = next((p for p in paired if p["metric"] == m and p["comparator"].lower() == c and p["status"] == "ok"), None)
            pvals[key] = hit["p"] if hit else 1.0
            if hit:
                present[key] = hit
        decisions = holm_bonferroni(pvals, alpha)
        tests = []
        for m, c in registered:
            key = f"{c}|{m}"
            if key in present:
                row = present[key]
                better = (row["diff"] > 0) if row["higher_is_better"] else (row["diff"] < 0)
                row["family"], row["holm_reject"] = name, bool(decisions[key])
                row["sign_favours_reference"] = bool(better)
                tests.append({"comparator": row["comparator"], "metric": m, "diff": row["diff"], "p": row["p"], "reject": bool(decisions[key]), "sign_favours_reference": bool(better)})
            else:
                pend = any(p["metric"] == m and p["comparator"].lower() == c for p in paired)
                tests.append({"comparator": c, "metric": m, "reject": None, "status": "pending" if m == "unsupported_fact_rate" and pend else "not run"})
        result[name] = {"claims": fam["claims"], "m_registered": len(registered), "alpha": alpha, "tests": tests}
    return result


# ---------------------------------------------------------------------------------------------------------------- T4 Rights Radar
def rights_summary(arms: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Accuracy per arm (Wilson interval), per rule, false-ELIGIBLE and CHECK rates on T4 scenario records; McNemar of the first arm against the others."""
    out: dict[str, Any] = {"arms": {}, "mcnemar": []}
    for arm, recs in sorted(arms.items()):
        n = len(recs)
        ok = sum(1 for r in recs if r["predicted"] == r["designed"])
        acc, lo, hi = sx.wilson_interval(ok, n)
        fe = sum(1 for r in recs if r["predicted"] == "ELIGIBLE" and r["designed"] != "ELIGIBLE")
        per_rule = {}
        for rule in sorted({r["rule"] for r in recs}):
            rr = [r for r in recs if r["rule"] == rule]
            per_rule[rule] = {"n": len(rr), "accuracy": sum(1 for r in rr if r["predicted"] == r["designed"]) / len(rr)}
        out["arms"][arm] = {"n": n, "accuracy": acc, "lo": lo, "hi": hi, "false_eligible": fe, "false_eligible_rate": fe / n if n else None,
                            "false_eligible_upper_95": (3 / n) if fe == 0 and n else None, "check_rate": (sum(1 for r in recs if r["predicted"] == "CHECK") / n) if n else None,
                            "per_rule": per_rule}
    names = sorted(arms)
    first = "radar" if "radar" in arms else (names[0] if names else None)
    for other in names:
        if first is None or other == first:
            continue
        ids = sorted({r["case_id"] for r in arms[first]} & {r["case_id"] for r in arms[other]})
        a = {r["case_id"]: r["predicted"] == r["designed"] for r in arms[first]}
        b = {r["case_id"]: r["predicted"] == r["designed"] for r in arms[other]}
        if ids:
            out["mcnemar"].append({"a": first, "b": other, "n": len(ids), **sx.mcnemar_exact([a[i] for i in ids], [b[i] for i in ids])})
    return out
