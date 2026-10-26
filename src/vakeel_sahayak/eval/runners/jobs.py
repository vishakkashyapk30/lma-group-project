"""Job table of the shard runner: which systems and cases a job of configs/eval/runs.yaml runs (docs/evaluation-plan.md §7.2).

Output layout (README C6): `<out_dir>/runs/<job>/outputs/<system>/<case_id>.json` for the first run of a system and `<system>__run<k>`
for repeat k; a manifest sits beside each output directory. Jobs whose case sets or arms are not built yet raise NotImplementedError.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.runners import driver
from vakeel_sahayak.eval.runners.systems import system_runner
from vakeel_sahayak.orchestration.switches import assert_variant_implemented

ABLATION_MODULES = {
    "A1": "a1_no_dossier", "A2": "a2_no_check_repair", "A3": "a3_no_tools", "A4": "a4_plain_retrieval", "A5": "a5_extractor_variants",
    "A6": "a6_fixed_router", "A7": "a7_free_planner", "A8": "a8_no_sparring", "A9": "a9_neither", "A10": "a10_store_knockouts",
}


# Jobs whose arms depend on code that is not built yet: the dependency is named in the error.
NEEDS = {
    "teacher_dossiers": "the teacher dossier pipeline (EV-08); it has its own Ada script, not a shard",
}
# VI-07: jobs run by the ingestion pipelines (`eval/ingestion/rq2.py`) and the feature evaluations (`eval/features/*`); results land in `<out>/runs/<job>/outputs/<arm>/` (RQ2) or
# `<out>/runs/<job>/outputs/<feature>/<arm>/` (features). F5 and F6 need the export modules (their `run` raises NotImplementedError naming that).
RQ2_JOBS = {"rq2_vision": ["p1", "p2", "p3", "p4"], "rq2_full": ["p5", "p6", "munshi"]}
FEATURE_JOBS = {"f1_f5_f6": ["f1_sparring", "f5_application", "f6_hearing_card"], "f2_change_sets": ["f2_incremental_redraft"], "f3_baselines": ["f3_rights_radar"], "f4_nocache": ["f4_batch_desk"]}
# Jobs run as the existing scripted system tests: job -> (pytest files, repeat count key).
SYSTEM_SUITES = {
    "t7_safety": ["tests/system/test_t7_*.py"],
    "t6_tool_calling": ["tests/system/test_flow2_quick_chat.py"],
}


def _run_system_suite(job: str, cfg: dict[str, Any], shard: int, n_shards: int, out_dir: str, deadline: float) -> int:
    """T6 (quick chat) and T7 (safety) as the scripted `tests/system` scenarios: `runs` repeats, one result file per scenario and run.

    The scenarios run on the fakes of `tests/`; a result file records pass or fail per test id (`<out>/runs/<job>/outputs/system/run<k>/<id>.json`).
    The T6/T7 builders (EV-04) will replace these with generated sets; the scripted tests are the fallback set (split.md vishak.md job map, job 14).
    """
    import glob
    import re
    import subprocess
    import sys
    import time
    import xml.etree.ElementTree as ET

    files = sorted(f for pattern in SYSTEM_SUITES[job] for f in glob.glob(str(driver.REPO / pattern)))
    done_total = 0
    for run_index in range(1, int(cfg.get("runs", 1)) + 1):
        out = Path(out_dir) / "runs" / job / "outputs" / "system" / f"run{run_index}"
        mine = [f for i, f in enumerate(files) if i % n_shards == shard]
        for path in mine:
            stem = re.sub(r"\W+", "_", Path(path).stem)
            if (out / f"{stem}.json").exists() or time.monotonic() >= deadline:
                continue
            xml = out / f"{stem}.xml"
            out.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", path, f"--junitxml={xml}"],
                           cwd=driver.REPO, capture_output=True, text=True, timeout=3600)
            cases = []
            if xml.exists():
                for tc in ET.parse(xml).getroot().iter("testcase"):
                    bad = [c.tag for c in tc if c.tag in {"failure", "error"}]
                    skipped = any(c.tag == "skipped" for c in tc)
                    cases.append({"test": f"{tc.get('classname')}::{tc.get('name')}", "outcome": "fail" if bad else "skip" if skipped else "pass"})
            driver.save_json(out / f"{stem}.json", {"case_id": stem, "run": run_index, "results": cases,
                                                    "passed": sum(c["outcome"] == "pass" for c in cases), "total": len(cases)})
            done_total += 1
    return done_total


def t1_cases_path(gold_source: str | None = None) -> Path:
    """`<testsets>/t1/cases.jsonl` (the 200 T1 cases, in the fixed run order) of the requested gold: `agreed` (default, primary) or `rule` (`t1_rule_only/`);
    `VS_GOLD_SOURCE` sets the default (`testsets/gold_source.py`)."""
    from vakeel_sahayak.testsets.gold_source import t1_dir

    return t1_dir(gold_source) / "cases.jsonl"


def testset_cases_path(testset: str) -> Path:
    """The driver case rows of a test set: `<testsets>/t1/cases.jsonl` for T1; for the others `<testsets>/<t2|t5|t7>/driver_cases.jsonl` (rows with `case_id`,
    `facts` or `facts_text`, `before`, and `bundle` for T2), which the set's builder or an adapter writes. A missing file is a `NotImplementedError` naming the path."""
    from vakeel_sahayak.config import load_config

    key = str(testset or "T1").lower()
    root = Path(load_config().paths.testsets_dir) / key
    if key == "t1":
        root = t1_cases_path().parent  # the gold source in force (VS_GOLD_SOURCE)
    path = root / ("cases.jsonl" if key == "t1" else "driver_cases.jsonl")
    if not path.is_file():
        raise NotImplementedError(f"test set {testset} has no driver case rows at {path}: build the set, or write its rows (case_id, facts, before, bundle) there")
    return path


