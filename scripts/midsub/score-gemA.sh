#!/bin/bash
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}  # main checkout (holds .venv), also from a worktree
VS_LMA=${VS_LMA:-$(dirname "$VS_REPO")}  # its parent folder (sweep-v3 worktree, scratch case files)
cd $VS_REPO
export VS_MODELS=auto VS_EXTERNAL=off VS_GEMINI=off OMP_NUM_THREADS=4
Q=$VS_LMA/sweep-v3/data/eval/dev_runs
echo "start gemA $(date +%T)"
.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs $Q/gemini_block/outputs --slice dev --gold-source agreed --out data/eval/dev_runs/scores/gemini_A 2>&1 | grep -vE "Warning|warn\(|Loading weights"
echo "SCORE_GEMA_DONE $(date +%T)"
