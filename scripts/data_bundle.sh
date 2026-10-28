#!/usr/bin/env bash
# Make the team data bundle: checksummed tar parts of everything a teammate would otherwise refetch or rebuild (make data-bundle).
#
#   make data-bundle                 # -> ~/vakeel-data-bundle
#   scripts/data_bundle.sh /path/to/folder          # another folder (must be outside the repository)
#   VS_DATA_DIR=/scratch/data scripts/data_bundle.sh /scratch/bundle
#   PART_SIZE=2G  scripts/data_bundle.sh            # size of one part (default 4G; the Hugging Face limit is 50 GB per file)
#   FORCE=1 scripts/data_bundle.sh                  # rebuild both archives even when nothing changed
#   RAW=0 scripts/data_bundle.sh                    # build only the data archive
#   BGE=0 scripts/data_bundle.sh                    # leave out the optional BGE-M3 side vectors even when data/stores has them
#
# Two archive families, plus an optional third, each written straight into the bundle folder (no scratch copy):
#   data.tar.gz.part-NNN  (gzip)       derived data: interim (with hindi_native.jsonl), stores, testsets, gaps (statutes), eval, raw/MANIFEST.json,
#                                      the Kathbath transcripts and audio index (about 1.5 MB), and bundle_manifest.json (unpacks to data/bundle_manifest.json).
#   raw.tar.part-NNN      (plain tar)  public source data: raw/open_india_law (judgment shards, legislation, sc_metadata.jsonl, SHA256SUMS.json, fetch logs),
#                                      raw/ipc2bns_verify, the full raw/kathbath (with the audio) and raw/MANIFEST.json. Not gzipped: parquet and m4a are already compressed.
#   bge.tar.part-NNN      (plain tar)  optional: the BGE-M3 side vectors data/stores/**/*.bge.sqlite and data/stores/BGE_MANIFEST.json (opt-in VS_STORES=bge,
#                                      about 0.8 GB of fp16, which gzip does not shrink). Built only when they exist; never inside the data archive; installed only with BGE=1.
# Resumable: an archive whose parts exist and whose source list (path, size, mtime) is unchanged since it was built is kept, not rebuilt
# (state files .state-data and .state-raw in the bundle folder; an older data archive without a state file is kept when every source is older than it).
# Left out on purpose: models/ (public weights on their own repos: see MODELS.txt and `make models`), data/cases (private client data), data/openai (spend ledger and cache),
# HLDC (gated, non-commercial licence), data/stores_prev, data/stores_candidate, data/*_sample, .env and any file named like a key, token or secret.
# Nothing is uploaded anywhere: `make data-publish` does that, and only when the owner runs it.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
DATA="$(cd "${VS_DATA_DIR:-data}" && pwd)"
OUT="${1:-${BUNDLE_DIR:-$HOME/vakeel-data-bundle}}"
PART_SIZE="${PART_SIZE:-4G}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
case "$OUT/" in "$(pwd)/"*) echo "refusing: $OUT is inside the repository" >&2; exit 1;; esac
if [ -n "$(ls -A "$OUT" 2>/dev/null)" ] && [ ! -f "$OUT/SHA256SUMS" ] && [ ! -f "$OUT/bundle_manifest.json" ] && [ "${FORCE:-0}" != 1 ]; then
  echo "refusing: $OUT is not empty and is not a bundle folder (FORCE=1 to use it anyway)" >&2; exit 1
fi
rm -f "$OUT"/SHA256SUMS "$OUT"/MODELS.txt "$OUT"/README.md

mapfile -t data_paths < <("$PY" scripts/_data_bundle.py paths "$DATA" data)
mapfile -t raw_paths < <("$PY" scripts/_data_bundle.py paths "$DATA" raw)
mapfile -t bge_paths < <("$PY" scripts/_data_bundle.py paths "$DATA" bge)
[ "${#data_paths[@]}" -gt 0 ] || { echo "nothing to bundle in $DATA" >&2; exit 1; }
"$PY" scripts/_data_bundle.py manifest "$DATA" "$OUT/bundle_manifest.json.new"
mv "$OUT/bundle_manifest.json.new" "$OUT/bundle_manifest.json"
"$PY" scripts/_data_bundle.py models "${VS_MODELS_DIR:-models}" > "$OUT/MODELS.txt"

