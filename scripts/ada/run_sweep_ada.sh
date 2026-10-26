#!/usr/bin/env bash
# Phase of the pre-freeze dev-set sweep that runs on Ada (configs/eval/sweep_dev.yaml, phase 4 by default: Qwen3-4B, free of API credits), one shard per interactive session.
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_sweep_ada.sh SHARD N_SHARDS   (PHASE=4 ARMS=S2,S6 bash scripts/ada/run_sweep_ada.sh 0 4)
# Calls: python scripts/sweep_dev.py run --phase $PHASE --backend ada --shards $N --shard-index $SHARD [--arms $ARMS]; outputs under data/eval/dev_runs_ada (out_roots of the yaml).
set -euo pipefail
. "$(dirname "$0")/_common.sh"
ada_args "$@"
ada_init
PHASE="${PHASE:-4}"
"$PY" scripts/sweep_dev.py run --phase "$PHASE" --backend ada --shards "$N" --shard-index "$SHARD" --parallel 1 ${ARMS:+--arms "$ARMS"}
