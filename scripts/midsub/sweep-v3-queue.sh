#!/bin/bash
# One queue, 4 workers (memory: each driver loads the NLI and embedding models). OpenAI gpt-6-luna, HOSTED, paid lock opened for openai only (owner go-ahead 2026-10-30).
cd /home/vishak/IIITH-IV-I/lma/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=$PWD/src OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export VS_ALLOW_PAID=openai VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_NLI=auto VS_HOSTED_RUN_ID=dev-sweep-openai-v3 VS_OPENAI_RUN_CAP_USD=0.50 VS_OPENAI_CAP_USD=4.90
R=$PWD/data/eval/dev_runs/openai_block_v3; PY=/home/vishak/IIITH-IV-I/lma/lma-group-project/.venv/bin/python
mkdir -p $R/logs; head -10 data/testsets/t1/dev.jsonl > $R/cases/t1_10.jsonl
job() { a=$1; c=$2; s=$3; ns=$4; d=$(echo $a | tr A-Z a-z)
  echo "start $a s$s/$ns $(date +%T)"
  $PY -m vakeel_sahayak.eval.runners.driver run --system $a --cases $R/cases/$c --out $R/outputs/$d --run-index 1 --shard $s --n-shards $ns >> $R/logs/$d-s$s.log 2>&1
  echo "done $a s$s: $(ls $R/outputs/$d/t1dev-*.json 2>/dev/null | wc -l) $(date +%T)"; }
export -f job; export R PY
printf '%s\n' "full t1_25.jsonl 0 2" "full t1_25.jsonl 1 2" "b4 t1_10.jsonl 0 1" "A2 t1_10.jsonl 0 1" "A3 t1_10.jsonl 0 1" "A6 t1_10.jsonl 0 1" "A7 t1_10.jsonl 0 1" "A8 t1_10.jsonl 0 1" "A9 t1_10.jsonl 0 1" "A1 t1_10.jsonl 0 1" \
 "S1 t1_10.jsonl 0 1" "S3 t1_10.jsonl 0 1" "S8 t1_10.jsonl 0 1" "S9 t1_10.jsonl 0 1" "S10 t1_10.jsonl 0 1" "S15 t1_10.jsonl 0 1" "S2 t1_10.jsonl 0 1" "S5 t1_10.jsonl 0 1" "S4 t1_10.jsonl 0 1" \
 "S11 t1_10.jsonl 0 1" "S12 t1_10.jsonl 0 1" "S6 t1_10.jsonl 0 1" "B5 t1_10.jsonl 0 1" "S18 t1_10.jsonl 0 1" "S3b t1_10.jsonl 0 1" | xargs -P4 -L1 bash -c 'job $0 $1 $2 $3'
echo QUEUE_DONE $(date +%T)
