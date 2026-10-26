#!/usr/bin/env bash
# Shared helpers of the scripts/ada/run_*.sh wrappers (sourced, never run on its own).
# Inside an interactive Ada GPU session (<= 6 h): the wrapper checks SHARD and N_SHARDS, puts this checkout on PYTHONPATH and hands the shard to the Python runner, which resumes from saved cases.
# Environment (all optional): REPO (this checkout), PY or VS_VENV (the interpreter; default python3), OUT (results root, default $REPO/results), HOURS (shard length, default 5),
# VS_MODELS / VS_LLM_BACKEND / VS_EXTERNAL (default auto / local / off: models served in the session, nothing leaves the node). No key is read or printed here.

ada_args() {
  SHARD="${1:-}"; N="${2:-}"
  case "$SHARD" in ''|*[!0-9]*) echo "usage: $0 SHARD N_SHARDS   (e.g. $0 0 4)" >&2; exit 2;; esac
  case "$N" in ''|*[!0-9]*|0) echo "usage: $0 SHARD N_SHARDS   (e.g. $0 0 4)" >&2; exit 2;; esac
  if [ "$SHARD" -ge "$N" ]; then echo "SHARD $SHARD is outside 0..$((N - 1))" >&2; exit 2; fi
}

ada_init() {
  REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  PY="${PY:-${VS_VENV:+$VS_VENV/bin/python}}"; PY="${PY:-python3}"
  OUT="${OUT:-$REPO/results}"; HOURS="${HOURS:-5}"
  export PYTHONPATH="$REPO/src${PYTHONPATH:+:$PYTHONPATH}"
  export VS_MODELS="${VS_MODELS:-auto}" VS_LLM_BACKEND="${VS_LLM_BACKEND:-local}" VS_EXTERNAL="${VS_EXTERNAL:-off}"
  cd "$REPO"
  echo "node=$(hostname) shard=$SHARD/$N out=$OUT hours=$HOURS backend=$VS_LLM_BACKEND start=$(date +%T)"
}

# ada_runner MODULE: one shard of the jobs of a thin runner (eval/runners/<MODULE>.py), saved per case, resumable.
ada_runner() {
  "$PY" -m "vakeel_sahayak.eval.runners.$1" --shard "$SHARD" --n-shards "$N" --out-dir "$OUT" --hours "$HOURS"
}

# ada_job JOB: one shard of one job of configs/eval/runs.yaml through the generic shard runner.
ada_job() {
  "$PY" -m vakeel_sahayak.eval.runners.shard_runner --job "$1" --shard "$SHARD" --n-shards "$N" --out-dir "$OUT" --hours "$HOURS"
}
