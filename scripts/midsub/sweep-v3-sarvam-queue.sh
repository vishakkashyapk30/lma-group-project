#!/bin/bash
# Sarvam-105B block on dev-sweep-v3 code. Paid lock opened for sarvam only, cap INR 5000 (owner go-ahead 2026-11-01). Pseudonymised payloads.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
cd $VS_LMA/sweep-v3; set -a; . ./.env; set +a; export PYTHONPATH=$PWD/src OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export VS_ALLOW_PAID=sarvam VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_EXTERNAL=pseudonymised VS_SARVAM=pseudonymised VS_SARVAM_CAP_INR=5000 VS_SARVAM_RUN_CAP_INR=60 VS_NLI=auto
R=$PWD/data/eval/dev_runs/sarvam_block_v3; PY=$VS_REPO/.venv/bin/python
mkdir -p $R/logs $R/cases; head -30 data/testsets/t1/dev.jsonl > $R/cases/t1_30.jsonl; head -10 data/testsets/t1/dev.jsonl > $R/cases/t1_10.jsonl
job() { a=$1; c=$2; s=$3; ns=$4; d=$(echo $a | tr A-Z a-z)
  echo "start $a s$s/$ns $(date +%T)"
  $PY -m vakeel_sahayak.eval.runners.driver run --system $a --cases $R/cases/$c --out $R/outputs/$d --run-index 1 --shard $s --n-shards $ns >> $R/logs/$d-s$s.log 2>&1
  echo "done $a s$s: $(ls $R/outputs/$d/t1dev-*.json 2>/dev/null | wc -l) $(date +%T)"; }
export -f job; export R PY
{ for s in 0 1 2; do echo "full t1_30.jsonl $s 3"; done
  for a in b0 b4 b1 b2 b3 b5 b6 A8 A2 A9 A3 A1 A6 A7 A4 A5 A10; do echo "$a t1_30.jsonl 0 1"; done
  for a in S4 S3 S3b S1 S8 S9 S10 S15 S2 S5 S11 S12 S6 S18 S7 S13 S14 S16 S17 P5 P6 P7 P8; do echo "$a t1_10.jsonl 0 1"; done; } | xargs -P4 -L1 bash -c 'job $0 $1 $2 $3'
echo QUEUE_DONE $(date +%T)
