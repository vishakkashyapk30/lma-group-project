#!/bin/bash
# A5:base_4b, A10:<store> (7 stores) and S13:stopping=llm on Sarvam-105B, first 10 dev cases, dev-sweep-v3 code (owner go-ahead 2026-11-01).
# Stops by itself once this script has spent more than BUDGET_INR (default 380) according to the Sarvam ledger.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
cd $VS_LMA/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=$PWD/src OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export VS_ALLOW_PAID=sarvam VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_EXTERNAL=pseudonymised VS_SARVAM=pseudonymised VS_SARVAM_CAP_INR=5000 VS_SARVAM_RUN_CAP_INR=90 VS_NLI=auto
R=$PWD/data/eval/dev_runs/sarvam_block_v3; PY=$VS_REPO/.venv/bin/python; BUDGET=${BUDGET_INR:-380}
mkdir -p $R/logs $R/cases; [ -f $R/cases/t1_10.jsonl ] || head -10 data/testsets/t1/dev.jsonl > $R/cases/t1_10.jsonl
spent() { $PY -m vakeel_sahayak.models.sarvam.spend 2>&1 | grep -oiE 'INR *[0-9.]+|[0-9.]+ *INR' | head -1 | grep -oE '[0-9.]+'; }
START=$(spent); echo "start ledger=$START $(date +%T)"
for a in A10:law.statutes A10:law.concordance A10:caselaw.reasoning A10:caselaw.citations A10:caselaw.similar A10:advocacy.arguments A10:advocacy.objections S13:stopping=llm A5:base_4b; do
  now=$(spent)
  if ! $PY -c "import sys; sys.exit(0 if float('$now')-float('$START')<$BUDGET else 1)"; then echo "BUDGET_STOP before $a ledger=$now"; break; fi
  d=$(echo $a | tr 'A-Z:=,.' 'a-z___'); echo "start $a $(date +%T)"
  $PY -m vakeel_sahayak.eval.runners.driver run --system "$a" --cases $R/cases/t1_10.jsonl --out $R/outputs/$d --run-index 1 >> $R/logs/$d.log 2>&1
  echo "done $a: $(ls $R/outputs/$d/t1dev-*.json 2>/dev/null | wc -l) cases, ledger=$(spent) $(date +%T)"
done
echo ARMS_DONE ledger=$(spent) $(date +%T)
