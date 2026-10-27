#!/usr/bin/env bash
# The phase-2 OpenAI ablation arms of the pre-freeze dev-set sweep, to be run by a teammate with HIS OWN OpenAI key and ledger (docs/handoff/sweep-openai-teammate.md).
#
#   scripts/sweep_openai_block.sh plan                                  # arms, cases and estimated USD (calls no model, needs no key)
#   VS_OPENAI_CAP_USD=2.50 scripts/sweep_openai_block.sh run            # run the not-yet-done arms in priority order until done or the cap is reached
#   VS_OPENAI_CAP_USD=2.50 ARMS=A2,A8 SHARDS=2 scripts/sweep_openai_block.sh run
#   scripts/sweep_openai_block.sh pack                                  # package the small result files into sweep-openai-<date>.tar.gz and print the upload command
#
# Prerequisites: `make setup`, `make data` (data/testsets/t1 and data/stores), OPENAI_API_KEY in your own untracked .env (never the owner's).
# Resumable: finished cases and finished arms are skipped (arms marked done in configs/eval/sweep_dev.yaml are not in the list at all), so stop any time and run again.
# The spend ledger is a LOCAL file (data/openai/ledger.sqlite, one per machine): the code refuses any call that would pass VS_OPENAI_CAP_USD, and the cap itself
# is clamped to 5 USD per ledger file. The key is read from the environment only and never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
cmd="${1:-plan}"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
ROOT="${SWEEP_ROOT:-data/eval/dev_runs}"
if [ "$cmd" = plan ]; then
  $PY -m vakeel_sahayak.eval.runners.driver plan --sweep | awk 'NR<=2 || ($1==2 && $2=="openai") || /still to pay/'
  echo "Estimates use the token counts measured on gpt-6-luna; the real figure is printed by 'make openai-spend' after the first arm. The whole phase is under 3 USD."
  exit 0
fi
if [ "$cmd" = run ]; then
  [ -f .env ] && { set -a; . ./.env; set +a; }
  [ -n "${OPENAI_API_KEY:-}" ] || { echo "OPENAI_API_KEY is not set: put it in your own untracked .env (never commit it)" >&2; exit 1; }
  [ -n "${VS_OPENAI_CAP_USD:-}" ] || { echo "set your own spend cap first, for example: VS_OPENAI_CAP_USD=2.50 $0 run   (the phase needs under 3 USD; the code clamps every cap to 5 USD)" >&2; exit 1; }
  TAG=dev-sweep-v1
  if [ "${ALLOW_OTHER_CODE:-0}" != 1 ]; then
    [ "$(git rev-parse HEAD 2>/dev/null)" = "$(git rev-parse "$TAG^{commit}" 2>/dev/null || echo none)" ] || { echo "this checkout is not the pinned tag $TAG: run  git fetch --tags && git checkout $TAG  (ALLOW_OTHER_CODE=1 overrides; the owner will then refuse the results)" >&2; exit 1; }
    [ -z "$(git status --porcelain -- src configs)" ] || { echo "src/ or configs/ have local edits: use a clean checkout of $TAG" >&2; exit 1; }
  fi
  [ -f data/testsets/t1/dev.jsonl ] || { echo "data/testsets/t1/dev.jsonl is missing: run make data" >&2; exit 1; }
  export VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_OPENAI_CAP_USD
  echo "cap USD $VS_OPENAI_CAP_USD (local ledger); spent so far:"; $PY -m vakeel_sahayak.models.openai.ledger 2>/dev/null | head -3 || true
  $PY scripts/sweep_dev.py run --phase 2 --backend openai --shards "${SHARDS:-3}" --parallel 1 ${ARMS:+--arms "$ARMS"}
  echo "finished or stopped; spend:"; $PY -m vakeel_sahayak.models.openai.ledger 2>/dev/null | head -3 || true
  echo "next: $0 pack"
  exit 0
fi
if [ "$cmd" = pack ]; then
  dirs="$($PY scripts/sweep_dev.py dirs --phase 2 --backend openai ${ARMS:+--arms "$ARMS"})"
  have=""; for d in $dirs; do [ -d "$ROOT/outputs/$d" ] && have="$have $d"; done
  [ -n "$have" ] || { echo "nothing to pack: none of the phase-2 arms has a directory under $ROOT/outputs (run first)" >&2; exit 1; }
  day="$(date +%Y-%m-%d)"; tar_name="$ROOT/sweep-openai-$day.tar.gz"; base_name="sweep-openai-$day.tar.gz"; stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' EXIT
  mkdir -p "$stage/openai_block/outputs" "$stage/openai_block/cases"
  # only the per-case result JSON and the MANIFEST of each phase-2 arm, plus the case lists: no _events (prompts), no logs, no keys, no .env
  for d in $have; do
    mkdir -p "$stage/openai_block/outputs/$d"
    find "$ROOT/outputs/$d" -maxdepth 1 -type f \( -name 'MANIFEST.json' -o -name 't1dev-*.json' \) -exec cp {} "$stage/openai_block/outputs/$d/" \;
  done
  [ -d "$ROOT/cases" ] && find "$ROOT/cases" -maxdepth 1 -type f -name '*.jsonl' -exec cp {} "$stage/openai_block/cases/" \;
  { echo "{"; echo "  \"date\": \"$day\", \"git_commit\": \"$(git rev-parse --short HEAD 2>/dev/null || echo unknown)\","; echo "  \"cap_usd\": \"${VS_OPENAI_CAP_USD:-unset}\","
    echo "  \"spend\": $($PY - <<'PYE' 2>/dev/null || echo '"unavailable"'
import json, subprocess, sys
out = subprocess.run([sys.executable, "-m", "vakeel_sahayak.models.openai.ledger"], capture_output=True, text=True).stdout
print(json.dumps(out.strip().splitlines()[:6]))
PYE
)"; echo "}"; } > "$stage/openai_block/PACK_INFO.json"
  if grep -rIlE "(sk-[A-Za-z0-9]{16,}|SARVAM_API_KEY|OPENAI_API_KEY|hf_[A-Za-z0-9]{20,})" "$stage" >/dev/null 2>&1; then echo "REFUSED: a key-like string is in the package" >&2; exit 1; fi
  tar -czf "$tar_name" -C "$stage" openai_block
  ls -l "$tar_name"
  cat <<EOM

Send it back (default: the team Hugging Face dataset; your token needs WRITE on the org: see docs/handoff/sweep-satvik.md):
  hf upload Vakeel-Sahayak/vakeel-sahayak-data $tar_name sweep-runs/$base_name --repo-type dataset
Fallback: send $tar_name to the owner directly. Then tell the owner the file name ($base_name).
EOM
  exit 0
fi
echo "usage: $0 plan|run|pack" >&2; exit 2
