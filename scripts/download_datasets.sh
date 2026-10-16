#!/usr/bin/env bash
# Download the public datasets of plan §2 into data/raw/ (idempotent and resumable: re-run after an interruption).
#
#   scripts/download_datasets.sh                 # everything below
#   scripts/download_datasets.sh --skip-oil      # only IPC2BNS-Verify and the manifest
#   OIL_COURTS="delhi sikkim" scripts/download_datasets.sh   # a subset of the Open India Law files (pilot)
#   OIL_WORKERS=12 PY=.venv/bin/python scripts/download_datasets.sh
#   SKIP_KATHBATH=1 KATHBATH_LIMIT=500 scripts/download_datasets.sh
#
# 1. Open India Law v2026.08.1 (CC BY 4.0): the 53.6 GB judgment files are NOT downloaded whole. oil_fetch streams them from the mirror
#    named in the dataset README (https://oss-data-in.vaquill.ai, no login) and keeps only the chunks of bail-candidate cases (about 1 GB on
#    disk for all courts); the legislation file is downloaded whole and checked against the published SHA-256. Needs ~1-3 hours on a
#    5 MB/s link, and the python packages `pyarrow` and `requests` (pip install -e '.[data]').
# 2. IPC2BNS-Verify (MIT), pinned to a commit: the concordance, the section labels and the 1,140-query benchmark (about 4 MB).
# 4. Blocked or optional datasets are NOT fetched; data/raw/MANIFEST.json records why and what a teammate must do
#    (HLDC and Kathbath are gated on Hugging Face: log in there yourself, no token is read or stored by this script).
# Afterwards: `make interim` converts the raw files into data/interim/ (orders.jsonl, statutes.jsonl, concordance_edges.jsonl).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
RAW="${RAW:-data/raw}"
IPC2BNS_REF="${IPC2BNS_REF:-8d3e77024b3693d21ccae39bffb81641329a4900}"
SKIP_OIL=0
for arg in "$@"; do [ "$arg" = "--skip-oil" ] && SKIP_OIL=1; done

mkdir -p "$RAW"

if [ "$SKIP_OIL" = 0 ]; then
  # shellcheck disable=SC2086
  PYTHONPATH=src "$PY" -m vakeel_sahayak.pipelines.oil_fetch --out "$RAW/open_india_law" --workers "${OIL_WORKERS:-8}" ${OIL_COURTS:+--courts $OIL_COURTS}
fi

fetch() {  # fetch <path-in-repo> [optional]
  local rel="$1" dest="$RAW/ipc2bns_verify/$1"
  mkdir -p "$(dirname "$dest")"
  if curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors -C - -o "$dest" \
      "https://raw.githubusercontent.com/MS-406/IPC2BNS-Verify/$IPC2BNS_REF/$rel"; then
    echo "ok   $rel"
  else
    rm -f "$dest"; echo "skip $rel (not available at this commit)"
  fi
}
for f in README.md \
  data/eval_ground_truth/concordance_v1.csv data/eval_ground_truth/validation_report.csv data/eval_ground_truth/CHANGELOG.md \
  data/phase2_cleaned/bns_sections.jsonl data/phase2_cleaned/ipc_sections.jsonl \
  data/phase1_raw/concordance_source_pdfs/concordance_provenance.md data/eval_benchmarks/provenance.md data/eval_benchmarks/benchmark_crpc_bnss.csv \
  phase7/benchmark/master_benchmark.jsonl phase7/benchmark/master_benchmark.csv phase7/data/final/benchmark_stats.json; do
  fetch "$f"
done

# 3. Kathbath Hindi test_known subset from the official object store (the Hugging Face repo is gated and has no test split): the first
#    KATHBATH_LIMIT utterances (default 1000, about 95 MB) plus the Hindi transcript file. Parallel range reads; the store gives about 30 KB/s per connection.
if [ "${SKIP_KATHBATH:-0}" = 0 ]; then
  PYTHONPATH=src "$PY" -m vakeel_sahayak.pipelines.kathbath_fetch --out "$RAW/kathbath" --limit "${KATHBATH_LIMIT:-1000}"
fi

PYTHONPATH=src "$PY" -m vakeel_sahayak.pipelines.raw_manifest --raw "$RAW"
