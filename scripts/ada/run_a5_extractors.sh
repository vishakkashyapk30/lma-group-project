#!/usr/bin/env bash
# A5: prompted Qwen3-32B extractor on 400 clean and noisy inputs (plan §15.4; about 6 node-hours).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_<job>.sh SHARD N_SHARDS
set -euo pipefail
echo "TODO"; exit 1
