#!/usr/bin/env bash
# Run on the LAPTOP after the QLoRA batch jobs: usage  fetch_qlora_outputs.sh [RUNS]   (RUNS default "0 1 2")
# For each run K: copy the adapter ($HOME/vakeel_qlora/out/run<K> on Ada: adapter/, epoch.json, manifest.json) to models/adapters/run<K>/ on the laptop,
# verify the sha256 sums written by the job; then, on the login node, copy it to /share1/$USER/vakeel-sahayak/adapters/run<K>/ (the archive), verify there too,
# and only then free the $HOME copy (NFS, about 2 GB free) unless KEEP_HOME=1. A run with epoch.json "final": false is fetched but flagged (training did not finish).
# Test hooks: LOCAL_ADA=<dir> (use <dir> as Ada's $HOME and run the "remote" steps locally), SHARE1_DIR=<dir>, DEST=<dir>.
set -euo pipefail
RUNS="${1:-0 1 2}"
REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
HOST="${ADA_HOST:-ada}"; DEST="${DEST:-$REPO/models/adapters}"
rsh() { if [ -n "${LOCAL_ADA:-}" ]; then HOME="$LOCAL_ADA" bash -c "$1"; else ssh "$HOST" "$1"; fi; }
rget() { if [ -n "${LOCAL_ADA:-}" ]; then cp -r "$LOCAL_ADA/$1" "$2"; else scp -q -r "$HOST:$1" "$2"; fi; }
SHARE1='${SHARE1_DIR:-/share1/$USER/vakeel-sahayak/adapters}'
status=0
for K in $RUNS; do
  case "$K" in 0|1|2) ;; *) echo "bad run '$K' (0, 1 or 2)" >&2; exit 2;; esac
  SRC="vakeel_qlora/out/run$K"
  if ! rsh "test -s \$HOME/$SRC/epoch.json && test -s \$HOME/$SRC/adapter/adapter_model.safetensors"; then echo "run $K: no adapter on Ada yet, skipped" >&2; status=1; continue; fi
  tmp="$DEST/.run$K.part"; rm -rf "$tmp"; mkdir -p "$DEST"
  rget "$SRC" "$tmp"
  python3 - "$tmp" <<'PY'
import hashlib, json, sys
from pathlib import Path
d = Path(sys.argv[1]); meta = json.loads((d / "epoch.json").read_text())
for name, want in meta["sha256"].items():
    got = hashlib.sha256((d / "adapter" / name).read_bytes()).hexdigest()
    assert got == want, f"checksum mismatch for {name}"
print(f"verified {len(meta['sha256'])} file(s); epoch {meta['epoch']} final={meta['final']}")
if not meta["final"]:
    print("WARNING: training had not finished (final=false); resubmit the job to continue")
PY
  rm -rf "$DEST/run$K"; mv "$tmp" "$DEST/run$K"
  echo "run $K: $DEST/run$K"
  # archive on the login node (share1 is visible from the gateway only), verify, then free $HOME
  rsh "A=\"$SHARE1/run$K\"; mkdir -p \"\$A\" && cp -a \$HOME/$SRC/. \"\$A/\" && cd \"\$A\" && (cd adapter && sha256sum adapter_model.safetensors adapter_config.json) > .sums && \
    python3 -c 'import json; m=json.load(open(\"epoch.json\"))[\"sha256\"]; print(\"\\n\".join(v+\"  \"+k for k,v in m.items()))' > .want && diff -q <(sort .sums) <(sort .want) >/dev/null && echo \"archived and verified in \$A\" && rm -f .sums .want" \
    || { echo "run $K: archive on share1 FAILED, the \$HOME copy is kept" >&2; status=1; continue; }
  if [ -z "${KEEP_HOME:-}" ]; then rsh "rm -rf \$HOME/$SRC" && echo "run $K: \$HOME copy removed (a resume would restart from epoch 0; KEEP_HOME=1 to keep)"; fi
done
exit $status
