#!/bin/bash
# usage: autoscore-arms.sh <root under data/eval/dev_runs> <n cases> <unit to wait for>
# Scores each finished arm (one scorer call per arm, at most 2 at once, MiniCheck on CPU) until every arm is scored and the unit has stopped.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
W=$(cd "$(dirname "$0")/../.." && pwd); cd "$W" || exit 1
export PYTHONPATH=$W/src VS_MODELS=auto VS_EXTERNAL=off VS_GEMINI=off VS_M6_CHECKER=minicheck OMP_NUM_THREADS=3
R=$W/data/eval/dev_runs/$1; N=$2; U=$3
PY=${PY:-$VS_REPO/.venv/bin/python}
mkdir -p "$R/scores" "$R/views" "$R/logs"
score_one() { a=$1; V=$R/views/$a; rm -rf "$V"; mkdir -p "$V"; cp -r "$R/outputs/$a" "$V/$a"
  "$PY" -m vakeel_sahayak.eval.scoring score --runs "$V" --slice dev --gold-source agreed --out "$R/scores/$a" > "$R/logs/score_$a.log" 2>&1
  rm -f "$R/scores/$a.started"; echo "scored $a $(date +%T)"; }
rm -f "$R"/scores/*.started   # stale markers from an interrupted run
while true; do
  queued=0
  for d in "$R"/outputs/*/; do
    [ -d "$d" ] || continue
    a=$(basename "$d")
    [ -f "$R/scores/$a/per_case_agreed.csv" ] && continue
    [ -f "$R/scores/$a.started" ] && { queued=1; continue; }
    if [ "$(ls "$d" | grep -c '^t1dev-.*json$')" -lt "$N" ]; then systemctl --user is-active --quiet "$U" && queued=1; continue; fi  # a partial arm waits only while its queue runs
    [ "$(jobs -r | wc -l)" -ge 2 ] && { queued=1; continue; }
    touch "$R/scores/$a.started"; score_one "$a" & queued=1
  done
  if [ $queued = 0 ] && ! systemctl --user is-active --quiet "$U"; then wait; break; fi
  sleep 60
done
echo AUTOSCORE_DONE
