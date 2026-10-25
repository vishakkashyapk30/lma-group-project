#!/usr/bin/env bash
# Install the team data bundle into data/ (make data-install SRC=<dir | URL | hf:repo> [FORCE=1]).
#
#   make data-install SRC=~/vakeel-data-bundle
#   make data-install SRC=https://host/path/to/bundle/            # a folder served over HTTP(S) (SHA256SUMS lists the parts)
#   make data-install SRC=hf:vishakkashyapk/vakeel-sahayak-data   # private Hugging Face dataset: `hf auth login`, or HF_TOKEN in the untracked .env
#   scripts/data_install.sh --force <src>                         # overwrite what is already in data/
#   VS_DATA_DIR=/scratch/data scripts/data_install.sh <src>        # another target folder (tests, trials)
#
# Steps: fetch (for URL and hf: into a scratch folder), verify SHA256SUMS, refuse to overwrite without --force, unpack into the data folder,
# then a sanity check of row and file counts against bundle_manifest.json. The token is read from the environment or the untracked .env and is never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
force="${FORCE:-0}"; src=""
for a in "$@"; do case "$a" in --force) force=1;; *) src="$a";; esac; done
src="${src:-${SRC:-}}"
[ -n "$src" ] || { echo "usage: scripts/data_install.sh [--force] <dir | URL | hf:<repo>>   (make data-install SRC=...)" >&2; exit 2; }
DATA="${VS_DATA_DIR:-data}"; mkdir -p "$DATA"; DATA="$(cd "$DATA" && pwd)"
scratch=""
cleanup() { [ -n "$scratch" ] && rm -rf "$scratch"; return 0; }
trap cleanup EXIT

case "$src" in
  hf:*)
    repo="${src#hf:}"
    if [ -z "${HF_TOKEN:-}" ] && [ -f .env ]; then HF_TOKEN="$(sed -n 's/^HF_TOKEN=//p' .env | head -1 | tr -d "\"' ")"; export HF_TOKEN; fi
    command -v hf >/dev/null 2>&1 || { echo "the hf command is not installed (pip install -U huggingface_hub)" >&2; exit 1; }
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/vs-data-install.XXXXXX")"
    echo "downloading dataset $repo (needs read access: the owner grants it) ..."
    hf download "$repo" --repo-type dataset --local-dir "$scratch/bundle" >/dev/null
    bundle="$scratch/bundle";;
  http://*|https://*)
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/vs-data-install.XXXXXX")"; bundle="$scratch/bundle"; mkdir -p "$bundle"; base="${src%/}"
    curl -fsSL "$base/SHA256SUMS" -o "$bundle/SHA256SUMS"
    awk '{print $2}' "$bundle/SHA256SUMS" | while read -r f; do echo "fetching $f"; curl -fSL --retry 3 -C - "$base/$f" -o "$bundle/$f"; done;;
  *) bundle="$(cd "${src/#\~/$HOME}" && pwd)";;
esac

[ -f "$bundle/SHA256SUMS" ] || { echo "no SHA256SUMS in $bundle" >&2; exit 1; }
echo "verifying checksums ..."
(cd "$bundle" && sha256sum -c --quiet SHA256SUMS) || { echo "checksum verification FAILED: nothing was unpacked" >&2; exit 1; }

if [ "$force" != 1 ]; then
  clash=()
  for d in interim stores testsets gaps eval; do [ -n "$(ls -A "$DATA/$d" 2>/dev/null)" ] && clash+=("$d"); done
  if [ "${#clash[@]}" -gt 0 ]; then
    echo "refusing to overwrite existing ${clash[*]} in $DATA (use --force, or FORCE=1 with make)" >&2; exit 1
  fi
fi
parts=("$bundle"/data.tar.gz.part-*)
need_kb=$(( $(du -Lck "${parts[@]}" | tail -1 | cut -f1) * 3 ))
free_kb=$(df -Pk "$DATA" | awk 'NR==2 {print $4}')
[ "$free_kb" -gt "$need_kb" ] || echo "warning: only $((free_kb / 1024)) MB free in $DATA; unpacking needs about $((need_kb / 1024)) MB" >&2
echo "unpacking into $DATA ..."
cat "${parts[@]}" | tar -xzf - -C "$DATA"
"$PY" scripts/_data_bundle.py check "$DATA" "$bundle/bundle_manifest.json"
echo "installed. Models are not part of the bundle: see MODELS.txt in the bundle and \`make models\`."
