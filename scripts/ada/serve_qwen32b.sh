#!/bin/bash
# Serve Qwen3-32B-AWQ with vLLM on one 4 x RTX 2080 Ti Ada node (OpenAI-compatible endpoint on port 8000).
# Run it INSIDE an interactive GPU session (plan 17: inference is interactive, the only sbatch job is QLoRA training):
#   srun -A research --qos=medium -p u22 --constraint=2080ti -N 1 -n 1 --gres=gpu:4 -c 2 --mem=48G --time=05:30:00 --pty bash   (add -x <bad node> to skip a node with a broken GPU; always -N 1 -n 1, or srun runs the script once per task)
#   bash scripts/ada/serve_qwen32b.sh 2>&1 | tee ~/serve_qwen32b.log      (keep the session open; cleanup runs on exit)
# Compute nodes cannot see /share1 and have no Python packages for this, so the job installs vLLM into node-local /scratch and downloads the
# weights (Apache-2.0, 19.3 GB) from Hugging Face into /scratch at start. Everything under /scratch/$USER/vs is removed when the job ends.
# The log shows the node name and "READY" once the model answers. From the laptop:
#   ssh -N -L 8001:<node>:8000 ada      then   VS_LLM_BACKEND=local with the vLLM URL http://localhost:8001/v1 (see configs/models.yaml, teacher)
set -uo pipefail
W=/scratch/$USER/vs; M=$W/models/Qwen3-32B-AWQ; R=Qwen/Qwen3-32B-AWQ
mkdir -p "$W" "$M" "$W/tmp" "$W/cache"; trap 'echo cleanup; rm -rf "$W"' EXIT
# $HOME is NFS with about 2 GB free: pip would cache the 436 MB vLLM wheel there and hang. Keep every cache and temp file on node-local scratch.
export PIP_CACHE_DIR="$W/cache/pip" PIP_NO_CACHE_DIR=1 TMPDIR="$W/tmp" XDG_CACHE_HOME="$W/cache" HF_HOME="$W/cache/hf" TRITON_CACHE_DIR="$W/cache/triton" VLLM_CACHE_ROOT="$W/cache/vllm" TORCHINDUCTOR_CACHE_DIR="$W/cache/inductor"
echo "node=$(hostname) start=$(date +%T)"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
# PyPI is slow from the compute nodes (about 5 MB/s; the 888 MB torch wheel did not finish in 150 s) while download.pytorch.org gives about 20 MB/s, so torch and the CUDA
# libraries come from the PyTorch index (its +cu128 builds win the version comparison) and everything else from PyPI.
python3 -m venv "$W/venv" && "$W/venv/bin/pip" -q install -U pip && \
  "$W/venv/bin/pip" install --progress-bar off --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple "vllm==${VLLM_VERSION:-0.10.2}" 2>&1 | grep -E "^(Collecting torch|Successfully|ERROR)|error" | cut -c1-160 || { echo "vllm install failed"; exit 1; }
"$W/venv/bin/python" -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__)" || { echo "vllm import failed"; exit 1; }
echo "vllm installed $(date +%T)"
curl -s -m 60 "https://huggingface.co/api/models/$R/tree/main" > "$M/.tree.json"
python3 - "$M" <<'PY' > "$M/.files.txt"
import sys, json
for x in json.load(open(sys.argv[1] + "/.tree.json")):
    if x["type"] == "file":
        print(x["path"], (x.get("lfs") or {}).get("oid", ""))
PY
while read -r f oid; do
  for try in 1 2 3 4 5; do curl -sSL -C - --retry 3 -o "$M/$f" "https://huggingface.co/$R/resolve/main/$f" && break; sleep 5; done
  if [ -n "$oid" ]; then [ "$(sha256sum "$M/$f" | cut -d' ' -f1)" = "$oid" ] || { echo "BAD $f"; exit 1; }; fi
done < "$M/.files.txt"
echo "weights ready $(date +%T)"
export HF_HUB_OFFLINE=1 VLLM_WORKER_MULTIPROC_METHOD=spawn
# Turing (2080 Ti, compute capability 7.5) has no flash attention and no Marlin AWQ kernels, so the default backend may refuse to start. Try, in order:
# the engine's own choice, the Triton attention backend, then the older xformers path (V0 engine). The first one that answers is kept; the log names it.
ATTEMPTS=("" "VLLM_ATTENTION_BACKEND=TRITON_ATTN" "VLLM_USE_V1=0 VLLM_ATTENTION_BACKEND=XFORMERS")
READY=0
for A in "${ATTEMPTS[@]}"; do
  echo "attempt: ${A:-default backend} $(date +%T)"
  env $A "$W/venv/bin/vllm" serve "$M" --served-model-name qwen3-32b --quantization awq --dtype half --tensor-parallel-size 4 \
    --max-model-len "${MAX_LEN:-8192}" --gpu-memory-utilization 0.90 --port 8000 --enforce-eager > "$W/vllm.log" 2>&1 &
  VP=$!
  for i in $(seq 1 120); do
    if curl -s -m 5 localhost:8000/v1/models | grep -q qwen3-32b; then READY=1; echo "READY node=$(hostname) backend=${A:-default} $(date +%T)"; break; fi
    kill -0 $VP 2>/dev/null || { echo "vllm exited with: ${A:-default}"; tail -15 "$W/vllm.log"; break; }
    sleep 15
  done
  [ $READY = 1 ] && break
  kill $VP 2>/dev/null; wait $VP 2>/dev/null; sleep 10
done
[ $READY = 1 ] || { echo "no backend worked on this GPU; see the log above"; exit 1; }
curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen3-32b","messages":[{"role":"user","content":"Name one ground for bail under the BNSS in one sentence."}],"max_tokens":60}' | head -c 600; echo
wait $VP; tail -20 "$W/vllm.log"
