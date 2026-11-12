#!/bin/bash
# The blind slice, once (pre-registration section 1.5 and deviations D1, D2, D6): c1457, Full and B0-B6, one run each, on Sarvam-105B.
# 1. The run file: the 80 sealed ids select the INPUTS from data/testsets/t1/cases.jsonl; the gold field is stripped, nothing else is read.
# 2. The runs (scripts/midsub/arch-search-sarvam-queue.sh, SPLIT=blind, OUT_ROOT=sarvam_blind).
# 3. ONE scoring call over all nine arms with --slice blind --open-blind: the gated opening (needs the tag eval-freeze-v1, writes data/eval/blind.lock;
#    a second opening is refused, so the arms cannot be scored one by one).
# 4. The paused ablations of c1457 on the dev search orders resume (scripts/midsub/winner-ablations-resume.sh) and are scored as they finish.
VS_REPO=${VS_REPO:-$(cd "$(dirname "$0")" && dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}
cd "$(dirname "$0")/../.." || exit 1
W=$PWD; R=$W/data/eval/dev_runs/sarvam_blind; PY=${PY:-$VS_REPO/.venv/bin/python}
git rev-parse -q --verify refs/tags/eval-freeze-v1 >/dev/null || { echo "no eval-freeze-v1 tag: freeze first"; exit 2; }
[ "$(git rev-parse HEAD)" = "$(git rev-parse eval-freeze-v1^{commit})" ] || { echo "HEAD is not the eval-freeze-v1 commit"; exit 2; }
mkdir -p "$R/cases" "$R/logs"
if [ ! -s "$R/cases/t1_30.jsonl" ]; then
  "$PY" -I - "$W/data/testsets/t1" "$R/cases/t1_30.jsonl" <<'PY'
import json, sys
src, out = sys.argv[1], sys.argv[2]
ids = set(json.load(open(f"{src}/blind_sealed.json"))["ids"])
n = 0
with open(out, "w") as fh:
    for line in open(f"{src}/cases.jsonl"):
        row = json.loads(line)
        if row["case_id"] in ids:
            row.pop("gold", None)
            fh.write(json.dumps(row) + "\n"); n += 1
print("blind inputs written:", n)
PY
fi
WIN="S13:signal_source=merge,abstention=strict,draft_source=facts_text,objection_grounding=by_id"
SPLIT=blind OUT_ROOT=sarvam_blind PY=$PY WORKERS=${WORKERS:-5} bash scripts/midsub/arch-search-sarvam-queue.sh "$WIN" full b0 b1 b2 b3 b4 b5 b6
SPLIT=blind OUT_ROOT=sarvam_blind PY=$PY WORKERS=${WORKERS:-5} bash scripts/midsub/arch-search-sarvam-queue.sh "$WIN" full b0 b1 b2 b3 b4 b5 b6   # second pass: shards lost to the manifest race
echo "BLIND_RUNS_DONE $(date +%T)"
for d in "$R"/outputs/*/; do echo "$(basename "$d") $(ls "$d" | grep -c '^t1-.*json$')"; done
PYTHONPATH=$W/src VS_MODELS=auto VS_EXTERNAL=off VS_GEMINI=off VS_M6_CHECKER=minicheck OMP_NUM_THREADS=${OMP:-14} \
  "$PY" -m vakeel_sahayak.eval.scoring score --runs "$R/outputs" --slice blind --open-blind --gold-source agreed --out "$R/scores" > "$R/logs/score_blind.log" 2>&1
tail -3 "$R/logs/score_blind.log"; echo "BLIND_SCORED $(date +%T)"
systemctl --user reset-failed vs-ablate2 2>/dev/null
systemd-run --user --unit=vs-ablate2 --property=StandardOutput=append:$W/data/eval/dev_runs/ablate2.log --property=StandardError=append:$W/data/eval/dev_runs/ablate2.log bash $W/scripts/midsub/winner-ablations-resume.sh
sleep 30
bash scripts/midsub/autoscore-arms.sh sarvam_ablate 30 vs-ablate2
echo ALL_DONE $(date +%T)
