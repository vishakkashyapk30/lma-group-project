#!/usr/bin/env bash
# Choose which T1 gold sits in data/testsets/t1: the agreed gold (primary, default) or the rule-only gold (pre-declared secondary).
# Usage: scripts/swap_gold.sh --primary agreed|rule [--backup DIR] [--testsets DIR] [--no-interim]
# Idempotent. The rule-only gold lives in data/testsets/t1_rule_only (the old t1, moved, never copied); the agreed source is data/testsets/t1_gold_candidate.
# A t1 whose gold is stored nowhere else is only replaced when --backup DIR (not existing yet) is given. Interim gold files follow (originals in data/interim/t1_work/gold/rule_only/).
# Afterwards: .venv/bin/python scripts/prereg_hash.py must print the same blind-set hash as before (the swap changes no id).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
exec "$PY" -m vakeel_sahayak.testsets.gold_source swap "$@"
