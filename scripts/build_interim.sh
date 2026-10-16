#!/usr/bin/env bash
# Convert data/raw into data/interim (plan §2, §18 week 0): statutes.jsonl, orders.jsonl, concordance_edges.jsonl, splits.json and
# the feasibility report (feasibility_report.json/.md). Streaming and resumable: finished shards are cached in data/interim/.oil_shards.
#   scripts/build_interim.sh [--no-feasibility]
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
export PYTHONPATH=src
RAW="${RAW:-data/raw}"
INTERIM="${INTERIM:-data/interim}"
mkdir -p "$INTERIM"
"$PY" -m vakeel_sahayak.pipelines.oil_ingest statutes --raw "$RAW/open_india_law" --out "$INTERIM"
"$PY" -m vakeel_sahayak.pipelines.oil_ingest orders --raw "$RAW/open_india_law" --out "$INTERIM"
"$PY" - <<PY
from vakeel_sahayak.pipelines.concordance.ipc2bns import build_ipc_bns_edges
n = build_ipc_bns_edges("$RAW/ipc2bns_verify", "$INTERIM/statutes.jsonl", "$INTERIM/concordance_edges.jsonl", strict=False)
print("concordance edges:", n)
PY
if [ "${1:-}" != "--no-feasibility" ]; then
  "$PY" -m vakeel_sahayak.pipelines.oil_ingest feasibility --raw "$RAW/open_india_law" --out "$INTERIM"
fi
