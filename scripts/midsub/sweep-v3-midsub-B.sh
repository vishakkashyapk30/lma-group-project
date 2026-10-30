#!/bin/bash
# Mid-submission block B: gemini-3.1-flash-lite (paired, its own Full): full, A2, A8 on 5 dev cases. Resumes every 20 min.
cd /home/vishak/IIITH-IV-I/lma/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=/home/vishak/IIITH-IV-I/lma/sweep-v3/src
export VS_MODELS=auto VS_LLM_BACKEND=gemini VS_GEMINI=pseudonymised VS_GEMINI_MODEL=gemini-3.1-flash-lite VS_NLI=auto VS_HOSTED_RUN_ID=dev-sweep-gemini-31
OUT=/home/vishak/IIITH-IV-I/lma/sweep-v3/data/eval/dev_runs/gemini_block_31/outputs; CASES=/home/vishak/IIITH-IV-I/lma/sweep-v3/data/eval/dev_runs/gemini_block/cases/t1_5.jsonl
cnt() { ls $OUT/$1/t1dev-*.json 2>/dev/null | wc -l; }
for i in $(seq 1 72); do
  echo "== pass $i $(date '+%F %T')"
  for a in full A2 A8; do d=$(echo $a | tr A-Z a-z)
    [ $(cnt $d) -ge 5 ] && continue
    /home/vishak/IIITH-IV-I/lma/lma-group-project/.venv/bin/python -m vakeel_sahayak.eval.runners.driver run --system $a --cases $CASES --out $OUT/$d --run-index 1 --shard 0 --n-shards 1 2>&1 | grep -vE "Warning|warn\(|Loading weights" | tail -3
  done
  echo "full:$(cnt full) a2:$(cnt a2) a8:$(cnt a8)"
  [ $(cnt full) -ge 5 ] && [ $(cnt a2) -ge 5 ] && [ $(cnt a8) -ge 5 ] && { echo "BLOCK_B_DONE $(date '+%F %T')"; break; }
  sleep 1200
done
