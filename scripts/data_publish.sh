#!/usr/bin/env bash
# Upload the data bundle folder to the private Hugging Face dataset (make data-publish). Run by the owner only, after `make data-bundle`.
#
#   make data-publish                                   # ~/vakeel-data-bundle -> Vakeel-Sahayak/vakeel-sahayak-data
#   scripts/data_publish.sh /path/to/bundle [repo_id]
#   HF_REPO=other/name make data-publish
#   ONLY=raw make data-publish                          # only the raw archive parts (plus the small files); ONLY=data for the data archive
#
# The token is read from the environment (HF_TOKEN) or the untracked .env, passed to `hf` through the environment only, and never printed.
# The bundle's README.md is the dataset card (what is included and excluded and why; attributions: Open India Law CC BY 4.0, IPC2BNS-Verify, Kathbath; HLDC not included; private repo).
# New files only: `hf upload` hashes each file and skips the ones the repository already holds, so a re-run after a rebuild sends only the changed or new parts
# (the .state-* resume files of the bundle folder are never uploaded).
set -euo pipefail
cd "$(dirname "$0")/.."
bundle="${1:-${BUNDLE_DIR:-$HOME/vakeel-data-bundle}}"
repo="${2:-${HF_REPO:-Vakeel-Sahayak/vakeel-sahayak-data}}"
for f in README.md SHA256SUMS bundle_manifest.json; do [ -f "$bundle/$f" ] || { echo "missing $bundle/$f: run make data-bundle first" >&2; exit 1; }; done
ls "$bundle"/data.tar.gz.part-* >/dev/null 2>&1 || { echo "no data parts in $bundle" >&2; exit 1; }
ls "$bundle"/raw.tar.part-* >/dev/null 2>&1 || echo "note: no raw.tar.part-* in $bundle: the raw source data will not be on the dataset (make data-bundle builds it)" >&2
grep -qi "not in it" "$bundle/README.md" || { echo "the dataset card lacks the list of what is excluded and why: rebuild it with make data-bundle" >&2; exit 1; }
grep -q "Open India Law corpus by Vaquill AI" "$bundle/README.md" || { echo "the dataset card lacks the Open India Law attribution" >&2; exit 1; }
. scripts/_hf_lib.sh
hf_load_token .env
[ -n "${HF_TOKEN:-}" ] || { echo "HF_TOKEN is not set (environment or untracked .env); hf auth login also works" >&2; }
hf_find_bin || exit 1
(cd "$bundle" && sha256sum -c --quiet SHA256SUMS) || { echo "checksum verification failed: not uploading" >&2; exit 1; }
echo "uploading $bundle to dataset $repo (private) ..."
inc=()
case "${ONLY:-}" in
  raw) inc=(--include "raw.tar.part-*" --include README.md --include SHA256SUMS --include bundle_manifest.json --include MODELS.txt);;
  data) inc=(--include "data.tar.gz.part-*" --include README.md --include SHA256SUMS --include bundle_manifest.json --include MODELS.txt);;
esac
"$HF" upload "$repo" "$bundle" . --repo-type dataset --private --exclude ".state-*" ${inc[@]+"${inc[@]}"} --commit-message "Data bundle $(date +%Y-%m-%d)" >/dev/null
echo "done: https://huggingface.co/datasets/$repo"
