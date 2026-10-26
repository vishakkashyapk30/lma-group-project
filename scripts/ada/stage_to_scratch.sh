#!/usr/bin/env bash
# Copy model weights and pseudonymised/public data to node /scratch at session start (plan §17). Never copy raw client files.
# Usage: stage_to_scratch.sh MODEL_KEY...        MODEL_KEY is a folder name under $VS_ADA_MODELS (default /share1/$USER/vakeel-sahayak/models), for example Qwen3-32B-AWQ
# Env: STAGE_DATA=1 also copies data/testsets, data/stores and data/interim/gold_candidate (public court text and built stores only); SCRATCH (default /scratch/$USER/vs).
# data/cases and data/raw are refused by name: they may hold client files.
set -euo pipefail
[ "$#" -ge 1 ] || [ "${STAGE_DATA:-0}" = 1 ] || { echo "usage: $0 MODEL_KEY...   (STAGE_DATA=1 to stage the public data too)" >&2; exit 2; }
REPO="${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
M="${VS_ADA_MODELS:-/share1/$USER/vakeel-sahayak/models}"
S="${SCRATCH:-/scratch/$USER/vs}"
mkdir -p "$S/models"
for key in "$@"; do
  case "$key" in */*|..*) echo "MODEL_KEY must be a folder name, got $key" >&2; exit 2;; esac
  [ -d "$M/$key" ] || { echo "no $M/$key (fetch it first: scripts/ada/fetch_qwen32b.sh)" >&2; exit 1; }
  mkdir -p "$S/models/$key"
  cp -ru "$M/$key/." "$S/models/$key/"
  echo "staged model $key -> $S/models/$key"
done
if [ "${STAGE_DATA:-0}" = 1 ]; then
  for d in data/testsets data/stores data/interim/gold_candidate; do
    case "$d" in data/cases*|data/raw*) echo "refusing $d" >&2; exit 2;; esac
    [ -d "$REPO/$d" ] || { echo "skip $d (not present)"; continue; }
    mkdir -p "$S/$d"
    cp -ru "$REPO/$d/." "$S/$d/"
    echo "staged $d -> $S/$d"
  done
  echo "point the run at it with VS_DATA_DIR=$S/data"
fi
du -sh "$S" 2>/dev/null || true
