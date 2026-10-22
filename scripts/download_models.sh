#!/usr/bin/env bash
# Resumable model-weight downloader driven by the `weights:` tier table in configs/models.yaml.
#
#   scripts/download_models.sh [T0|T1|T2|T3] [--dry-run] [--yes] [--min-free-gb N]
#   VS_MODELS=T1 scripts/download_models.sh --dry-run
#
# Tier: first argument, else $VS_MODELS, else T1. T0 downloads nothing. Hosted backends (Sarvam, OpenAI) need no weights.
# --skip TEXT leaves out repos whose id contains TEXT. --dry-run lists repos, licences and exact sizes (from the Hugging Face file listing) and the free disk, and downloads nothing.
# A download is refused when free disk would drop below size + margin (--min-free-gb, default 5). Downloads resume (huggingface_hub),
# and hashes are verified against the LFS SHA-256 the Hub publishes. Weights go to $VS_MODELS_DIR (default models/hf); the manifest
# is written to models/MANIFEST.json. A token (HF_TOKEN) is only read from the environment, never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
exec "$PY" -I scripts/_download_models.py "$@"
