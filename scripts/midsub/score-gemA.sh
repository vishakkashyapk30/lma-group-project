#!/bin/bash
cd /home/vishak/IIITH-IV-I/lma/lma-group-project
export VS_MODELS=auto VS_EXTERNAL=off VS_GEMINI=off OMP_NUM_THREADS=4
Q=/home/vishak/IIITH-IV-I/lma/sweep-v3/data/eval/dev_runs
echo "start gemA $(date +%T)"
.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs $Q/gemini_block/outputs --slice dev --gold-source agreed --out data/eval/dev_runs/scores/gemini_A 2>&1 | grep -vE "Warning|warn\(|Loading weights"
echo "SCORE_GEMA_DONE $(date +%T)"
