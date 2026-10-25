#!/usr/bin/env bash
# Make the team data bundle: compressed, checksummed tar parts of what a teammate cannot rebuild cheaply (make data-bundle).
#
#   make data-bundle                 # -> ~/vakeel-data-bundle
#   scripts/data_bundle.sh /path/to/folder          # another folder (must be outside the repo)
#   VS_DATA_DIR=/scratch/data scripts/data_bundle.sh /scratch/bundle
#   PART_SIZE=500M  scripts/data_bundle.sh          # size of one part (default 1G)
#
# Included (under data/): interim, stores, testsets, gaps, eval, raw/MANIFEST.json.
# Left out on purpose: models/ (weights: see MODELS.txt and `make models`), data/cases (private client data), data/openai (spend ledger and cache),
# data/raw (public, re-downloadable), data/stores_prev, data/stores_candidate, data/*_sample, .env and anything named like a key or token.
# Nothing is uploaded anywhere: `make data-publish` does that, and only when the owner runs it.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
DATA="$(cd "${VS_DATA_DIR:-data}" && pwd)"
OUT="${1:-${BUNDLE_DIR:-$HOME/vakeel-data-bundle}}"
PART_SIZE="${PART_SIZE:-1G}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
case "$OUT/" in "$(pwd)/"*) echo "refusing: $OUT is inside the repository" >&2; exit 1;; esac
if [ -n "$(ls -A "$OUT" 2>/dev/null)" ] && [ "${FORCE:-0}" != 1 ]; then echo "refusing: $OUT is not empty (FORCE=1 to overwrite)" >&2; exit 1; fi
rm -f "$OUT"/data.tar.*.part-* "$OUT"/SHA256SUMS "$OUT"/bundle_manifest.json "$OUT"/MODELS.txt "$OUT"/README.md

paths=()
for d in interim stores testsets gaps eval; do [ -d "$DATA/$d" ] && paths+=("$d"); done
[ -f "$DATA/raw/MANIFEST.json" ] && paths+=("raw/MANIFEST.json")
[ "${#paths[@]}" -gt 0 ] || { echo "nothing to bundle in $DATA" >&2; exit 1; }

need_kb=$(du -sk "${paths[@]/#/$DATA/}" | awk '{s+=$1} END {print int(s/2)}')   # compressed size is under half of the source for these files
free_kb=$(df -Pk "$OUT" | awk 'NR==2 {print $4}')
echo "bundling ${paths[*]} from $DATA (about $((need_kb / 1024)) MB needed, $((free_kb / 1024)) MB free in $OUT)"
[ "$free_kb" -gt "$need_kb" ] || { echo "not enough free disk in $OUT" >&2; exit 1; }

"$PY" scripts/_data_bundle.py manifest "$DATA" "$OUT/bundle_manifest.json"
"$PY" scripts/_data_bundle.py models "${VS_MODELS_DIR:-models}" > "$OUT/MODELS.txt"
if command -v pigz >/dev/null 2>&1; then gz=(pigz -p 4 -6); else gz=(gzip -6); fi
tar -C "$DATA" --exclude='*.env' --exclude='*key*' --exclude='*token*' --exclude='*secret*' -cf - "${paths[@]}" \
  | "${gz[@]}" | split -b "$PART_SIZE" -d -a 3 - "$OUT/data.tar.gz.part-"

cat > "$OUT/README.md" <<'CARD'
---
license: other
pretty_name: Vakeel-Sahayak.ai working data (private team copy)
tags: [legal, india, bail, retrieval]
---
# Vakeel-Sahayak.ai: derived working data (private)

A private team copy of the data that cannot be rebuilt cheaply (the full rebuild takes hours): `data/interim`, `data/stores`, `data/testsets`,
`data/gaps`, `data/eval` and `data/raw/MANIFEST.json` of the LMA group project repository, as compressed tar parts.

Install (from the repository root): `make data-install SRC=<this folder>` or `make data-install SRC=hf:<repo>`; it verifies `SHA256SUMS`,
unpacks into `data/` (refusing to overwrite without `--force`) and checks the row counts against `bundle_manifest.json`.
`MODELS.txt` lists the model folders by name and size; the weights are not here (`make models`).

## What is in it, and where it comes from
- Court orders and statutes: derived from Open India Law. "Structured Indian primary-law data from the Open India Law corpus by Vaquill AI
  (https://github.com/Vaquill-AI/open-india-law), used under CC BY 4.0." The judgments and statutes themselves are Government works.
- IPC to BNS concordance: derived from IPC2BNS-Verify (MS-406; MIT per the repository's README badge).
- Hindi speech test material: derived from Kathbath (AI4Bharat; CC0 packaging, cc-by-4.0 on the Hugging Face card).
- Test sets T1 to T9, stores, gold labels and evaluation outputs: constructed by the project from the sources above (no manual annotation).
- NOT included: HLDC (Kapoor et al., 2022; gated, non-commercial licence), model weights, client case files, API keys or tokens.

This repository is private and for the four team members of the project only. Licences of the sources apply to the derived files.
CARD
(cd "$OUT" && sha256sum data.tar.gz.part-* bundle_manifest.json MODELS.txt README.md > SHA256SUMS)
echo "bundle written to $OUT:"; (cd "$OUT" && ls -lh && du -sh .)
