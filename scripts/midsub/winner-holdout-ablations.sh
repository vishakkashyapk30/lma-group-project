#!/bin/bash
# Winner of the architecture search (c1457 = X1+X4+X5+X7): holdout t1dev-030..049 once (winner, Full, B0-B6), then ablations on the 30 search cases
# (the winner rerun on this commit, leave-one-out of each component, and A1-A4, A6-A9 applied to the winner). Sarvam only; OpenAI locked.
cd "$(dirname "$0")/../.."
export PY=/home/vishak/IIITH-IV-I/lma/lma-group-project/.venv/bin/python WORKERS=4
SPLIT=holdout OUT_ROOT=sarvam_holdout bash scripts/midsub/arch-search-sarvam-queue.sh "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id" full b0 b1 b2 b3 b4 b5 b6
echo HOLDOUT_DONE $(date +%T)
OUT_ROOT=sarvam_ablate bash scripts/midsub/arch-search-sarvam-queue.sh "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id" \
  "S13:abstention=strict,draft_source=facts_text,objection_grounding=by_id" \
  "S13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id" \
  "S13:signal_source=merge,abstention=strict,objection_grounding=by_id" \
  "S13:signal_source=merge,abstention=strict,draft_source=facts_text" \
  "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,no_dossier=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,no_check_repair=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,no_tools=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,plain_retrieval=true" \
  "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,fixed_router=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,free_planner=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,no_sparring=true" "S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id,no_sparring=true,no_check_repair=true"
echo ABLATE_DONE $(date +%T)
