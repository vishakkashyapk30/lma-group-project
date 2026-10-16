#!/usr/bin/env bash
# Build the seven shared stores from data/interim (wraps python -m vakeel_sahayak.pipelines.store_builders.build_all) (plan §5).
# Extra arguments pass through, e.g. --splits data/interim/splits.json --only reasoning citations --embedder auto
#
#   make stores                          # all orders in data/interim/orders.jsonl
#   SAMPLE=2000 make stores              # prove the build on a court-balanced sample first (writes data/stores_sample; see below)
#   EMBEDDER=hashed-ngram make stores    # the hashed embedder (no model download); the default when no embedding model is installed
#
# SAMPLE=N copies N orders (plus statutes.jsonl and concordance_edges.jsonl) to data/interim_sample and builds into data/stores_sample,
# leaving data/stores alone. When data/interim/splits.json exists (written by `make interim`) the test orders and same-FIR orders are
# left out of every store (plan §2); pass --splits to use another file.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
args=("$@")
has_flag() { for a in "${args[@]:-}"; do [ "$a" = "$1" ] && return 0; done; return 1; }
if [ -n "${EMBEDDER:-}" ] && ! has_flag --embedder; then args+=(--embedder "$EMBEDDER"); fi
if [ -f data/interim/splits.json ] && ! has_flag --splits; then args+=(--splits data/interim/splits.json); fi
if [ -n "${SAMPLE:-}" ]; then
  "$PY" -m vakeel_sahayak.pipelines.oil_ingest sample --out data/interim --sample-out data/interim_sample --n "$SAMPLE"
  exec "$PY" -m vakeel_sahayak.pipelines.store_builders.build_all --interim data/interim_sample --out data/stores_sample "${args[@]}"
fi
exec "$PY" -m vakeel_sahayak.pipelines.store_builders.build_all "${args[@]}"
