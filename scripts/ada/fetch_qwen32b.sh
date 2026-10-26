#!/usr/bin/env bash
# Download Qwen/Qwen3-32B-AWQ (public, Apache-2.0, 19.3 GB, 14 files) on Ada with resume and sha256 verification.
# Plain curl, no Python packages: the share1 quota allows only 3,000 files, so a venv does not fit there.
# Usage on the gateway (ssh <user>@ada-gw1):  nohup setsid scripts/ada/fetch_qwen32b.sh > fetch_qwen32b.log 2>&1 &
# Target: $VS_ADA_MODELS (default /share1/$USER/vakeel-sahayak/models). Serving is done inside a GPU session: see docs/handoff/ada-qwen32b.md.
set -u
R=Qwen/Qwen3-32B-AWQ
D="${VS_ADA_MODELS:-/share1/$USER/vakeel-sahayak/models}/Qwen3-32B-AWQ"
mkdir -p "$D"
curl -s -m 60 "https://huggingface.co/api/models/$R/tree/main" > "$D/.tree.json" || exit 1
python3 - "$D" <<'PY' > "$D/.files.txt"
import sys, json
for x in json.load(open(sys.argv[1] + "/.tree.json")):
    if x["type"] == "file":
        print(x["path"], (x.get("lfs") or {}).get("oid", ""))
PY
fail=0
while read -r f oid; do
  for try in 1 2 3 4 5; do
    curl -sSL -C - --retry 3 -o "$D/$f" "https://huggingface.co/$R/resolve/main/$f" && break
    sleep 5
  done
  if [ -n "$oid" ]; then
    got=$(sha256sum "$D/$f" | cut -d" " -f1)
    if [ "$got" = "$oid" ]; then echo "OK $f"; else echo "BAD $f"; fail=1; fi
  else
    echo "OK $f"
  fi
done < "$D/.files.txt"
if [ "$fail" = 0 ]; then echo ALL_DONE; else echo FAILED; fi
