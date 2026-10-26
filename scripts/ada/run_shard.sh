#!/usr/bin/env bash
# Generic Ada interactive shard runner (plan §17).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_<job>.sh SHARD N_SHARDS
# Calls: python -m vakeel_sahayak.eval.runners.shard_runner --job $JOB --shard $SHARD --n-shards $N
set -euo pipefail
# JOB is the name of a job of configs/eval/runs.yaml (not qlora: that is sbatch): JOB=rq1_full bash scripts/ada/run_shard.sh 0 4
. "$(dirname "$0")/_common.sh"
JOB="${JOB:?set JOB to a job of configs/eval/runs.yaml, for example JOB=rq1_full}"
ada_args "$@"
ada_init
ada_job "$JOB"
