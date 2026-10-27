#!/usr/bin/env bash
# The Sarvam-105B block of the pre-freeze dev-set sweep, to be run by a teammate with HIS OWN Sarvam key and spend cap (docs/handoff/sweep-satvik.md).
#
#   scripts/sweep_sarvam_block.sh plan            # arms, cases and estimated INR (calls no model, needs no key)
#   VS_SARVAM_CAP_INR=150 scripts/sweep_sarvam_block.sh run            # run the arms in priority order until done or the cap is reached
#   VS_SARVAM_CAP_INR=150 ARMS=full,b0,S3 SHARDS=3 scripts/sweep_sarvam_block.sh run     # a subset
#   scripts/sweep_sarvam_block.sh pack            # package the small result files into sweep-sarvam-<date>.tar.gz and print the upload command
#
# Prerequisites: `make setup`, `make data` (needs data/testsets/t1 and data/stores), your SARVAM_API_KEY in your own untracked .env.
# Resumable: finished cases are skipped, so stop any time (Ctrl-C) and run it again. Outputs: data/eval/dev_runs/sarvam_block/. The spend ledger is a LOCAL file
# (data/sarvam/ledger.sqlite): nothing is shared, and the ledger refuses the call that would pass VS_SARVAM_CAP_INR. The key is read from the environment only and is never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
cmd="${1:-plan}"
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
ROOT="${SWEEP_ROOT:-data/eval/dev_runs/sarvam_block}"
if [ "$cmd" = plan ]; then
  $PY -m vakeel_sahayak.eval.runners.driver plan --sweep | awk 'NR<=2 || $2=="sarvam" || /still to pay/'
  echo "Estimates assume the token counts measured on gpt-6-luna (about 70K input and 4K output tokens per Full case) at the Sarvam-105B dashboard prices; the real figure is printed by 'make sarvam-spend' after the first arm."
  exit 0
fi
if [ "$cmd" = run ]; then
  [ -f .env ] && { set -a; . ./.env; set +a; }
  [ -n "${SARVAM_API_KEY:-}" ] || { echo "SARVAM_API_KEY is not set: put it in your own untracked .env (never commit it)" >&2; exit 1; }
  [ -n "${VS_SARVAM_CAP_INR:-}" ] || { echo "set your own spend cap first, for example: VS_SARVAM_CAP_INR=150 $0 run   (the whole block needs about INR 440; you decide how much to spend)" >&2; exit 1; }
  TAG=dev-sweep-v1
  if [ "${ALLOW_OTHER_CODE:-0}" != 1 ]; then
    [ "$(git rev-parse HEAD 2>/dev/null)" = "$(git rev-parse "$TAG^{commit}" 2>/dev/null || echo none)" ] || { echo "this checkout is not the pinned tag $TAG: run  git fetch --tags && git checkout $TAG  (ALLOW_OTHER_CODE=1 overrides; the owner will then refuse the results)" >&2; exit 1; }
    [ -z "$(git status --porcelain -- src configs)" ] || { echo "src/ or configs/ have local edits: use a clean checkout of $TAG" >&2; exit 1; }
  fi
  [ -f data/testsets/t1/dev.jsonl ] || { echo "data/testsets/t1/dev.jsonl is missing: run make data" >&2; exit 1; }
  export VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_EXTERNAL=pseudonymised VS_SARVAM=pseudonymised VS_SARVAM_CAP_INR
  echo "cap INR $VS_SARVAM_CAP_INR (local ledger); spent so far:"; $PY -m vakeel_sahayak.models.sarvam.spend 2>/dev/null | head -3 || true
  $PY scripts/sweep_dev.py run --phase 3 --backend sarvam --shards "${SHARDS:-3}" --parallel 1 ${ARMS:+--arms "$ARMS"}
  echo "finished or stopped; spend:"; $PY -m vakeel_sahayak.models.sarvam.spend 2>/dev/null | head -3 || true
  echo "next: $0 pack"
  exit 0
fi
if [ "$cmd" = pack ]; then
  [ -d "$ROOT/outputs" ] || { echo "nothing to pack: no $ROOT/outputs (run first)" >&2; exit 1; }
  day="$(date +%Y-%m-%d)"; tar_name="data/eval/dev_runs/sweep-sarvam-$day.tar.gz"; base_name="sweep-sarvam-$day.tar.gz"; stage="$(mktemp -d)"
  trap 'rm -rf "$stage"' EXIT
  mkdir -p "$stage/sarvam_block"
  # only the per-case result JSON and the MANIFEST of each arm, plus the case lists: no _events (prompts), no logs, no keys, no .env
  (cd "$ROOT" && find outputs cases -type f \( -name 'MANIFEST.json' -o -name '*.jsonl' -o -path 'outputs/*/t1dev-*.json' \) ! -path '*/_events/*' -print0 | tar --null -T - -cf - ) | tar -xf - -C "$stage/sarvam_block"
  { echo "{"; echo "  \"date\": \"$day\", \"git_commit\": \"$(git rev-parse --short HEAD 2>/dev/null || echo unknown)\","; echo "  \"cap_inr\": \"${VS_SARVAM_CAP_INR:-unset}\","
    echo "  \"spend\": $($PY - <<'PYE' 2>/dev/null || echo '"unavailable"'
import json, subprocess, sys
out = subprocess.run([sys.executable, "-m", "vakeel_sahayak.models.sarvam.spend"], capture_output=True, text=True).stdout
print(json.dumps(out.strip().splitlines()[:6]))
PYE
)"; echo "}"; } > "$stage/sarvam_block/PACK_INFO.json"
  if grep -rIlE "(sk-[A-Za-z0-9]{16,}|SARVAM_API_KEY|OPENAI_API_KEY|hf_[A-Za-z0-9]{20,})" "$stage" >/dev/null 2>&1; then echo "REFUSED: a key-like string is in the package" >&2; exit 1; fi
  tar -czf "$tar_name" -C "$stage" sarvam_block
  ls -l "$tar_name"
  cat <<EOM

Send it back (default: the team Hugging Face dataset; your token needs WRITE on the org: see docs/handoff/sweep-satvik.md):
  hf upload Vakeel-Sahayak/vakeel-sahayak-data $tar_name sweep-runs/$base_name --repo-type dataset
Fallback: send $tar_name to the owner directly. Then tell the owner the file name ($base_name).
EOM
  exit 0
fi
echo "usage: $0 plan|run|pack" >&2; exit 2
