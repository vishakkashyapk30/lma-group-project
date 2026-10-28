#!/bin/bash
#SBATCH -J vs_bge_m3
#SBATCH -A research
#SBATCH --qos=medium
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=12G
#SBATCH --gres=gpu:1
#SBATCH -x gnode069
#SBATCH --time=03:00:00
#SBATCH -o /home2/%u/vs_bge/logs/embed_%j.log
# BGE-M3 vectors for the four vector stores on one RTX 2080 Ti (opt-in side vectors, VS_STORES=bge; docs/handoff/bge-vectors-2026-10-28.md).
#
# Staging (from the laptop, see scripts/ada/stage_bge_m3.sh): ~/vs_bge/{bge_vectors.py, texts/*.texts.jsonl.gz, texts/texts_manifest.json}, and the
# folders ~/vs_bge/logs and ~/vs_bge/outbox. Submit with `sbatch ~/vs_bge/embed_bge_m3.sbatch`.
# Disk facts (docs/handoff/ada-qwen32b.md): compute nodes cannot see /share1; /home2 has well under 1 GB free, so only the texts (about 100 MB), the
# logs and an outbox of at most 4 shards (about 40 MB each) live there; the laptop pulls each shard and deletes it (scripts/ada/pull_bge_shards.sh),
# and the job waits while the outbox is full. Everything else (venv, pip cache, temp files, weights, shards in progress) is on node-local /scratch
# and is removed when the job ends. No token or key is used: the weights come from the public BAAI/bge-m3 repository at a pinned revision.
# A rerun resumes: shards already pulled are listed in ~/vs_bge/received.txt and skipped.
set -uo pipefail
H=$HOME/vs_bge
W=/scratch/$USER/vs_bge_${SLURM_JOB_ID:-manual}
REV=${BGE_REVISION:-5617a9f61b028005a4858fdac845db406aefb181}
R=BAAI/bge-m3
mkdir -p "$W/tmp" "$W/cache" "$W/model/1_Pooling" "$W/out" "$H/outbox" "$H/logs"
trap 'echo "cleanup $(date +%T)"; rm -rf "$W"' EXIT
export PIP_CACHE_DIR="$W/cache/pip" PIP_NO_CACHE_DIR=1 TMPDIR="$W/tmp" XDG_CACHE_HOME="$W/cache" HF_HOME="$W/cache/hf" HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
unset HF_TOKEN HUGGING_FACE_HUB_TOKEN
echo "node=$(hostname) job=${SLURM_JOB_ID:-} start=$(date +%T)"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
df -h "$H" /scratch | tail -2

PY=""
for c in python3.12 python3.11 python3.10 python3 "$HOME/miniforge3/bin/python3"; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' 2>/dev/null; then PY=$c; break; fi
done
[ -n "$PY" ] || PY="$HOME/miniforge3/bin/python3"
echo "python=$PY $($PY --version 2>&1)"
"$PY" -m venv "$W/venv" || { echo "venv failed"; exit 1; }
V="$W/venv/bin"
"$V/pip" -q install -U pip
# PyPI is slow from the nodes (about 5 MB/s) while download.pytorch.org gives about 20 MB/s: torch and its CUDA libraries come from the PyTorch index.
"$V/pip" install --progress-bar off --index-url https://download.pytorch.org/whl/cu128 torch 2>&1 | grep -E "^(Successfully|ERROR)|error" | cut -c1-200
"$V/python" -c "import torch; assert torch.cuda.is_available(); print('torch', torch.__version__, torch.cuda.get_device_name(0))" || { echo "torch/cuda failed"; exit 1; }
# the laptop's versions (the query side of VS_STORES=bge); unpinned if a pin does not install on this Python
"$V/pip" install --progress-bar off "transformers==5.20.2" "sentence-transformers==6.2.0" numpy 2>&1 | grep -E "^(Successfully|ERROR)" | cut -c1-200 \
  || "$V/pip" install --progress-bar off transformers sentence-transformers numpy 2>&1 | grep -E "^(Successfully|ERROR)" | cut -c1-200
"$V/python" -c "import transformers, sentence_transformers, numpy; print('transformers', transformers.__version__, 'st', sentence_transformers.__version__)" || { echo "install failed"; exit 1; }
echo "installed $(date +%T)"

# weights: the files sentence-transformers needs for the dense model, at the pinned revision, LFS files checked against their sha256
curl -s -m 60 "https://huggingface.co/api/models/$R/tree/$REV" > "$W/tree.json"
curl -s -m 60 "https://huggingface.co/api/models/$R/tree/$REV/1_Pooling" > "$W/tree_pool.json"
"$V/python" - "$W" > "$W/files.txt" <<'PY'
import json, sys
w = sys.argv[1]
want = {"config.json", "config_sentence_transformers.json", "modules.json", "sentence_bert_config.json", "pytorch_model.bin",
        "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "1_Pooling/config.json"}
for name in ("tree.json", "tree_pool.json"):
    for x in json.load(open(f"{w}/{name}")):
        if x.get("type") == "file" and x["path"] in want:
            print(x["path"], (x.get("lfs") or {}).get("oid", "-"))
PY
[ "$(wc -l < "$W/files.txt")" -ge 10 ] || { echo "could not list the model files"; cat "$W/files.txt"; exit 1; }
while read -r f oid; do
  for try in 1 2 3 4 5; do curl -sSL -C - --retry 3 -o "$W/model/$f" "https://huggingface.co/$R/resolve/$REV/$f" && break; sleep 5; done
  if [ "$oid" != "-" ]; then [ "$(sha256sum "$W/model/$f" | cut -d' ' -f1)" = "$oid" ] || { echo "BAD sha256 $f"; exit 1; }; fi
done < "$W/files.txt"
echo "weights ready $(date +%T) $(du -sh "$W/model" | cut -f1)"

touch "$H/received.txt"
"$V/python" "$H/bge_vectors.py" embed --texts-dir "$H/texts" --out-dir "$W/out" --outbox "$H/outbox" --outbox-max "${OUTBOX_MAX:-4}" \
  --skip-file "$H/received.txt" --model-dir "$W/model" --model-revision "$REV" --check-n 32 ${EMBED_ARGS:-}
rc=$?
echo "embed exit=$rc end=$(date +%T)"
exit $rc
