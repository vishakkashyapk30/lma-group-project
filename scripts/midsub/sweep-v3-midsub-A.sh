#!/bin/bash
# Mid-submission block A: gemini-3.5-flash-lite (paired): full,b0,b1,b2,b3 n=10; A1 n=5; b0l (gemini-3.6-flash) n=10. Resumes hourly.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
cd $VS_LMA/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=$VS_LMA/sweep-v3/src
OUT=$VS_LMA/sweep-v3/data/eval/dev_runs/gemini_block/outputs
cnt() { ls $OUT/$1/t1dev-*.json 2>/dev/null | wc -l; }
for i in $(seq 1 48); do
  echo "== pass $i $(date '+%F %T')"
  $VS_REPO/.venv/bin/python scripts/sweep_dev.py run --phase 5 --arms full,b0,b1,b2,b3 --n 10 --shards 2 --parallel 1 2>&1 | grep -E "started|finished|quota|Error|error" | tail -12
  $VS_REPO/.venv/bin/python scripts/sweep_dev.py run --phase 5 --arms A1 --n 5 --shards 2 --parallel 1 2>&1 | grep -E "started|finished|quota|Error|error" | tail -6
  $VS_REPO/.venv/bin/python scripts/sweep_dev.py run --phase 5 --arms b0l --n 10 --shards 1 --parallel 1 2>&1 | grep -E "started|finished|quota|Error|error" | tail -6
  s="full:$(cnt full) b0:$(cnt b0) b1:$(cnt b1) b2:$(cnt b2) b3:$(cnt b3) a1:$(cnt a1) b0l:$(cnt b0l)"; echo "$s"
  [ $(cnt full) -ge 10 ] && [ $(cnt b0) -ge 10 ] && [ $(cnt b1) -ge 10 ] && [ $(cnt b2) -ge 10 ] && [ $(cnt b3) -ge 10 ] && [ $(cnt a1) -ge 5 ] && [ $(cnt b0l) -ge 10 ] && { echo "BLOCK_A_DONE $(date '+%F %T')"; break; }
  sleep 1200
done
