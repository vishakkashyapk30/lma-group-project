#!/usr/bin/env bash
# Install the team data bundle into data/ (make data-install SRC=<dir | URL | hf:repo> [FORCE=1] [RAW=0]).
#
#   make data-install SRC=~/vakeel-data-bundle
#   make data-install SRC=https://host/path/to/bundle/            # a folder served over HTTP(S) (SHA256SUMS lists the parts)
#   make data-install SRC=hf:Vakeel-Sahayak/vakeel-sahayak-data   # private Hugging Face dataset: `hf auth login`, or HF_TOKEN in the untracked .env
#   scripts/data_install.sh --force <src>                         # overwrite what is already in data/
#   RAW=0 scripts/data_install.sh <src>   (or --no-raw)           # skip the raw archive (public source data, about 2 GB) to save disk
#   scripts/data_install.sh --only-raw <src>                      # add only the raw archive to a data/ that already has the derived data
#   VS_DATA_DIR=/scratch/data scripts/data_install.sh <src>        # another target folder (tests, trials)
#
# Both archives are installed by default: data.tar.gz.part-* (interim, stores, testsets, gaps, eval) and raw.tar.part-* (data/raw: Open India Law shards,
# IPC2BNS-Verify, Kathbath audio, MANIFEST.json). Steps: fetch (for URL and hf: into a scratch folder under TMPDIR, as large as the archives you install),
# verify SHA256SUMS of the files that will be unpacked, refuse to overwrite without --force, check the free disk, unpack, then a sanity check of row and
# file counts against bundle_manifest.json. The token is read from the environment or the untracked .env and is never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
force="${FORCE:-0}"; src=""; raw="${RAW:-1}"; only_raw=0
for a in "$@"; do case "$a" in --force) force=1;; --no-raw) raw=0;; --only-raw) only_raw=1; raw=1;; *) src="$a";; esac; done
src="${src:-${SRC:-}}"
[ -n "$src" ] || { echo "usage: scripts/data_install.sh [--force] [--no-raw | --only-raw] <dir | URL | hf:<repo>>   (make data-install SRC=...; RAW=0 skips the raw archive)" >&2; exit 2; }
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
    excl=(); [ "$raw" = 1 ] || excl+=(--exclude "raw.tar.part-*"); [ "$only_raw" != 1 ] || excl+=(--exclude "data.tar.gz.part-*")
    echo "downloading dataset $repo (needs read access: the owner grants it) ..."
    hf download "$repo" --repo-type dataset --local-dir "$scratch/bundle" "${excl[@]}" >/dev/null
    bundle="$scratch/bundle";;
  http://*|https://*)
    scratch="$(mktemp -d "${TMPDIR:-/tmp}/vs-data-install.XXXXXX")"; bundle="$scratch/bundle"; mkdir -p "$bundle"; base="${src%/}"
    curl -fsSL "$base/SHA256SUMS" -o "$bundle/SHA256SUMS"
    awk '{print $2}' "$bundle/SHA256SUMS" | while read -r f; do
      case "$f" in raw.tar.part-*) [ "$raw" = 1 ] || continue;; data.tar.gz.part-*) [ "$only_raw" != 1 ] || continue;; esac
      echo "fetching $f"; curl -fSL --retry 3 -C - "$base/$f" -o "$bundle/$f"
    done;;
  *) bundle="$(cd "${src/#\~/$HOME}" && pwd)";;
esac

[ -f "$bundle/SHA256SUMS" ] || { echo "no SHA256SUMS in $bundle" >&2; exit 1; }
# verify only the files that are going to be unpacked (a skipped raw archive need not be present)
sums="$(mktemp "${TMPDIR:-/tmp}/vs-sums.XXXXXX")"; trap 'rm -f "$sums"; cleanup' EXIT
cp "$bundle/SHA256SUMS" "$sums"
[ "$raw" = 1 ] || sed -i '/ raw\.tar\.part-/d' "$sums"
[ "$only_raw" != 1 ] || sed -i '/ data\.tar\.gz\.part-/d' "$sums"
echo "verifying checksums ..."
(cd "$bundle" && sha256sum -c --quiet "$sums") || { echo "checksum verification FAILED: nothing was unpacked" >&2; exit 1; }

data_parts=("$bundle"/data.tar.gz.part-*); raw_parts=("$bundle"/raw.tar.part-*)
[ -e "${data_parts[0]}" ] || data_parts=(); [ -e "${raw_parts[0]}" ] || raw_parts=()
[ "$only_raw" != 1 ] || data_parts=()
[ "$raw" = 1 ] || raw_parts=()
[ "$raw" != 1 ] || [ "${#raw_parts[@]}" -gt 0 ] || echo "note: this bundle has no raw archive (older bundle); installing the data archive only" >&2
[ "${#data_parts[@]}" -gt 0 ] || [ "${#raw_parts[@]}" -gt 0 ] || { echo "nothing to install: no archive parts for these options in $bundle" >&2; exit 1; }

if [ "$force" != 1 ]; then
  clash=()
  if [ "${#data_parts[@]}" -gt 0 ]; then
    for d in interim stores testsets gaps eval; do [ -n "$(ls -A "$DATA/$d" 2>/dev/null)" ] && clash+=("$d"); done
  fi
  if [ "${#raw_parts[@]}" -gt 0 ]; then
    for d in raw/open_india_law raw/ipc2bns_verify raw/kathbath/hindi/test_known/audio; do [ -n "$(ls -A "$DATA/$d" 2>/dev/null)" ] && clash+=("$d"); done
  fi
  if [ "${#clash[@]}" -gt 0 ]; then
    echo "refusing to overwrite existing ${clash[*]} in $DATA (use --force, or FORCE=1 with make; RAW=0 / --no-raw leaves data/raw alone)" >&2; exit 1
  fi
fi
free_kb=$(df -Pk "$DATA" | awk 'NR==2 {print $4}')
if [ "${#data_parts[@]}" -gt 0 ]; then
  need_kb=$(( $(du -Lck "${data_parts[@]}" | tail -1 | cut -f1) * 3 ))
  [ "$free_kb" -gt "$need_kb" ] || echo "warning: only $((free_kb / 1024)) MB free in $DATA; unpacking the data archive needs about $((need_kb / 1024)) MB" >&2
fi
if [ "${#raw_parts[@]}" -gt 0 ]; then
  need_kb=$(( $(du -Lck "${raw_parts[@]}" | tail -1 | cut -f1) + 262144 ))   # a plain tar unpacks to its own size
  if [ "$free_kb" -le "$need_kb" ]; then
    echo "not enough free disk in $DATA for the raw archive: $((free_kb / 1024)) MB free, about $((need_kb / 1024)) MB needed. Free some space, or skip it with RAW=0 / --no-raw (nothing was unpacked)" >&2; exit 1
  fi
fi
if [ "${#data_parts[@]}" -gt 0 ]; then
  echo "unpacking the data archive into $DATA ..."
  cat "${data_parts[@]}" | tar -xzf - -C "$DATA"
fi
if [ "${#raw_parts[@]}" -gt 0 ]; then
  echo "unpacking the raw archive into $DATA ..."
  cat "${raw_parts[@]}" | tar -xf - -C "$DATA"
fi
if [ "${#data_parts[@]}" -gt 0 ] || [ "$only_raw" = 1 ]; then
  [ -f "$bundle/bundle_manifest.json" ] && cp "$bundle/bundle_manifest.json" "$DATA/bundle_manifest.json"   # the bundle folder's copy also records the raw archive
fi
"$PY" scripts/_data_bundle.py check "$DATA" "$bundle/bundle_manifest.json" $([ "${#raw_parts[@]}" -gt 0 ] && echo raw)
echo "installed. Models are not part of the bundle: see MODELS.txt in the bundle and \`make models\`."
