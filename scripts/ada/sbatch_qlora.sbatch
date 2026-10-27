#!/usr/bin/env bash
#SBATCH --job-name=vs-qlora
#SBATCH --account=research
#SBATCH --partition=u22
#SBATCH --qos=medium
#SBATCH --constraint=2080ti
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --exclude=gnode069
#SBATCH --output=slurm_logs/qlora_%j.out
# QLoRA training of the Qwen3-4B extractor (plan §12, §17): the ONLY sbatch job.
# RECONCILED: owner decision 2026-10-27, 4 GPUs for DDP QLoRA (plan §17 said one GPU per run). One task: torchrun starts the 4 processes inside.
# The limit above is the single place for the wall time (<= 36 h, the 4-day QOS maximum is far away); the estimate is 2 to 6 h per run (docs/handoff/finetune.md).
# Medium QOS allows 4 GPUs, 40 CPUs, 125000M per user at once, so the three runs (RUN=0,1,2) go one after another. Ask for modest CPUs and memory: a node with
# 4 free GPUs also needs free CPUs. gnode069 has a broken GPU. This is training, not inference serving.
#
# Nodes have no repo and cannot see /share1; they see $HOME (NFS, about 2 GB free: small files only). Everything big lives on node-local /scratch.
# Inputs come from $HOME/vakeel_qlora/in (scripts/ada/stage_qlora_inputs.sh on the laptop puts them there and prints the submit command):
#   code-<tag>.tar.gz (git archive of the tag), train.jsonl, dev.jsonl, qlora.yaml, stage.env (tag and commit), SHA256SUMS, this script.
# Submit (from $HOME; slurm_logs must exist):  mkdir -p ~/slurm_logs && cd ~ && sbatch --export=ALL,RUN=0 vakeel_qlora/in/sbatch_qlora.sbatch
# After every epoch ONLY the adapter files (about 130 MB) are copied to $HOME/vakeel_qlora/out/run$RUN (refused below 500 MB free there).
# Resubmitting the same command resumes from that copy: it restores the adapter weights and the epoch counter, NOT the optimizer, the LR schedule
# or the RNG (those live only in the /scratch checkpoint, which is deleted at job end). Finish with scripts/ada/fetch_qlora_outputs.sh on the laptop.
set -euo pipefail
RUN="${RUN:-0}"
case "$RUN" in 0|1|2) ;; *) echo "RUN must be 0, 1 or 2 (three seeds), got '$RUN'" >&2; exit 2;; esac
TORCH_SPEC="torch==2.8.0"
BASE_REPO="Qwen/Qwen3-4B"
IN="$HOME/vakeel_qlora/in"
OUT="$HOME/vakeel_qlora/out/run$RUN"
W="/scratch/$USER/vs-qlora/run$RUN"
M="$W/models/Qwen3-4B"
mkdir -p "$W/tmp" "$W/cache" "$M" "$OUT"
# $HOME is NFS with about 2 GB free: pip would cache wheels there and hang. Every cache and temp dir goes to node-local scratch.
export PIP_CACHE_DIR="$W/cache/pip" PIP_NO_CACHE_DIR=1 TMPDIR="$W/tmp" XDG_CACHE_HOME="$W/cache" HF_HOME="$W/cache/hf" \
  TRITON_CACHE_DIR="$W/cache/triton" TORCHINDUCTOR_CACHE_DIR="$W/cache/inductor" TORCH_HOME="$W/cache/torch"
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 NCCL_DEBUG=WARN TORCH_NCCL_ASYNC_ERROR_HANDLING=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
GPUPID=""
cleanup() { echo "cleanup $(date +%T)"; [ -n "$GPUPID" ] && kill "$GPUPID" 2>/dev/null || true; rm -rf "$W"; }
trap cleanup EXIT
echo "node=$(hostname) run=$RUN job=${SLURM_JOB_ID:-none} start=$(date +%T)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
NGPU=$(nvidia-smi -L | wc -l)
[ "$NGPU" -eq 4 ] || { echo "expected 4 GPUs, found $NGPU"; exit 1; }
nvidia-smi topo -m || true   # PCIe or NVLink: the trainer disables NCCL P2P by itself when peer access is missing
FREE_MB=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
echo "free on \$HOME: ${FREE_MB} MB"
[ "$FREE_MB" -ge 500 ] || echo "WARNING: under 500 MB free on \$HOME: adapter copies will be refused (the adapter then exists only on /scratch until the job ends)"

# Inputs: verify what was staged, then unpack the code of the tag.
for f in train.jsonl dev.jsonl qlora.yaml stage.env SHA256SUMS; do [ -s "$IN/$f" ] || { echo "missing $IN/$f: run scripts/ada/stage_qlora_inputs.sh on the laptop"; exit 1; }; done
(cd "$IN" && sha256sum -c SHA256SUMS)
# shellcheck disable=SC1091
. "$IN/stage.env"; export VS_CODE_TAG VS_CODE_SHA
mkdir -p "$W/code" && tar -xzf "$IN"/code-*.tar.gz -C "$W/code"
mkdir -p "$W/code/data/interim/finetune"
cp "$IN/train.jsonl" "$IN/dev.jsonl" "$W/code/data/interim/finetune/"
cp "$IN/qlora.yaml" "$W/code/configs/finetune/qlora.yaml"
echo "code tag=$VS_CODE_TAG sha=$VS_CODE_SHA"

