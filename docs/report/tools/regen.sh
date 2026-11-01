#!/usr/bin/env bash
# Rebuild docs/report/generated/*.tex from the per-case CSVs under docs/results (run from anywhere).
set -euo pipefail
cd "$(dirname "$0")/../../.."
R=docs/results
specs="openai=$R/midsub/openai_v3b/per_case_agreed.csv,$R/midsub/a7/per_case_agreed.csv gemini=$R/midsub/gemini_A/per_case_agreed.csv v1=$R/midsub/v1/per_case_agreed.csv shravani_gem=$R/shravani/gemini_31/per_case_agreed.csv shravani_off=$R/shravani/offline_a10/per_case_agreed.csv"
[ -f $R/midsub/sarvam/per_case_agreed.csv ] && specs="$specs sarvam=$R/midsub/sarvam/per_case_agreed.csv"
python3 docs/report/tools/make_result_tables.py docs/report/generated $specs
