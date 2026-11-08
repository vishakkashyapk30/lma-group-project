#!/bin/bash
# Second queue: the 24 dev cases whose gold the factor and objection metrics can score (picked from gold only, same for every arm). OpenAI gpt-6-luna, HOSTED.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
cd $VS_LMA/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=$PWD/src OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export VS_ALLOW_PAID=openai VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_NLI=auto VS_HOSTED_RUN_ID=dev-sweep-openai-v3 VS_OPENAI_RUN_CAP_USD=0.60 VS_OPENAI_CAP_USD=4.90
R=$PWD/data/eval/dev_runs/openai_block_v3; PY=$VS_REPO/.venv/bin/python
cp $VS_LMA/t1_scor24.jsonl $R/cases/t1_scor24.jsonl
job() { a=$1; d=$(echo $a | tr A-Z a-z)
  echo "start $a $(date +%T)"
  $PY -m vakeel_sahayak.eval.runners.driver run --system $a --cases $R/cases/t1_scor24.jsonl --out $R/outputs/$d --run-index 1 --shard 0 --n-shards 1 >> $R/logs/$d-q2.log 2>&1
  echo "done $a: $(ls $R/outputs/$d/t1dev-*.json 2>/dev/null | wc -l) $(date +%T)"; }
export -f job; export R PY
printf '%s\n' full b0 b1 b2 b3 b4 A1 A2 A3 A6 A7 A8 A9 | xargs -P4 -L1 bash -c 'job $0'
echo QUEUE2_DONE $(date +%T)
