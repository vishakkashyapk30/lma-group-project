#!/bin/bash
# Serve Qwen3-32B-AWQ with vLLM on one 4 x RTX 2080 Ti Ada node (OpenAI-compatible endpoint on port 8000).
# Run it INSIDE an interactive GPU session (plan 17: inference is interactive, the only sbatch job is QLoRA training):
#   srun -A research --qos=medium -p u22 --constraint=2080ti --gres=gpu:4 -c 8 --mem-per-cpu=6G --time=05:30:00 --pty bash
#   bash scripts/ada/serve_qwen32b.sh 2>&1 | tee ~/serve_qwen32b.log      (keep the session open; cleanup runs on exit)
# Compute nodes cannot see /share1 and have no Python packages for this, so the job installs vLLM into node-local /scratch and downloads the
# weights (Apache-2.0, 19.3 GB) from Hugging Face into /scratch at start. Everything under /scratch/$USER/vs is removed when the job ends.
# The log shows the node name and "READY" once the model answers. From the laptop:
#   ssh -N -L 8001:<node>:8000 ada      then   VS_LLM_BACKEND=local with the vLLM URL http://localhost:8001/v1 (see configs/models.yaml, teacher)
set -uo pipefail
W=/scratch/$USER/vs; M=$W/models/Qwen3-32B-AWQ; R=Qwen/Qwen3-32B-AWQ
mkdir -p "$W" "$M"; trap 'echo cleanup; rm -rf "$W"' EXIT
echo "node=$(hostname) start=$(date +%T)"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python3 -m venv "$W/venv" && "$W/venv/bin/pip" -q install -U pip && "$W/venv/bin/pip" -q install "vllm==${VLLM_VERSION:-0.10.2}" || { echo "vllm install failed"; exit 1; }
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
"$W/venv/bin/vllm" serve "$M" --served-model-name qwen3-32b --quantization awq --dtype half --tensor-parallel-size 4 \
  --max-model-len "${MAX_LEN:-8192}" --gpu-memory-utilization 0.90 --port 8000 --enforce-eager > "$W/vllm.log" 2>&1 &
VP=$!
for i in $(seq 1 120); do
  if curl -s -m 5 localhost:8000/v1/models | grep -q qwen3-32b; then echo "READY node=$(hostname) $(date +%T)"; break; fi
  kill -0 $VP 2>/dev/null || { echo "vllm exited"; tail -40 "$W/vllm.log"; exit 1; }
  sleep 15
done
curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen3-32b","messages":[{"role":"user","content":"Name one ground for bail under the BNSS in one sentence."}],"max_tokens":60}' | head -c 600; echo
wait $VP; tail -20 "$W/vllm.log"
