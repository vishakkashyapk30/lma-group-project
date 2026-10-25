#!/usr/bin/env bash
# Construct the test sets T1-T9 (wraps vakeel_sahayak.testsets.*) (plan §15.2). Outputs go to data/testsets/<set>/ (gitignored); each set writes manifest.json.
#
#   scripts/build_testsets.sh                 # T4 T3 T2 T6 T9 T5 T8 (T1 only if data/testsets/t1/cases.jsonl is missing)
#   SETS="t4 t3" scripts/build_testsets.sh    # only these
#   SMALL=1 scripts/build_testsets.sh         # T2 with 12 cases (CI-sized) instead of 100
#   T1=1 scripts/build_testsets.sh            # also (re)build T1 (about 15 minutes; needs data/interim)
#
# Order matters: T6 reads T2 truth, T5 reads T4. T7 (safety scenarios) is not built here.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
SETS="${SETS:-t4 t3 t2 t6 t9 t5 t8}"
export VS_MODELS="${VS_MODELS:-offline}" VS_LLM_BACKEND="${VS_LLM_BACKEND:-offline}"

if [[ "${T1:-0}" == "1" || ! -f data/testsets/t1/cases.jsonl ]]; then
  echo "== T1 =="; "$PY" -m vakeel_sahayak.testsets.t1_court_grounded --update-splits
fi
for s in $SETS; do
  echo "== ${s^^} =="
  case "$s" in
    t2) if [[ "${SMALL:-0}" == "1" ]]; then "$PY" -m vakeel_sahayak.testsets.t2_messy_bundles --small; else "$PY" -m vakeel_sahayak.testsets.t2_messy_bundles; fi ;;
    t3) "$PY" -m vakeel_sahayak.testsets.t3_change_sets ;;
    t4) "$PY" -m vakeel_sahayak.testsets.t4_rights_scenarios ;;
    t5) "$PY" -m vakeel_sahayak.testsets.t5_batch ;;
    t6) "$PY" -m vakeel_sahayak.testsets.t6_chat_questions ;;
    t8) "$PY" -m vakeel_sahayak.testsets.t8_speech ;;
    t9) "$PY" -m vakeel_sahayak.testsets.t9_citation_formats ;;
    t7) echo "T7 is built by its own task (EV-04); skipped" ;;
    *) echo "unknown set: $s" >&2; exit 2 ;;
  esac
done
