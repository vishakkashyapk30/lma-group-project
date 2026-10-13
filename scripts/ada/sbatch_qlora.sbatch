#!/usr/bin/env bash
#SBATCH --job-name=vs-qlora
#SBATCH --gres=gpu:1
#SBATCH --time=1-12:00:00
#SBATCH --output=logs/qlora_%j.out
# QLoRA training of the Qwen3-4B extractor (plan §12, §17): the ONLY sbatch job.
# One 2080 Ti per run, at most 1.5 days (well inside the 4-day batch limit), checkpoint every epoch.
# This is training, not inference serving; all LLM/vision inference uses interactive sessions instead.
set -euo pipefail
echo "TODO"; exit 1
