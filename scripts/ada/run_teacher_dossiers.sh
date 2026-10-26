#!/usr/bin/env bash
# Teacher dossiers for about 4K train orders on Qwen3-32B-AWQ (plan §12, §17; about 60 node-hours; skipped if the API teacher is chosen).
# Ada interactive session (<= 6 h; one 4-GPU session per account). Runs a shard of about 5 h with vLLM started INSIDE the Python script (no long-lived server), loading weights from node /scratch (20-30 min).
# Each case's output is saved as soon as it finishes; re-running resumes from saved progress. Usage: run_teacher_dossiers.sh SHARD N_SHARDS
#   srun -A research --qos=medium -p u22 --constraint=2080ti --gres=gpu:4 -c 8 --mem-per-cpu=6G --time=05:30:00 --pty bash
#   bash scripts/ada/run_teacher_dossiers.sh 0 3 2>&1 | tee ~/teacher_0.log
# Input : $ORDERS (default data/interim/finetune/train_orders.jsonl): JSON lines {"doc_id", "facts"}, PUBLIC train orders only.
# Output: $OUT (default data/interim/finetune/dossiers.shard<SHARD>.jsonl), copied back to the repo after every 50 orders and at exit.
set -uo pipefail
SHARD="${1:?usage: run_teacher_dossiers.sh SHARD N_SHARDS}"; N="${2:?usage: run_teacher_dossiers.sh SHARD N_SHARDS}"
REPO="${REPO:-$PWD}"
ORDERS="${ORDERS:-$REPO/data/interim/finetune/train_orders.jsonl}"
OUT="${OUT:-$REPO/data/interim/finetune/dossiers.shard${SHARD}.jsonl}"
W=/scratch/$USER/vs-teacher; M="${VS_ADA_MODELS:-/share1/$USER/vakeel-sahayak/models}/Qwen3-32B-AWQ"
[ -s "$ORDERS" ] || { echo "missing $ORDERS"; exit 1; }
mkdir -p "$W" "$(dirname "$OUT")"
LOCAL_OUT="$W/dossiers.jsonl"; [ -s "$OUT" ] && cp "$OUT" "$LOCAL_OUT"   # resume from what an earlier session saved
sync_out() { [ -s "$LOCAL_OUT" ] && cp "$LOCAL_OUT" "$OUT"; }
trap 'sync_out; echo cleanup; rm -rf "$W"' EXIT
echo "node=$(hostname) shard=$SHARD/$N start=$(date +%T)"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
# Weights: node-local copy of the share1 download (scripts/ada/fetch_qwen32b.sh), 19 GB.
if [ -d "$M" ]; then mkdir -p "$W/model" && cp -r "$M/." "$W/model/"; else echo "weights not found at $M: run scripts/ada/fetch_qwen32b.sh first"; exit 1; fi
python3 -m venv "$W/venv" && "$W/venv/bin/pip" -q install -U pip && \
  "$W/venv/bin/pip" install --progress-bar off --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple "vllm==${VLLM_VERSION:-0.10.2}" pyyaml 2>&1 | grep -E "^(Successfully|ERROR)|error" | cut -c1-160
"$W/venv/bin/pip" install --progress-bar off --no-deps -e "$REPO" pydantic >/dev/null 2>&1 || "$W/venv/bin/pip" install -q -e "$REPO"
"$W/venv/bin/python" -c "import vllm; print('vllm', vllm.__version__)" || { echo "vllm import failed"; exit 1; }
# Teacher = Qwen3-32B-AWQ in process on 4 GPUs. The facts are public court text; no case file is read. Offline mode must be OFF for real generation.
export HF_HUB_OFFLINE=1 VLLM_WORKER_MULTIPROC_METHOD=spawn VS_MODELS=auto VS_TEACHER=vllm VS_VLLM_MODEL="$W/model" VS_VLLM_TP=4 VS_EXTERNAL=off
unset VS_VLLM_BASE_URL
( while sleep 600; do sync_out; done ) & SYNC=$!
"$W/venv/bin/python" -m vakeel_sahayak.finetune.teacher_dossiers shard "$ORDERS" "$LOCAL_OUT" "$SHARD" "$N"
RC=$?; kill $SYNC 2>/dev/null; sync_out; echo "exit=$RC $(date +%T): $(wc -l < "$OUT") dossiers in $OUT"; exit $RC