def first_n_cases(src: Path, n: int | None, dest: Path) -> str:
    """Write the first `n` cases of `src` (the fixed run order) to `dest` and return its path (all cases when n is None)."""
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines[: n or len(lines)]) + "\n", encoding="utf-8")
    return str(dest)


def run_job(job: str, cfg: dict[str, Any], shard: int, n_shards: int, out_dir: str, deadline: float) -> int:
    """Run one shard of a job; returns the cases completed now."""
    if job in {"rq1_full", "rq1_b2_b3", "rq1_b0l_b0s_b6"}:
        return _run_systems(job, cfg, shard, n_shards, out_dir, deadline)
    if job == "ablations":
        return _run_ablations(job, cfg, shard, n_shards, out_dir)
    if job in {"a5_extractors", "a10_knockouts"}:
        key = "A5" if job == "a5_extractors" else "A10"
        mod = importlib.import_module("vakeel_sahayak.eval.ablations." + ABLATION_MODULES[key])
        cases = first_n_cases(t1_cases_path(), cfg.get("inputs") and None, Path(out_dir) / "runs" / job / "cases.jsonl")
        mod.run(cases, str(Path(out_dir) / "runs" / job / "outputs" / key.lower()), shard, n_shards)
        return len(driver.load_progress(str(Path(out_dir) / "runs" / job / "outputs" / key.lower())))
    if job in SYSTEM_SUITES:
        return _run_system_suite(job, cfg, shard, n_shards, out_dir, deadline)
    if job in RQ2_JOBS:
        from vakeel_sahayak.eval.ingestion import rq2

        truth = str(Path(driver.REPO) / "data" / "testsets" / "t2" / "truth.jsonl")
        return sum(rq2.run(arm, truth, out_dir, shard, n_shards, limit=cfg.get("bundles_per_kind"), job=job, page_budget=1500 if arm == "p4" else None)["done"] for arm in RQ2_JOBS[job])
    if job in FEATURE_JOBS:
        for name in FEATURE_JOBS[job]:
            dest = Path(out_dir) / "runs" / job / "outputs" / name
            try:
                importlib.import_module("vakeel_sahayak.eval.features." + name).run(str(dest), shard, n_shards)
            except NotImplementedError as exc:  # F5 and F6: the export modules are not built; the other features of the job still run
                dest.mkdir(parents=True, exist_ok=True)
                (dest / "NOT_RUN.txt").write_text(str(exc), encoding="utf-8")
        return 0
    if job == "gold_source_sweep":
        return run_gold_source_sweep(cfg, out_dir)
    if cfg.get("runner") == "workflow_search":
        raise NotImplementedError(f"job {job!r}: S13 runs through eval/runners/workflow_search.search on dev cases with a model-backed evaluator; none is wired to a hosted or local model yet")
    if cfg.get("systems") and job not in NEEDS:  # a VI-03 job: systems of `systems.system_runner` on the rows of its test set
        return _run_systems(job, cfg, shard, n_shards, out_dir, deadline)
    if job in NEEDS:
        raise NotImplementedError(f"job {job!r} needs {NEEDS[job]}")
    raise NotImplementedError(f"job {job!r}: no arm is wired for it yet")


