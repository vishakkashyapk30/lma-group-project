#!/usr/bin/env bash
# RQ1 main runs: Full, B0, B1, B4 x 3 runs; B2, B3 x 1 on T1 (plan §15.3; about 82 node-hours).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_<job>.sh SHARD N_SHARDS
set -euo pipefail
. "$(dirname "$0")/_common.sh"
ada_args "$@"
ada_init
ada_runner run_rq1
