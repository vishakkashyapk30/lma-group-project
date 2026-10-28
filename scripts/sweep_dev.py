#!/usr/bin/env python3
"""Run the arms of the pre-freeze dev-set sweep (configs/eval/sweep_dev.yaml) as resumable shards of `driver run`.

    bash -c 'set -a; . ./.env; set +a; exec .venv/bin/python scripts/sweep_dev.py run --phase 2 --shards 4 --parallel 2'
    .venv/bin/python scripts/sweep_dev.py run --phase 1 --arms S4,S5 --dry-run

Environment per backend comes from the yaml (`backends.<name>.env`) and is applied AFTER the shell's .env, so `.env`'s `VS_SARVAM=off` cannot win. Keys are never read
or printed here: they reach the driver through the inherited environment only. Outputs: `<out_root>/outputs/<system>` (`__run2` for the second repeat), logs in
`<out_root>/logs/`. A finished arm is skipped (every case file present), a half-done one resumes (the driver skips saved cases). Dev cases only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
STORES = ["law.statutes", "law.concordance", "caselaw.reasoning", "caselaw.citations", "caselaw.similar", "advocacy.arguments", "advocacy.objections"]
EXPAND = {"A10:*": [f"A10:{s}" for s in STORES], "S17*": ["S17", "S17b", "S17c", "S17d"], "P5-P8": ["P5", "P6", "P7", "P8"]}
STUDY_OUT = "studies"  # <out_root>/studies/<study>/ ; M17 (`study: m17`) is a driver-style run under <out_root>/outputs/m17
SKIP_STATUS = ("locked", "blocked", "moved")  # arms that wait for the owner (paid provider locked) or were moved to another backend: never launched
TESTSET_FILES = {"T1": "data/testsets/t1/dev.jsonl", "T2": "data/testsets/t2/driver_cases.jsonl", "T5": "data/testsets/t5/driver_cases.jsonl", "T7": "data/testsets/t7/driver_cases.jsonl"}


def load_cfg() -> dict:
    return yaml.safe_load((REPO / "configs/eval/sweep_dev.yaml").read_text(encoding="utf-8"))


def dir_name(system: str, run_index: int) -> str:
    base = system.lower().replace(":", "_")
    return base if run_index == 1 else f"{base}__run{run_index}"


def cases_file(cfg: dict, root: Path, testset: str, n: int) -> Path:
    """The first n rows of the test set's case file, written once under <root>/cases/."""
    src = REPO / TESTSET_FILES[testset.upper()]
    rows = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    dest = root / "cases" / f"{testset.lower()}_{n}.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_text("\n".join(rows[:n]) + "\n", encoding="utf-8")
    return dest