# Node-local venv. PyPI is slow from the nodes (about 5 MB/s), the PyTorch index about 20 MB/s: torch and its CUDA libraries first from there.
python3 -m venv "$W/venv"
"$W/venv/bin/pip" -q install -U pip
"$W/venv/bin/pip" install --progress-bar off --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple "$TORCH_SPEC"
"$W/venv/bin/pip" install --progress-bar off -r "$W/code/scripts/ada/qlora_requirements.txt"
export PYTHONPATH="$W/code/src"
"$W/venv/bin/python" - <<'PY'
import torch, transformers, peft, bitsandbytes
assert torch.cuda.is_available() and torch.cuda.device_count() == 4, "need 4 CUDA devices"
print("torch", torch.__version__, "cuda", torch.version.cuda, "transformers", transformers.__version__, "peft", peft.__version__, "bnb", bitsandbytes.__version__)
print("capability", [torch.cuda.get_device_capability(i) for i in range(4)])
# bitsandbytes smoke on sm_75: a 4-bit NF4 linear in fp16 must run forward and backward on every GPU, or fail here and not after the download.
for i in range(4):
    with torch.cuda.device(i):
        lin = bitsandbytes.nn.Linear4bit(64, 64, compute_dtype=torch.float16, quant_type="nf4").cuda(i)
        x = torch.randn(2, 64, device=f"cuda:{i}", dtype=torch.float16, requires_grad=True)
        lin(x).sum().backward()
print("bnb smoke ok on 4 GPUs")
PY

# Qwen3-4B (Apache-2.0, about 8 GB) from Hugging Face into scratch, file by file, resumable, sha256-verified against the LFS oid (as serve_qwen32b.sh).
REV=$(curl -s -m 60 "https://huggingface.co/api/models/$BASE_REPO" | python3 -c 'import sys, json; print(json.load(sys.stdin)["sha"])')
[ -n "$REV" ] || { echo "could not read the revision of $BASE_REPO"; exit 1; }
export VS_BASE_REVISION="$REV"
echo "base model $BASE_REPO revision $REV"
curl -s -m 60 "https://huggingface.co/api/models/$BASE_REPO/tree/$REV" > "$M/.tree.json"
python3 - "$M" <<'PY' > "$M/.files.txt"
import sys, json
for x in json.load(open(sys.argv[1] + "/.tree.json")):
    if x["type"] == "file" and x["path"] not in (".gitattributes", "README.md"):
        print(x["path"], (x.get("lfs") or {}).get("oid", "-"))
PY
[ -s "$M/.files.txt" ] || { echo "empty file list for $BASE_REPO"; exit 1; }
while read -r f oid; do
  for try in 1 2 3 4 5; do curl -sSL -C - --retry 3 -o "$M/$f" "https://huggingface.co/$BASE_REPO/resolve/$REV/$f" && break; sleep 5; done
  [ -s "$M/$f" ] || { echo "BAD (empty) $f"; exit 1; }
  if [ "$oid" != "-" ]; then [ "$(sha256sum "$M/$f" | cut -d' ' -f1)" = "$oid" ] || { echo "BAD checksum $f"; exit 1; }; fi
done < "$M/.files.txt"
echo "weights ready $(date +%T)"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# GPU memory every 2 minutes into the job log.
( while true; do sleep 120; echo "[gpu] $(date +%T) $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader | tr '\n' ';')"; done ) &
GPUPID=$!

cd "$W/code"
"$W/venv/bin/python" -m vakeel_sahayak.finetune.train_qlora configs/finetune/qlora.yaml --run "$RUN" --dry-run --world-size 4 --export-dir "$OUT"
# DDP over the 4 GPUs: one process per GPU, effective batch kept by the trainer (per-device 1, accumulation 4).
"$W/venv/bin/torchrun" --standalone --nproc_per_node=4 -m vakeel_sahayak.finetune.train_qlora configs/finetune/qlora.yaml \
  --run "$RUN" --export-dir "$OUT" --base-model "$M"

# Verify the adapter that is now on $HOME against the checksums written next to it.
"$W/venv/bin/python" - "$OUT" <<'PY'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1]); meta = json.loads((out / "epoch.json").read_text())
for name, want in meta["sha256"].items():
    got = hashlib.sha256((out / "adapter" / name).read_bytes()).hexdigest()
    assert got == want, f"{name} differs from epoch.json"
print("done", meta["epoch"], "epochs, final =", meta["final"], "; adapter in", out)
PY
echo "finished $(date +%T)"