# build_archive <family> <part prefix> <compressor or cat> <source paths...>: skipped when the parts exist and the source state is unchanged.
build_archive() {
  local fam="$1" prefix="$2" comp="$3"; shift 3
  local state_file="$OUT/.state-$fam" now
  now="$("$PY" scripts/_data_bundle.py state "$DATA" "$fam")"
  if [ "${FORCE:-0}" != 1 ] && ls "$OUT/$prefix"* >/dev/null 2>&1; then
    if [ -f "$state_file" ] && [ "$(cat "$state_file")" = "$now" ]; then
      echo "$fam archive: sources unchanged, keeping the existing parts"; return 0
    fi
    if [ ! -f "$state_file" ] && [ "$fam" = data ] && [ -z "$(cd "$DATA" && find -L "$@" -type f -newer "$OUT/${prefix}000" -print -quit)" ]; then
      echo "$now" > "$state_file"; echo "$fam archive: every source is older than the existing parts, keeping them"; return 0
    fi
  fi
  local need_kb free_kb
  need_kb=$(cd "$DATA" && du -sk "$@" | awk '{s+=$1} END {print int(s)}'); [ "$comp" = cat ] || need_kb=$((need_kb / 2))
  free_kb=$(df -Pk "$OUT" | awk 'NR==2 {print $4}')
  echo "$fam archive: $* (about $((need_kb / 1024)) MB needed, $((free_kb / 1024)) MB free in $OUT)"
  [ "$free_kb" -gt "$need_kb" ] || { echo "not enough free disk in $OUT" >&2; exit 1; }
  rm -f "$state_file" "$OUT/$prefix"*
  local extra=() skip=(); [ "$fam" = data ] && extra=(-C "$OUT" bundle_manifest.json) && skip=(--exclude='*.bge.sqlite' --exclude='BGE_MANIFEST.json')
  tar -C "$DATA" --exclude='*.env' --exclude='*key*' --exclude='*token*' --exclude='*secret*' ${skip[@]+"${skip[@]}"} -cf - "$@" ${extra[@]+"${extra[@]}"} \
    | $comp | split -b "$PART_SIZE" -d -a 3 - "$OUT/$prefix"
  echo "$now" > "$state_file"
}

if command -v pigz >/dev/null 2>&1; then gz="pigz -p 4 -6"; else gz="gzip -6"; fi
build_archive data data.tar.gz.part- "$gz" "${data_paths[@]}"
if [ "${RAW:-1}" != 0 ] && [ "${#raw_paths[@]}" -gt 0 ]; then
  build_archive raw raw.tar.part- cat "${raw_paths[@]}"
else
  echo "raw archive: skipped (RAW=0 or no raw data in $DATA)"; rm -f "$OUT"/raw.tar.part-* "$OUT/.state-raw"
fi
if [ "${BGE:-1}" != 0 ] && [ "${#bge_paths[@]}" -gt 0 ]; then
  build_archive bge bge.tar.part- cat "${bge_paths[@]}"
else
  echo "bge archive: skipped (BGE=0 or no BGE-M3 side vectors in $DATA/stores)"; rm -f "$OUT"/bge.tar.part-* "$OUT/.state-bge"
fi
"$PY" scripts/_data_bundle.py archives "$OUT/bundle_manifest.json" "$OUT"
MODEL_IDS="$("$PY" -c "import sys; sys.path.insert(0, 'scripts'); import _data_check as c; print(', '.join(c.model_ids(c.ROOT / 'configs' / 'models.yaml')))" 2>/dev/null || true)"

