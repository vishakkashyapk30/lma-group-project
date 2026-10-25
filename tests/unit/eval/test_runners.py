"""Resumable shard runners (plan §17, §15.9): the eval runners and `shard_runner`.

Plan §17: Ada inference runs only in interactive sessions of at most 6 h, as resumable shards of about 5 h; vLLM starts INSIDE the script
(no long-lived server); every case's output is saved as soon as it finishes; the only sbatch job is QLoRA training. Plan §15.9 / runs.yaml
`statistics.repeats`: Full, B0, B1 and B4 are run 3 times and averaged per case; B2, B3 and the ablations once.

The runners are thin CLIs: each `main(argv)` hands named jobs of configs/eval/runs.yaml to `shard_runner.run_shard(job, shard, n_shards,
out_dir, time_limit_hours)`. The tests replace `run_shard` by a spy.
# ASSUMPTION: CLI flags `--shard N --n-shards M --out-dir DIR` (the Ada scripts pass SHARD and N_SHARDS, scripts/ada/run_shard.sh).
# ASSUMPTION: output of a finished case is `out_dir/<case_id>.json`, and `load_progress(out_dir)` returns the ids of those files.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
from pathlib import Path

import pytest

from vakeel_sahayak.eval.runners import shard_runner

REPO = Path(__file__).resolve().parents[3]
RUNNERS_DIR = REPO / "src" / "vakeel_sahayak" / "eval" / "runners"

# runner module -> jobs of configs/eval/runs.yaml it launches (plan §15, §17)
RUNNER_JOBS = {
    "run_rq1": ["rq1_full", "rq1_b2_b3", "rq1_b0l_b0s_b6"],  # RECONCILED: job 5 (B0L, B0S, B6) is a job of the evaluation plan 7.2
    "run_ablations": ["ablations", "a5_extractors", "a10_knockouts"],
    "run_rq2": ["rq2_vision", "rq2_full"],
    "run_features": ["f2_change_sets", "f1_f5_f6", "f3_baselines", "f4_nocache"],
    "run_tool_calling": ["t6_tool_calling"],
    "run_safety": ["t7_safety"],
    "run_variants": __import__("importlib").import_module("vakeel_sahayak.eval.runners.run_variants").JOBS,  # RECONCILED: VI-03 adds a runner for the variant and hosted-block jobs of runs.yaml
}


class SpyShard:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, job, shard, n_shards, out_dir, time_limit_hours=5.0):
        self.calls.append({"job": job, "shard": shard, "n_shards": n_shards, "out_dir": out_dir, "time_limit_hours": time_limit_hours})
        return 1


@pytest.fixture()
def spy(monkeypatch):
    s = SpyShard()
    monkeypatch.setattr(shard_runner, "run_shard", s)
    for name in RUNNER_JOBS:  # a runner may have imported the function by name
        mod = importlib.import_module(f"vakeel_sahayak.eval.runners.{name}")
        if hasattr(mod, "run_shard"):
            monkeypatch.setattr(mod, "run_shard", s)
    return s


def main_of(name: str):
    return importlib.import_module(f"vakeel_sahayak.eval.runners.{name}").main


# ---------------------------------------------------------------- static facts (pass today)
def test_run_shard_signature_and_the_five_hour_default(load_yaml):
    """run_shard(job, shard, n_shards, out_dir, time_limit_hours=5.0): the default is runs.yaml's shard_hours."""
    params = inspect.signature(shard_runner.run_shard).parameters
    assert list(params) == ["job", "shard", "n_shards", "out_dir", "time_limit_hours"]
    assert params["time_limit_hours"].default == load_yaml("eval/runs.yaml")["shard_hours"] == 5


def test_a_five_hour_shard_fits_a_six_hour_interactive_session_with_loading_time(load_yaml):
    """5 h + 20-30 min model loading from /scratch stays below the 6-hour interactive limit (plan §17)."""
    assert load_yaml("eval/runs.yaml")["shard_hours"] + 0.5 <= 6