def n_done(out: Path, cases: Path) -> int:
    ids = [json.loads(ln).get("case_id") for ln in cases.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return sum((out / f"{i}.json").exists() for i in ids)


def jobs_for(cfg: dict, args: argparse.Namespace) -> list[dict]:
    jobs = []
    wanted = {a.lower() for a in args.arms.split(",")} if args.arms else None
    for arm in cfg["arms"]:
        cap = getattr(args, "n", None)
        arm = dict(arm, **({"n": min(int(arm["n"]), cap)} if cap else {}))
        if arm["phase"] != args.phase or (arm.get("status") == "done" and not getattr(args, "include_done", False)):
            continue
        if args.backend and arm["backend"] != args.backend:
            continue
        if str(arm.get("status", "")).split(":")[0].strip() in SKIP_STATUS and not getattr(args, "include_locked", False):
            continue  # never launched; `dirs` still lists them so results produced before the lock can be packed
        if arm.get("kind") == "study":  # not a driver system: an offline study (one job per study, even when several arms name it)
            if wanted and arm["id"].lower() not in wanted and arm["study"].lower() not in wanted:
                continue
            if not any(j["study"] == arm["study"] for j in jobs if "study" in j):
                jobs.append({"system": arm["id"], "study": arm["study"], "arm": arm, "run_index": 1})
            continue
        for system in EXPAND.get(arm["id"], [arm["id"]]):
            if wanted and system.lower() not in wanted and arm["id"].lower() not in wanted:
                continue
            for k in range(1, int(arm.get("runs", 1)) + 1):
                jobs.append({"system": system, "arm": arm, "run_index": k})
    return jobs


def study_command(job: dict, cfg: dict, root: Path, shard: int = 0, n_shards: int = 1) -> tuple[list[str], Path]:
    """The command of a study job and where it writes: `python -m vakeel_sahayak.eval.studies <study> --out <root>/studies/<study> [--n N]`; the m17 removal arm is a driver-style
    run (`--cases` the first `study_n` T1 dev cases, `--out <root>/outputs/m17`, sharded like a driver arm)."""
    arm, study = job["arm"], job["study"]
    base = [sys.executable, "-m", "vakeel_sahayak.eval.studies", study]
    n = arm.get("study_n")
    if study == "m17":
        cases = cases_file(cfg, root, arm.get("testset", "T1"), int(n or arm["n"]))
        out = root / "outputs" / "m17"
        return [*base, "--cases", str(cases), "--out", str(out), "--shard", str(shard), "--n-shards", str(n_shards)], out
    out = root / STUDY_OUT / study
    return [*base, "--out", str(out), *(["--n", str(n)] if n else [])], out


def launch_study(job: dict, cfg: dict, args: argparse.Namespace) -> list[subprocess.Popen]:
    """Start a study (a single process; m17 uses the shards like a driver arm). A finished study (its result file exists) is skipped."""
    arm = job["arm"]
    root = REPO / cfg["out_roots"][arm["backend"]]
    shards = args.shards if job["study"] == "m17" else 1
    env = dict(os.environ)
    env.update({k: str(v) for k, v in cfg["backends"][arm["backend"]]["env"].items()})
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = "2"
    env["PYTHONPATH"] = str(REPO / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    procs = []
    for shard in range(shards):
        if shards > 1 and args.shard_index is not None and shard != args.shard_index:
            continue
        cmd, out = study_command(job, cfg, root, shard, shards)
        if job["study"] != "m17" and (out / f"{job['study']}.json").exists():
            print(f"skip study {job['study']}: {out.name}/{job['study']}.json exists", flush=True)
            return []
        if args.dry_run:
            print(" ".join(cmd))
            continue
        log = open(logs / f"study_{job['study']}_s{shard}.log", "ab")
        procs.append(subprocess.Popen(cmd, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT))
    print(f"started study {job['study']} ({job['system']}) on {arm['backend']}: {len(procs)} process(es)", flush=True)
    return procs


def launch(job: dict, cfg: dict, args: argparse.Namespace) -> list[subprocess.Popen]:
    if "study" in job:
        return launch_study(job, cfg, args)
    arm = job["arm"]
    root = REPO / cfg["out_roots"][arm["backend"]]
    cases = cases_file(cfg, root, arm.get("testset", "T1"), int(arm["n"]))
    out = root / "outputs" / dir_name(job["system"], job["run_index"])
    if n_done(out, cases) >= int(arm["n"]):
        print(f"skip {job['system']} run{job['run_index']}: {out.name} complete", flush=True)
        return []
    env = dict(os.environ)
    env.update({k: str(v) for k, v in cfg["backends"][arm["backend"]]["env"].items()})
    env["OMP_NUM_THREADS"] = env["MKL_NUM_THREADS"] = "2"
    env["PYTHONPATH"] = str(REPO / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")  # run THIS checkout's code (a pinned git worktree), not another editable install
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    procs = []
    for shard in range(args.shards):
        if args.shard_index is not None and shard != args.shard_index:
            continue  # another Ada session runs this shard
        cmd = [sys.executable, "-m", "vakeel_sahayak.eval.runners.driver", "run", "--system", job["system"], "--cases", str(cases), "--out", str(out),
               "--run-index", str(job["run_index"]), "--shard", str(shard), "--n-shards", str(args.shards)]
        if args.dry_run:
            print(" ".join(cmd))
            continue
        log = open(logs / f"{dir_name(job['system'], job['run_index'])}_s{shard}.log", "ab")
        procs.append(subprocess.Popen(cmd, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT))
    print(f"started {job['system']} run{job['run_index']} on {arm['backend']}: {len(procs)} shard(s) -> {out}", flush=True)
    return procs


def locked_backends(cfg: dict, jobs: list[dict]) -> list[str]:
    """Lock messages for the jobs whose backend runs a paid provider that is locked (models/paid_lock.py; unlock VS_ALLOW_PAID, only with the owner's go-ahead)."""
    sys.path.insert(0, str(REPO / "src"))
    from vakeel_sahayak.models.paid_lock import lock_message, paid_unlocked

    out: list[str] = []
    for backend in sorted({j["arm"]["backend"] for j in jobs}):
        env = (cfg["backends"].get(backend) or {}).get("env") or {}
        names = {str(env.get(v, "")).strip().lower() for v in ("VS_LLM_BACKEND", "VS_LABELER", "VS_TEACHER")} - {""}
        out += [f"backend {backend!r} ({n}): " + lock_message(n) for n in sorted(names) if not paid_unlocked(n)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--phase", type=int, required=True)
    r.add_argument("--arms", default=None, help="comma list of system ids (case-insensitive)")
    r.add_argument("--backend", default=None)
    r.add_argument("--shards", type=int, default=4)
    r.add_argument("--shard-index", type=int, default=None, help="run only this shard of --shards (one Ada session per shard: scripts/ada/run_sweep_ada.sh); default: all shards here")
    r.add_argument("--parallel", type=int, default=1, help="arms running at the same time (each with --shards processes)")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--include-done", action="store_true", help="also run arms marked done (the rerun of the baselines on the pinned code)")
    r.add_argument("--n", type=int, default=None, help="cap the number of cases of every arm (budget-limited runs)")
    d = sub.add_parser("dirs", help="print the output directory names of the arms of a phase/backend (used by the packing scripts)")
    d.add_argument("--phase", type=int, required=True)
    d.add_argument("--backend", default=None)
    d.add_argument("--arms", default=None)
    args = ap.parse_args()
    if args.cmd == "dirs":
        for j in jobs_for(load_cfg(), argparse.Namespace(phase=args.phase, backend=args.backend, arms=args.arms, n=None, include_done=False, include_locked=True)):
            if "study" not in j:
                print(dir_name(j["system"], j["run_index"]))
        return 0
    if args.shard_index is not None and not 0 <= args.shard_index < args.shards:
        ap.error(f"--shard-index {args.shard_index} is outside 0..{args.shards - 1}")
    cfg = load_cfg()
    jobs = jobs_for(cfg, args)
    print(f"{len(jobs)} job(s) in phase {args.phase}", flush=True)
    locked = locked_backends(cfg, jobs)
    if locked:
        print("\n".join(locked), file=sys.stderr, flush=True)
        if not args.dry_run:
            return 3
    active: list[tuple[dict, list[subprocess.Popen]]] = []
    queue = list(jobs)
    t0 = time.time()
    while queue or active:
        active = [(j, p) for j, p in active if any(x.poll() is None for x in p)]
        while queue and len(active) < args.parallel:
            j = queue.pop(0)
            procs = launch(j, cfg, args)
            if procs:
                active.append((j, procs))
        if not args.dry_run and (queue or active):
            time.sleep(20)
        elif args.dry_run:
            break
    print(f"phase {args.phase} finished in {(time.time() - t0) / 60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
