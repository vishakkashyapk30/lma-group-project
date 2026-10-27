#!/usr/bin/env bash
# Run on the LAPTOP. Stage everything the QLoRA batch job needs on Ada (the nodes have no repo): usage  stage_qlora_inputs.sh TAG [DATA_DIR]
#   TAG       an existing git tag (the code that trains is exactly this tag: `git archive`, so uncommitted files never travel)
#   DATA_DIR  folder with train.jsonl and dev.jsonl (default data/interim/finetune, where finetune.build_dataset writes them)
# Sends to $ADA_HOST:vakeel_qlora/in/ (default host `ada` = ada-gw1; $HOME there is NFS with about 2 GB free): code-TAG.tar.gz, train.jsonl, dev.jsonl,
# qlora.yaml (of the tag), sbatch_qlora.sbatch (of the tag), stage.env, SHA256SUMS. Checks the free space first and verifies the checksums after the copy.
# Refuses to send client data or secrets: nothing from data/cases or data/raw (except .gitkeep), no .env (except .env.example), no key files; the data files
# must contain chat rows only. Then prints the sbatch commands. Test hooks (no ssh): NO_SEND=1 (stage locally in $STAGE_DIR), ADA_FREE_KB=<number>, REPO=<git repo>.
set -euo pipefail
TAG="${1:-}"; DATA_DIR="${2:-data/interim/finetune}"
[ -n "$TAG" ] || { echo "usage: $0 TAG [DATA_DIR]   (TAG: git tag of the code to train with)" >&2; exit 2; }
REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
HOST="${ADA_HOST:-ada}"; REMOTE_DIR="vakeel_qlora/in"
STAGE_DIR="${STAGE_DIR:-$(mktemp -d)}"; MIN_SPARE_KB=$((500 * 1024))
cd "$REPO"
git rev-parse -q --verify "refs/tags/$TAG^{commit}" >/dev/null || { echo "no such git tag: $TAG (create it: git tag $TAG, then re-run)" >&2; exit 2; }
SHA=$(git rev-parse "$TAG^{commit}")

# 1. refuse client data, secrets in the archive
BAD=$(git archive --format=tar "$TAG" | tar -t | grep -E '^(data/cases/|data/raw/)|(^|/)\.env(\.|$)|\.(pem|key|p12)$|(^|/)id_(rsa|ed25519)|(^|/)(secrets?|credentials)(\.|/|$)' \
  | grep -v -E '(^|/)\.gitkeep$|(^|/)\.env\.example$|/$' || true)
[ -z "$BAD" ] || { echo "REFUSED: the archive of $TAG contains client data or secrets:" >&2; echo "$BAD" | head >&2; exit 3; }
# 2. refuse data files from the wrong place, and files that are not chat rows
for f in train.jsonl dev.jsonl; do
  p="$DATA_DIR/$f"
  [ -s "$p" ] || { echo "missing or empty $p: build it with python -m vakeel_sahayak.finetune.build_dataset" >&2; exit 2; }
  real=$(realpath "$p")
  case "$real" in */data/cases/*|*/data/raw/*|*/.env*|*key*) echo "REFUSED: $real is client data, raw data or a key file" >&2; exit 3;; esac
  python3 - "$p" <<'PY' || { echo "REFUSED: $p is not a chat dataset ({\"messages\": [...]} per line)" >&2; exit 3; }
import json, sys
n = 0
for line in open(sys.argv[1], encoding="utf-8"):
    if line.strip():
        m = json.loads(line)["messages"]; assert m[-1]["role"] == "assistant"; n += 1
assert n
PY
done
# 3. build the stage folder
rm -rf "$STAGE_DIR"; mkdir -p "$STAGE_DIR"
git archive --format=tar.gz -o "$STAGE_DIR/code-$TAG.tar.gz" "$TAG"
cp "$DATA_DIR/train.jsonl" "$DATA_DIR/dev.jsonl" "$STAGE_DIR/"
git show "$TAG:configs/finetune/qlora.yaml" > "$STAGE_DIR/qlora.yaml"
git show "$TAG:scripts/ada/sbatch_qlora.sbatch" > "$STAGE_DIR/sbatch_qlora.sbatch"
printf 'VS_CODE_TAG=%s\nVS_CODE_SHA=%s\n' "$TAG" "$SHA" > "$STAGE_DIR/stage.env"
(cd "$STAGE_DIR" && sha256sum code-"$TAG".tar.gz train.jsonl dev.jsonl qlora.yaml sbatch_qlora.sbatch stage.env > SHA256SUMS)
NEED_KB=$(du -sk "$STAGE_DIR" | cut -f1)
echo "staged $(ls "$STAGE_DIR" | wc -l) files, ${NEED_KB} KB, tag $TAG ($SHA)"
# 4. size check against the free space of $HOME on Ada
if [ -n "${ADA_FREE_KB:-}" ]; then FREE_KB="$ADA_FREE_KB"; elif [ -n "${NO_SEND:-}" ]; then FREE_KB=""; else
  FREE_KB=$(ssh "$HOST" 'df -Pk "$HOME" | awk "NR==2{print \$4}"')
fi
if [ -n "$FREE_KB" ] && [ "$((NEED_KB + MIN_SPARE_KB))" -gt "$FREE_KB" ]; then
  echo "REFUSED: needs ${NEED_KB} KB plus 500 MB spare (adapters come back here) but \$HOME on Ada has ${FREE_KB} KB free; clear ~/vakeel_qlora/out or old files first" >&2; exit 4
fi
[ -z "${NO_SEND:-}" ] || { echo "NO_SEND set: staged in $STAGE_DIR"; exit 0; }
# 5. send and verify
ssh "$HOST" "mkdir -p $REMOTE_DIR slurm_logs && rm -f $REMOTE_DIR/code-*.tar.gz"
scp -q "$STAGE_DIR"/* "$HOST:$REMOTE_DIR/"
ssh "$HOST" "cd $REMOTE_DIR && sha256sum -c SHA256SUMS"
rm -rf "$STAGE_DIR"
cat <<MSG
Staged on $HOST:$REMOTE_DIR. Submit the three seeds one after another (the QOS allows 4 GPUs at once):
  ssh $HOST 'cd ~ && mkdir -p slurm_logs && sbatch --export=ALL,RUN=0 vakeel_qlora/in/sbatch_qlora.sbatch'    # then RUN=1, RUN=2 when the previous one has finished
Watch:  ssh $HOST 'squeue -u \$USER; tail -n 30 ~/slurm_logs/qlora_*.out'
Fetch:  bash scripts/ada/fetch_qlora_outputs.sh
MSG
