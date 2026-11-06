#!/bin/bash
# Resume the ablations on the winner c1457 after the 4 Nov reboot (finished cases are skipped by the driver).
# A1, A2, A8 and A9 cannot sit on top of all four winner switches (the Switches validator refuses the combinations):
#   A1 = no dossier: X1 (merges dossier and facts) and X5 (drafts from facts while the dossier stays) are dropped, since with no dossier everything reads the facts.
#   A2 = no check-and-repair: X4 (acts on the repair result) is dropped.
#   A8 = no sparring: X7 (how Abhiyojak's references are checked) is dropped.  A9 = A2 + A8.
cd "$(dirname "$0")/../.."
export PY=/home/vishak/IIITH-IV-I/lma/lma-group-project/.venv/bin/python WORKERS=4
W="S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
OUT_ROOT=sarvam_ablate bash scripts/midsub/arch-search-sarvam-queue.sh \
  "$W,no_tools=true" "$W,plain_retrieval=true" "$W,fixed_router=true" "$W,free_planner=true" \
  "S13:abstention=strict,objection_grounding=by_id,no_dossier=true" \
  "S13:signal_source=merge,draft_source=facts_text,objection_grounding=by_id,no_check_repair=true" \
  "S13:signal_source=merge,abstention=strict,draft_source=facts_text,no_sparring=true" \
  "S13:signal_source=merge,draft_source=facts_text,no_sparring=true,no_check_repair=true"
echo ABLATE_DONE $(date +%T)