@pytest.mark.parametrize("runner", sorted(RUNNER_JOBS))
def test_every_runner_has_main_argv_returning_int(runner):
    sig = inspect.signature(main_of(runner))
    assert list(sig.parameters) == ["argv"] and sig.parameters["argv"].default is None


def test_runner_job_names_exist_in_runs_yaml_and_cover_every_interactive_job(load_yaml):
    """The runners together cover every Ada interactive job of runs.yaml except the teacher dossiers (scripts/ada/run_teacher_dossiers.sh)
    and the laptop-side part of A10; QLoRA is the one batch job and has no runner."""
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    launched = {j for js in RUNNER_JOBS.values() for j in js}
    assert launched <= set(jobs)
    not_launched = set(jobs) - launched
    assert not_launched == {"teacher_dossiers", "qlora"}
    assert [n for n, j in jobs.items() if j["where"] == "ada-batch"] == ["qlora"]


def test_ada_scripts_follow_the_shard_convention():
    """Every interactive Ada script says vLLM starts inside the script, outputs are saved per case, and takes SHARD N_SHARDS (plan §17)."""
    scripts = [p for p in (REPO / "scripts" / "ada").glob("run_*.sh")]
    assert len(scripts) >= 8
    for p in scripts:
        text = p.read_text(encoding="utf-8")
        assert "INSIDE the Python script" in text and "saved as soon as it finishes" in text and "SHARD N_SHARDS" in text, p.name
        assert "sbatch" not in re.sub(r"#.*", "", text), f"{p.name}: inference must not be a batch job"


