#!/usr/bin/env bash
# Build the seven shared stores from data/interim (wraps python -m vakeel_sahayak.pipelines.store_builders.build_all) (plan §5).
# Extra arguments pass through, e.g. --splits data/interim/splits.json --only reasoning citations --embedder auto
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
exec "$PY" -m vakeel_sahayak.pipelines.store_builders.build_all "$@"
