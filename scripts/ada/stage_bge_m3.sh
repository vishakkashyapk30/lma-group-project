#!/bin/bash
# Stage the BGE-M3 embedding job on Ada (laptop side): copies the exported texts (about 100 MB), bge_vectors.py and the sbatch file to ~/vs_bge on /home2.
# Only these files are copied: never .env, tokens or keys. Run `python -m vakeel_sahayak.pipelines.store_builders.bge_vectors export` first.
#   bash scripts/ada/stage_bge_m3.sh && ssh ada 'sbatch ~/vs_bge/embed_bge_m3.sbatch'
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
TEXTS=${TEXTS:-$REPO/data/bge_work/texts}
[ -f "$TEXTS/texts_manifest.json" ] || { echo "no $TEXTS/texts_manifest.json: run the export first"; exit 1; }
need_kb=$(du -sk "$TEXTS" | cut -f1)
free_kb=$(ssh -o BatchMode=yes ada 'df -Pk ~ | awk "NR==2 {print \$4}"')
echo "texts ${need_kb} KB, /home2 free ${free_kb} KB"
[ "$free_kb" -gt $((need_kb + 250000)) ] || { echo "not enough room on /home2 for the texts plus a 4-shard outbox"; exit 1; }
ssh -o BatchMode=yes ada 'mkdir -p ~/vs_bge/texts ~/vs_bge/logs ~/vs_bge/outbox'
scp -q "$TEXTS"/*.texts.jsonl.gz "$TEXTS/texts_manifest.json" ada:vs_bge/texts/
scp -q "$REPO/src/vakeel_sahayak/pipelines/store_builders/bge_vectors.py" "$REPO/scripts/ada/embed_bge_m3.sbatch" ada:vs_bge/
ssh -o BatchMode=yes ada 'cd ~/vs_bge && python3 - <<"PY"
import hashlib, json
m = json.load(open("texts/texts_manifest.json"))
for store, e in m["stores"].items():
    got = hashlib.sha256(open("texts/" + e["file"], "rb").read()).hexdigest()
    print(store, e["rows"], "ok" if got == e["gz_sha256"] else "BAD")
PY
du -sh ~/vs_bge; df -h ~ | tail -1'
