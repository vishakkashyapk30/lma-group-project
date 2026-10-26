#!/usr/bin/env bash
# Ablations A1-A4 and A6-A9 on 100 T1 cases (plan §15.4; about 50 node-hours).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_<job>.sh SHARD N_SHARDS
set -euo pipefail
. "$(dirname "$0")/_common.sh"
ada_args "$@"
ada_init
ada_job ablations