def run_gold_source_sweep(cfg: dict[str, Any], out_dir: str) -> int:
    """`gold_source_sweep`: rescore the existing outputs against the agreed gold (primary) and the rule-only gold (secondary); no model call, cost 0.

    The scoring modules (`eval/metrics/*`, Harshita's) must exist: a stub raises NotImplementedError naming them. Nothing is written until they do."""
    from vakeel_sahayak.eval.metrics.factor_scores import factor_recall_precision

    try:
        factor_recall_precision([], [], [])
    except NotImplementedError as exc:
        raise NotImplementedError("job 'gold_source_sweep' rescoring needs the scoring modules in vakeel_sahayak/eval/metrics (factor_scores, unsupported_fact, ...; owner Harshita): "
                                  "they are still stubs, so no metric can be recomputed against the other gold") from exc
    raise NotImplementedError("job 'gold_source_sweep': the metrics exist but the rescoring loop (read every <out>/runs/*/outputs/<system>, score against "
                              "testsets.gold_source.load_t1('test', source) for source in cfg['gold_sources'], write <out>/runs/gold_source_sweep/scores_<source>.json) is not written yet")


def _run_systems(job: str, cfg: dict[str, Any], shard: int, n_shards: int, out_dir: str, deadline: float) -> int:
    src = t1_cases_path() if str(cfg.get("testset", "T1")).upper() == "T1" else testset_cases_path(cfg["testset"])
    cases = first_n_cases(src, cfg.get("cases"), Path(out_dir) / "runs" / job / "cases.jsonl")
    total = 0
    for run_index in range(1, int(cfg.get("runs", 1)) + 1):
        for system in cfg["systems"]:
            runner, switches = system_runner(system)
            out = driver.outputs_dir(job, system, run_index, root=out_dir)
            total += driver.run_cases(cases, str(out), system, runner, switches, shard=shard, n_shards=n_shards, seed=run_index, deadline=deadline)
    return total


def _run_ablations(job: str, cfg: dict[str, Any], shard: int, n_shards: int, out_dir: str) -> int:
    cases = first_n_cases(t1_cases_path(), cfg.get("cases"), Path(out_dir) / "runs" / job / "cases.jsonl")
    total = 0
    for ident in cfg["ids"]:
        assert_variant_implemented(ident)  # NotImplementedError naming the variant when its behaviour is not built yet
        mod = importlib.import_module("vakeel_sahayak.eval.ablations." + ABLATION_MODULES[ident])
        out = driver.outputs_dir(job, ident.lower(), 1, root=out_dir)
        before = len(driver.load_progress(str(out)))
        mod.run(cases, str(out), shard, n_shards)
        total += len(driver.load_progress(str(out))) - before
    return total
