"""Generic shard runner: starts vLLM inside the script (no long-lived server), processes a shard of about 5 h, saves each case's output as it finishes and resumes from saved progress (plan §17).

`run_shard(job, shard, n_shards, out_dir, time_limit_hours)` runs one named job of configs/eval/runs.yaml on this shard's cases. The
per-case saving, the resume and the run manifest live in `driver.run_cases`; this module validates the request, owns the clock and
maps a job to its systems. `launch(jobs, argv)` is the shared body of the thin runner CLIs (`run_rq1`, `run_ablations`, ...).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

import yaml

from vakeel_sahayak.eval.runners.driver import REPO, load_progress  # noqa: F401  (load_progress is re-exported: the tests use it from here)

BATCH_JOBS = {"qlora"}


def runs_config() -> dict[str, Any]:
    """configs/eval/runs.yaml."""
    return yaml.safe_load((REPO / "configs" / "eval" / "runs.yaml").read_text(encoding="utf-8"))


def default_hours() -> float:
    """The shard length of runs.yaml (`shard_hours`)."""
    return float(runs_config().get("shard_hours", 5))


def run_shard(job: str, shard: int, n_shards: int, out_dir: str, time_limit_hours: float = 5.0) -> int:
    """Run one shard of a named job (see configs/eval/runs.yaml).

    Args:
        job: a job name of runs.yaml (the batch job `qlora` is refused: it is sbatch, not a shard)
        shard: this shard's index, 0 <= shard < n_shards
        n_shards: number of shards
        out_dir: results root; each system writes under `<out_dir>/<job>/outputs/<system>` (README C6)
        time_limit_hours: no new case starts after this many hours

    Returns:
        Cases completed in this call.

    Raises:
        ValueError: unknown or batch job, or a shard index outside the shard count.
        NotImplementedError: the job's case set or arm is not built yet (the message says which).
    """
    jobs = runs_config()["jobs"]
    if job not in jobs:
        raise ValueError(f"unknown job {job!r}: use one of {sorted(jobs)}")
    if job in BATCH_JOBS or jobs[job].get("where") == "ada-batch":
        raise ValueError(f"{job!r} is a batch job (sbatch), not an interactive shard")
    if n_shards < 1 or not 0 <= shard < n_shards:
        raise ValueError(f"shard {shard} is outside 0..{n_shards - 1}")
    if time_limit_hours <= 0:
        return 0
    deadline = time.monotonic() + time_limit_hours * 3600
    from vakeel_sahayak.eval.runners import jobs as job_table

    return job_table.run_job(job, jobs[job], shard, n_shards, out_dir, deadline)


def launch(jobs: list[str], argv: list[str] | None, description: str) -> int:
    """The body of a runner CLI: `--shard N --n-shards M --out-dir DIR [--hours H]`, then each job as one shard. Returns an exit code."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--hours", type=float, default=None)
    args = ap.parse_args(argv)
    if args.n_shards < 1 or not 0 <= args.shard < args.n_shards:
        ap.error(f"--shard {args.shard} is outside 0..{args.n_shards - 1}")
    hours = float(args.hours) if args.hours is not None else default_hours()
    for job in jobs:
        done = run_shard(job, args.shard, args.n_shards, args.out_dir, hours)
        print(f"{job}: {done} case(s) completed (shard {args.shard}/{args.n_shards})")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI of `scripts/ada/run_shard.sh`: `python -m vakeel_sahayak.eval.runners.shard_runner --job NAME --shard N --n-shards M [--out-dir DIR] [--hours H]` runs one shard of one job of runs.yaml.

    Returns:
        0; a usage error (unknown or batch job, shard outside the range) exits 2 with the message and runs nothing.
    """
    import sys

    ap = argparse.ArgumentParser(prog="shard_runner", description=main.__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--hours", type=float, default=None)
    a = ap.parse_args(argv)
    try:
        done = run_shard(a.job, a.shard, a.n_shards, a.out_dir, float(a.hours) if a.hours is not None else default_hours())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{a.job}: {done} case(s) completed (shard {a.shard}/{a.n_shards})")
    return 0


def start_vllm(model_key: str) -> Any:
    """Launch vLLM in-process; model loaded from node /scratch.

    Args:
        model_key: a model key of configs/models.yaml (a role such as 'agents_14b' or a model name under `llm`)

    Returns:
        Engine handle.

    Raises:
        ValueError: the key is not in configs/models.yaml.
        ModelUnavailable: vLLM is not installed here (it is on Ada).
    """
    from vakeel_sahayak.models.base import ModelUnavailable
    from vakeel_sahayak.models.factory import role_config

    cfg = role_config(model_key)  # raises ValueError for an unknown key
    try:
        from vllm import LLM  # noqa: PLC0415 - started inside the script, never at import time
    except ImportError as exc:
        raise ModelUnavailable("vLLM is not installed: run this on Ada (scripts/ada/*.sh)", "models") from exc
    scratch = Path("/scratch") / "vakeel_sahayak"
    model = str(cfg.get("model") or model_key)
    local = scratch / model.replace("/", "--")
    return LLM(model=str(local if local.exists() else model), tensor_parallel_size=int(cfg.get("tensor_parallel", 1) or 1))


if __name__ == "__main__":
    raise SystemExit(main())
