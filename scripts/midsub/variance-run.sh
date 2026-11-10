#!/bin/bash
# Run-to-run spread (pre-registration D12): c1457, Full and B0-B6 on the 30 dev search orders t1dev-000..029, on the frozen code
# (the run worktree at eval-freeze-v1), with the Sarvam response cache OFF, so a repeat is a fresh call to the model and not a replay.
# Usage: FROZEN=<worktree at eval-freeze-v1> bash scripts/midsub/variance-run.sh <run number>     (writes data/eval/dev_runs/sarvam_var<n>)
# Then score with the D10 scoring code: SCORER=<score-fix worktree> bash scripts/midsub/variance-run.sh score <n>
# Sarvam only (VS_ALLOW_PAID=sarvam inside the queue script), payloads pseudonymised; OpenAI stays locked. Holdout and blind are not touched.
set -u
FROZEN=${FROZEN:?set FROZEN to the worktree at eval-freeze-v1}
VENV_PY=${PY:-$(dirname "$(git -C "$FROZEN" rev-parse --path-format=absolute --git-common-dir)")/.venv/bin/python}
[ "$(git -C "$FROZEN" rev-parse HEAD)" = "$(git -C "$FROZEN" rev-parse 'eval-freeze-v1^{commit}')" ] || { echo "FROZEN is not at eval-freeze-v1"; exit 2; }
WIN="S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
if [ "$1" = score ]; then
  n=$2; R=$FROZEN/data/eval/dev_runs/sarvam_var$n; SCORER=${SCORER:?set SCORER to the score-fix worktree}
  PYTHONPATH=$SCORER/src VS_DATA_DIR=$FROZEN/data VS_MODELS=auto VS_EXTERNAL=off VS_GEMINI=off VS_M6_CHECKER=minicheck OMP_NUM_THREADS=${OMP:-6} \
    "$VENV_PY" -m vakeel_sahayak.eval.scoring score --runs "$R/outputs" --slice dev --gold-source agreed --out "$R/scores" > "$R/logs/score.log" 2>&1
  echo "SCORED var$n exit=$? $(date +%T)"; exit 0
fi
n=$1
export VS_SARVAM_NO_CACHE=1
for pass in 1 2; do   # the second pass picks up shards lost to a start-up race; a resume skips cases already saved
  OUT_ROOT=sarvam_var$n SPLIT=search PY=$VENV_PY WORKERS=${WORKERS:-7} NSHARDS=${NSHARDS:-3} \
    bash "$FROZEN/scripts/midsub/arch-search-sarvam-queue.sh" "$WIN" full b4 b5 b0 b1 b2 b3 b6
done
R=$FROZEN/data/eval/dev_runs/sarvam_var$n
for d in "$R"/outputs/*/; do echo "$(basename "$d") $(ls "$d" | grep -c '^t1dev-.*json$')"; done
echo "VAR_RUN_DONE $n $(date +%T)"
