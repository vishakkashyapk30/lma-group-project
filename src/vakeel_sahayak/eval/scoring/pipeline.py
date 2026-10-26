"""Score a run directory end to end and write the machine-readable results; the gold-source sweep (job `gold_source_sweep`).

Files written under `<out>/`:
* `score_<gold>.json`: meta (gold source and hash, slice, config, pending metrics), per-system summaries, paired comparisons, Holm decisions, T4 Rights Radar;
* `per_case_<gold>.csv` (and `.parquet` when pyarrow is installed): one row per system, run and case, one column per metric;
* sweep only: `sweep.json` with both golds side by side, the delta of every system metric, and the sign and Holm decision of every family test on both golds.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.scoring import case_metrics as cm
from vakeel_sahayak.eval.scoring import engine
from vakeel_sahayak.eval.scoring.loader import (
    SLICES,
    RunSet,
    discover_rights,
    discover_runs,
    gold_provenance,
    gold_rows,
    resolve_slice_ids,
)

# Metrics that depend on the gold source (plan 5.9: M1 to M4, M22, M36, M40, M46); G2 recall and the run-side columns do not.
GOLD_DEPENDENT = ["factor_recall", "factor_precision_strict", "factor_precision_lenient", "factor_f1", "court_discussed_recall", "objection_recall", "objection_precision"]
CSV_COLUMNS = ["system", "run", "case_id", *engine.METRICS, "passed", "n_errors", "g2_gold_n", "g4_n", "retrieved_source"]


def _json_default(o: Any) -> Any:
    if isinstance(o, set):
        return sorted(o)
    return str(o)


def score_once(runs: list[RunSet], cases: list[dict[str, Any]], gold_source: str, slice_name: str, reference: str, cfg: cm.ScoreConfig,
               rights: dict[str, list[dict[str, Any]]], testsets_dir: str | None = None, excluded_note: dict[str, int] | None = None) -> dict[str, Any]:
    """One scoring pass of the loaded runs against one gold source (see `score_runs`, `summarise_systems`, `paired_comparisons`, `holm_families`)."""
    scored = engine.score_runs(runs, cases, cfg)
    rows = scored["rows"]
    systems = engine.summarise_systems(rows, runs, len(cases), cfg)
    paired = engine.paired_comparisons(rows, reference)
    families = engine.holm_families(paired)
    prov = gold_provenance(gold_source, testsets_dir)
    manifests_gold = sorted({str(rs.manifest.get("gold_source")) for rs in runs if rs.manifest.get("gold_source")})
    meta = {
        "gold_source": gold_source, "gold_sha256": prov.get("gold_sha256"), "gold_dir": prov.get("gold_dir"), "slice": slice_name, "n_gold_cases": len(cases),
        "reference": reference, "config": cfg.as_dict(), "pending": scored["pending"], "excluded_records": scored["excluded_records"], "systems_in_runs": sorted({r.system for r in runs}),
        "run_manifests_gold_source": manifests_gold, "min_slice_n": engine.MIN_SLICE_N, "alpha": engine.ALPHA, "n_boot": engine.N_BOOT,
        "models_modes": sorted({str((r.manifest.get("models") or {}).get("models_mode")) for r in runs}),
    }
    return {"meta": meta, "systems": systems, "paired": paired, "families": families, "rights": engine.rights_summary(rights) if rights else None, "per_case": rows}


def write_per_case(path_base: Path, rows: list[dict[str, Any]]) -> None:
    """`per_case_<gold>.csv` (always) and `.parquet` (when pyarrow is installed)."""
    with path_base.with_suffix(".csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_COLUMNS})
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist([{k: r.get(k) for k in CSV_COLUMNS} for r in rows]), str(path_base.with_suffix(".parquet")))
    except ImportError:
        pass


def score_command(runs_dir: str, out: str, *, gold_source: str = "agreed", slice_name: str = "dev", reference: str = "full", testsets_dir: str | None = None,
                  open_blind: bool = False, cfg: cm.ScoreConfig | None = None, lock: Path | None = None, check_tag: bool = True) -> dict[str, Any]:
    """Score `runs_dir` against one gold source (`agreed`, `rule`) or both (`both`: the sweep). Returns the result dict(s) after writing the files.

    Raises `BlindSliceError` for the blind slice unless the flag, the freeze tag and an absent lock file allow it (the check happens after the runs are
    loaded and before any blind id is read, so a bad run directory does not burn the one opening).
    """
    if slice_name not in SLICES:
        raise ValueError(f"slice must be one of {SLICES}")
    cfg = cfg or cm.ScoreConfig()
    runs = discover_runs(runs_dir)
    if not runs:
        raise FileNotFoundError(f"no run (a directory with MANIFEST.json and case files) found under {runs_dir}")
    rights = discover_rights(runs_dir)
    sources = ["agreed", "rule"] if gold_source == "both" else [gold_source]
    ids = resolve_slice_ids(slice_name, sources[0], testsets_dir, open_blind=open_blind, lock=lock, check_tag=check_tag)
    outd = Path(out)
    outd.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for src in sources:
        cases = gold_rows(slice_name, ids, src, testsets_dir)
        res = score_once(runs, cases, src, slice_name, reference, cfg, rights, testsets_dir)
        results[src] = res
        (outd / f"score_{src}.json").write_text(json.dumps(res, indent=1, default=_json_default), encoding="utf-8")
        write_per_case(outd / f"per_case_{src}", res["per_case"])
    if gold_source == "both":
        sweep = sweep_delta(results["agreed"], results["rule"])
        (outd / "sweep.json").write_text(json.dumps(sweep, indent=1, default=_json_default), encoding="utf-8")
        results["sweep"] = sweep
    return results


def sweep_delta(agreed: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """The gold-source sensitivity analysis (evaluation plan 5.9): the same outputs scored against both golds, the delta, and robustness of each family test.

    A family test is `robust` when its sign (which system is better) and its Holm decision are the same on both golds; where they differ the primary
    (agreed) stays the headline. The sweep adds no test to any family: the Holm decisions are the ones each gold gets within the registered family.
    """
    systems: dict[str, Any] = {}
    for name, a in agreed["systems"].items():
        r = rule["systems"].get(name)
        if r is None:
            continue
        entry = {}
        for m in GOLD_DEPENDENT:
            am, rm = a["metrics"][m], r["metrics"][m]
            entry[m] = {"agreed": am, "rule": rm, "delta": (am["mean"] - rm["mean"]) if am["mean"] is not None and rm["mean"] is not None else None}
        systems[name] = entry
    tests = []
    for fname, fam in agreed["families"].items():
        rfam = rule["families"].get(fname, {"tests": []})
        for t in fam["tests"]:
            if t.get("reject") is None:
                continue
            other = next((x for x in rfam["tests"] if x["comparator"].lower() == t["comparator"].lower() and x["metric"] == t["metric"] and x.get("reject") is not None), None)
            if other is None:
                continue
            same_sign = t["sign_favours_reference"] == other["sign_favours_reference"]
            tests.append({"family": fname, "claims": fam["claims"], "comparator": t["comparator"], "metric": t["metric"],
                          "agreed": {k: t[k] for k in ("diff", "p", "reject", "sign_favours_reference")},
                          "rule": {k: other[k] for k in ("diff", "p", "reject", "sign_favours_reference")},
                          "robust": bool(same_sign and t["reject"] == other["reject"])})
    return {"agreed": {"gold_sha256": agreed["meta"]["gold_sha256"], "n_gold_cases": agreed["meta"]["n_gold_cases"]},
            "rule": {"gold_sha256": rule["meta"]["gold_sha256"], "n_gold_cases": rule["meta"]["n_gold_cases"]},
            "slice": agreed["meta"]["slice"], "systems": systems, "family_tests": tests, "gold_dependent_metrics": GOLD_DEPENDENT}
