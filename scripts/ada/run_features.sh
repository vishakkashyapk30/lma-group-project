#!/usr/bin/env bash
# Feature evaluations F1, F2, F3 baselines, F4 no-cache, F5, F6 (plan §15.6).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_<job>.sh SHARD N_SHARDS
set -euo pipefail
. "$(dirname "$0")/_common.sh"
ada_args "$@"
ada_init
ada_runner run_features
