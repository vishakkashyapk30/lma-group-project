#!/bin/bash
# Architecture search on Sarvam-105B: dev cases t1dev-000..029 only (the holdout 030..049 is not touched here).
# Usage: scripts/midsub/arch-search-sarvam-queue.sh <arm> [<arm> ...]   (arms: full b4 a7 X1..X6 H1 H1m1..H1m6, or S13:<field>=<value>,... grid points)
# Each arm runs as NSHARDS shards (default 2) of the 30 cases; WORKERS (default 4) processes run at a time.
# Paid lock opened for Sarvam only (owner go-ahead 2026-11-01, total cap INR 5000); OpenAI stays locked (never put openai in VS_ALLOW_PAID).
# Run it as a systemd user unit: systemd-run --user --unit=vs-search1 bash scripts/midsub/arch-search-sarvam-queue.sh full b4 a7 X1 X2 X3 X4 X5 X6
# Outputs: data/eval/dev_runs/sarvam_search/outputs/<arm>, logs beside them. Every arm must run on the same committed code (the scorer refuses mixed code stamps).
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W" || exit 1
set -a; . ./.env; set +a
export PYTHONPATH=$W/src OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export VS_ALLOW_PAID=sarvam VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_EXTERNAL=pseudonymised VS_SARVAM=pseudonymised VS_SARVAM_CAP_INR=5000 VS_SARVAM_RUN_CAP_INR=60 VS_NLI=auto
R=$W/data/eval/dev_runs/sarvam_search
PY=${PY:-$W/.venv/bin/python}; [ -x "$PY" ] || PY=python   # a worktree without its own .venv: pass PY=<path to the venv python>
WORKERS=${WORKERS:-4}; NSHARDS=${NSHARDS:-2}
mkdir -p "$R/logs" "$R/cases"
head -30 data/testsets/t1/dev.jsonl > "$R/cases/t1_30.jsonl"
job() { a=$1; s=$2; ns=$3; d=$(echo "$a" | tr 'A-Z:=,' 'a-z___')
  echo "start $a shard $s/$ns $(date +%T)"
  "$PY" -m vakeel_sahayak.eval.runners.driver run --system "$a" --cases "$R/cases/t1_30.jsonl" --out "$R/outputs/$d" --run-index 1 --shard "$s" --n-shards "$ns" >> "$R/logs/$d-s$s.log" 2>&1
  echo "done $a shard $s: $(ls "$R"/outputs/"$d"/t1dev-*.json 2>/dev/null | wc -l) cases so far $(date +%T)"; }
export -f job; export R PY
for a in "$@"; do for ((s = 0; s < NSHARDS; s++)); do echo "$a $s $NSHARDS"; done; done | xargs -P"$WORKERS" -L1 bash -c 'job $0 $1 $2'
echo QUEUE_DONE $(date +%T)