@pytest.mark.parametrize("path", sorted(RUNNERS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_runner_modules_import_no_inference_engine_at_top_level(path):
    """vLLM and torch are started inside functions (`start_vllm`), never at import time, so the package imports on a bare install."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"vllm", "torch", "transformers"}


def test_start_vllm_takes_a_model_key_from_models_yaml():
    assert list(inspect.signature(shard_runner.start_vllm).parameters) == ["model_key"]


# ---------------------------------------------------------------- runners launch the right jobs
@pytest.mark.parametrize("runner", sorted(RUNNER_JOBS))
def test_runner_launches_its_jobs_with_the_shard_arguments(spy, tmp_path, runner):
    """`main(['--shard','1','--n-shards','4','--out-dir',DIR])` runs each of the runner's jobs as shard 1 of 4 with the 5-hour limit."""
    code = main_of(runner)(["--shard", "1", "--n-shards", "4", "--out-dir", str(tmp_path)])
    assert code == 0
    assert [c["job"] for c in spy.calls] == RUNNER_JOBS[runner]
    assert all(c["shard"] == 1 and c["n_shards"] == 4 and c["time_limit_hours"] == 5.0 for c in spy.calls)


def test_rq1_runs_the_three_run_systems_and_the_one_run_systems_as_separate_jobs(spy, tmp_path, load_yaml):
    """Plan §15.3/§15.9: Full, B0, B1, B4 x 3 runs; B2 and B3 x 1. They are two jobs so that the repeats differ per system, and each job
    carries its repeat count in runs.yaml."""
    main_of("run_rq1")(["--shard", "0", "--n-shards", "1", "--out-dir", str(tmp_path)])
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    by_job = {c["job"]: jobs[c["job"]] for c in spy.calls}
    assert by_job["rq1_full"]["systems"] == ["full", "b0", "b1", "b4"] and by_job["rq1_full"]["runs"] == 3
    assert by_job["rq1_b2_b3"]["systems"] == ["b2", "b3"] and by_job["rq1_b2_b3"]["runs"] == 1


def test_ablations_run_once_each_on_100_cases(spy, tmp_path, load_yaml):
    """Ablations are single runs (no repeats key) on 100 cases; A5 on 400 inputs (plan §15.4, §17)."""
    main_of("run_ablations")(["--shard", "0", "--n-shards", "1", "--out-dir", str(tmp_path)])
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    assert "runs" not in jobs["ablations"] and jobs["ablations"]["cases"] == 100 and jobs["a5_extractors"]["inputs"] == 400


def test_safety_and_tool_calling_are_three_run_jobs(load_yaml):
    """T6 and T7 are repeated 3 times (pass^3, plan §15.8)."""
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    assert jobs["t6_tool_calling"]["runs"] == 3 and jobs["t7_safety"]["runs"] == 3


def test_repeats_in_the_statistics_block_match_the_job_runs(load_yaml):
    """One source of truth for '3 runs vs 1 run': the statistics.repeats table agrees with the rq1 jobs' `runs`."""
    cfg = load_yaml("eval/runs.yaml")
    repeats = cfg["statistics"]["repeats"]
    full_job = cfg["jobs"]["rq1_full"]
    assert all(repeats[s] == full_job["runs"] for s in full_job["systems"])
    assert repeats["others"] == cfg["jobs"]["rq1_b2_b3"]["runs"] == 1


def test_a_bad_argument_is_a_nonzero_exit_not_a_traceback(spy, tmp_path):
    """# ASSUMPTION: argparse-style failure: SystemExit with a non-zero code (or a non-zero return), and no job is launched."""
    try:
        code = main_of("run_rq1")(["--shard", "5", "--n-shards", "4", "--out-dir", str(tmp_path)])
    except SystemExit as exc:
        code = exc.code
    assert code not in (0, None) and spy.calls == []


# ---------------------------------------------------------------- shard_runner: progress, resume, per-case saving
def save_case(out_dir: Path, case_id: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{case_id}.json").write_text(json.dumps({"case_id": case_id}), encoding="utf-8")


def test_load_progress_of_a_missing_or_empty_directory_is_empty(tmp_path):
    """A first session has nothing saved: no error, nothing done."""
    assert shard_runner.load_progress(str(tmp_path / "never_created")) == set()
    (tmp_path / "empty").mkdir()
    assert shard_runner.load_progress(str(tmp_path / "empty")) == set()


def test_load_progress_lists_the_saved_case_ids(tmp_path):
    for cid in ("t1-001", "t1-002", "t1-007"):
        save_case(tmp_path, cid)
    assert shard_runner.load_progress(str(tmp_path)) == {"t1-001", "t1-002", "t1-007"}


def test_a_half_written_output_is_not_counted_as_done(tmp_path):
    """A session killed while writing leaves a truncated file; it must not be treated as finished. # ASSUMPTION: invalid JSON = not done."""
    save_case(tmp_path, "t1-001")
    (tmp_path / "t1-002.json").write_text('{"case_id": "t1-0', encoding="utf-8")
    assert shard_runner.load_progress(str(tmp_path)) == {"t1-001"}


def test_a_zero_hour_limit_completes_nothing_and_saves_nothing(tmp_path):
    """time_limit_hours bounds the shard: with no time left, no case is started and the function returns 0 completed."""
    assert shard_runner.run_shard("t6_tool_calling", 0, 1, str(tmp_path / "out"), time_limit_hours=0.0) == 0
    assert shard_runner.load_progress(str(tmp_path / "out")) == set()


@pytest.mark.parametrize("job", ["no_such_job", "qlora"])
def test_unknown_and_batch_jobs_are_refused(tmp_path, job):
    """Only the interactive jobs of runs.yaml run as shards; QLoRA is the sbatch job (plan §17). # ASSUMPTION: ValueError/KeyError."""
    with pytest.raises((ValueError, KeyError)):
        shard_runner.run_shard(job, 0, 1, str(tmp_path / "out"))


@pytest.mark.parametrize(("shard", "n_shards"), [(4, 4), (-1, 4), (0, 0)])
def test_shard_index_must_be_inside_the_shard_count(tmp_path, shard, n_shards):
    with pytest.raises(ValueError):
        shard_runner.run_shard("t6_tool_calling", shard, n_shards, str(tmp_path / "out"))
