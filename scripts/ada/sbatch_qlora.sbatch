#!/usr/bin/env bash
#SBATCH --job-name=vs-qlora
#SBATCH --account=research
#SBATCH --partition=u22
#SBATCH --qos=medium
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=6G
#SBATCH --time=1-12:00:00
#SBATCH --output=logs/qlora_%j.out
# QLoRA training of the Qwen3-4B extractor (plan §12, §17): the ONLY sbatch job.
# One 2080 Ti per run, at most 1.5 days (well inside the 4-day batch limit), checkpoint every epoch.
# This is training, not inference serving; all LLM/vision inference uses interactive sessions instead.
#
# Submit from the repo root (the repo and data/interim/finetune/{train,dev}.jsonl must be visible to the job; mkdir -p logs first):
#   RUN=0 sbatch --export=ALL,RUN=0 scripts/ada/sbatch_qlora.sbatch      # three runs: RUN=0, 1, 2 (configs/finetune/qlora.yaml `runs: 3`)
# A job killed after epoch 1 resumes from <output>/run$RUN/checkpoints on resubmission (same command).
# Adapter lands in models/extractor-qlora/run$RUN; copy the chosen run to models/extractor-qlora, then package with
#   python -m vakeel_sahayak.finetune.merge_adapter models/extractor-qlora <out_dir>
set -euo pipefail
RUN="${RUN:-0}"
REPO="${SLURM_SUBMIT_DIR:-$PWD}"
W="/scratch/$USER/vs-qlora"
mkdir -p "$W" "$REPO/logs"
trap 'echo cleanup; rm -rf "$W"' EXIT
echo "node=$(hostname) run=$RUN start=$(date +%T)"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Node-local venv. PyPI is slow from the compute nodes, so torch comes from the PyTorch index (cu128) and the rest from PyPI.
python3 -m venv "$W/venv"
"$W/venv/bin/pip" -q install -U pip
"$W/venv/bin/pip" install --progress-bar off --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple \
  torch "transformers>=4.51" "peft>=0.12" "bitsandbytes>=0.43" "accelerate>=0.34" pyyaml
"$W/venv/bin/pip" install --progress-bar off --no-deps -e "$REPO"
"$W/venv/bin/python" - <<'PY'
import torch, transformers, peft, bitsandbytes
assert torch.cuda.is_available(), "no CUDA device"
print("torch", torch.__version__, "transformers", transformers.__version__, "peft", peft.__version__, torch.cuda.get_device_name(0))
PY

# Qwen3-4B weights (Apache-2.0) into node-local scratch; the 2080 Ti job never needs the network after this.
export HF_HOME="$W/hf"
cd "$REPO"
for f in data/interim/finetune/train.jsonl data/interim/finetune/dev.jsonl; do
  [ -s "$f" ] || { echo "missing $f: build it with python -m vakeel_sahayak.finetune.build_dataset"; exit 1; }
done
"$W/venv/bin/python" -m vakeel_sahayak.finetune.train_qlora configs/finetune/qlora.yaml --run "$RUN"
echo "done $(date +%T): adapter in models/extractor-qlora/run$RUN"