cat > "$OUT/README.md" <<CARD
---
license: other
pretty_name: Vakeel-Sahayak.ai data (private team copy)
tags: [legal, india, bail, retrieval]
---
# Vakeel-Sahayak.ai: working and source data (private)

A private team copy of every dataset the LMA group project repository uses, so that no teammate has to refetch from the web. Two archive families (tar parts of at most 4 GB):

- \`data.tar.gz.part-*\` (gzip): the data that is slow to rebuild: \`data/interim\`, \`data/stores\`, \`data/testsets\`, \`data/gaps\`, \`data/eval\`, \`data/raw/MANIFEST.json\` and the Kathbath transcripts.
- \`bge.tar.part-*\` (plain tar, optional, only when present): the opt-in BGE-M3 side vectors of the four vector stores (\`data/stores/**/*.bge.sqlite\`, \`data/stores/BGE_MANIFEST.json\`), used only with \`VS_STORES=bge\`; installed with \`BGE=1\`.
- \`raw.tar.part-*\` (plain tar; parquet and m4a are already compressed): the public source data under \`data/raw\`: \`open_india_law\` (judgment shards, legislation, \`sc_metadata.jsonl\`, \`SHA256SUMS.json\`, fetch logs), \`ipc2bns_verify\`, the full \`kathbath\` (with the audio) and \`MANIFEST.json\`.

Install (from the repository root): \`make data-install SRC=<this folder>\` or \`make data-install SRC=hf:<repo>\`; it verifies \`SHA256SUMS\`, unpacks into \`data/\`
(refusing to overwrite without \`--force\`) and checks the counts against \`bundle_manifest.json\`. It installs both archives; \`RAW=0\` (or \`--no-raw\`) skips the raw one to save disk
(the data archive alone is what the pipelines need to run). \`MODELS.txt\` lists the model folders by name and size.

## What is in it, and where it comes from
- Court orders and statutes: derived from Open India Law. "Structured Indian primary-law data from the Open India Law corpus by Vaquill AI
  (https://github.com/Vaquill-AI/open-india-law), used under CC BY 4.0." The judgments and statutes themselves are Government works. \`raw/open_india_law\` holds the shards we kept.
- IPC to BNS concordance: derived from IPC2BNS-Verify (MS-406; MIT per the repository's README badge); \`raw/ipc2bns_verify\` is the repository snapshot.
- Hindi speech test material: Kathbath (AI4Bharat; CC0 packaging, cc-by-4.0 on the Hugging Face card): the Hindi test_known audio (m4a) and transcripts.
- \`interim/hindi_native.jsonl\`: native Hindi High Court bail orders selected from Open India Law (stand-in for HLDC; High Court, not district-court Hindi).
- Test sets T1 to T9, stores, gold labels and evaluation outputs: constructed by the project from the sources above (no manual annotation).

## What is NOT in it, and why
- \`data/cases\`: client case files stay on the lawyer's own machine (privacy rule of the project).
- \`data/openai\` (spend ledger and response cache), \`.env\`, and any file named like a key, token or secret: credentials and private working state.
- Model weights: they are public on their own repositories and are fetched by the project: \`make models-dry-run\` (sizes), then \`make models\` (\`scripts/download_models.sh\`, tiers in \`configs/models.yaml\`).
  T1 models: ${MODEL_IDS:-see configs/models.yaml}.
- HLDC (Kapoor et al., 2022): gated, non-commercial licence (CC BY-NC 4.0); each teammate requests access to Exploration-Lab/IL-TUR on Hugging Face.

This repository is private and for the four team members of the project only. Licences of the sources apply to the derived and raw files.
CARD
(cd "$OUT" && sha256sum $(ls data.tar.gz.part-* raw.tar.part-* bge.tar.part-* 2>/dev/null) bundle_manifest.json MODELS.txt README.md > SHA256SUMS)
echo "bundle written to $OUT:"; (cd "$OUT" && ls -lh && du -sh .)
