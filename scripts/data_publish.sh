#!/usr/bin/env bash
# Upload the data bundle folder to the private Hugging Face dataset (make data-publish). Run by the owner only, after `make data-bundle`.
#
#   make data-publish                                   # ~/vakeel-data-bundle -> Vakeel-Sahayak/vakeel-sahayak-data
#   scripts/data_publish.sh /path/to/bundle [repo_id]
#   HF_REPO=other/name make data-publish
#
# The token is read from the environment (HF_TOKEN) or the untracked .env, passed to `hf` through the environment only, and never printed.
# The bundle's README.md is the dataset card (attributions: Open India Law CC BY 4.0, IPC2BNS-Verify, Kathbath; HLDC not included; private repo).
set -euo pipefail
cd "$(dirname "$0")/.."
bundle="${1:-${BUNDLE_DIR:-$HOME/vakeel-data-bundle}}"
repo="${2:-${HF_REPO:-Vakeel-Sahayak/vakeel-sahayak-data}}"
for f in README.md SHA256SUMS bundle_manifest.json; do [ -f "$bundle/$f" ] || { echo "missing $bundle/$f: run make data-bundle first" >&2; exit 1; }; done
ls "$bundle"/data.tar.gz.part-* >/dev/null 2>&1 || { echo "no data parts in $bundle" >&2; exit 1; }
grep -q "Open India Law corpus by Vaquill AI" "$bundle/README.md" || { echo "the dataset card lacks the Open India Law attribution" >&2; exit 1; }
if [ -z "${HF_TOKEN:-}" ] && [ -f .env ]; then HF_TOKEN="$(sed -n 's/^HF_TOKEN=//p' .env | head -1 | tr -d "\"' ")"; export HF_TOKEN; fi
[ -n "${HF_TOKEN:-}" ] || { echo "HF_TOKEN is not set (environment or untracked .env); hf auth login also works" >&2; }
command -v hf >/dev/null 2>&1 || { echo "the hf command is not installed (pip install -U huggingface_hub)" >&2; exit 1; }
(cd "$bundle" && sha256sum -c --quiet SHA256SUMS) || { echo "checksum verification failed: not uploading" >&2; exit 1; }
echo "uploading $bundle to dataset $repo (private) ..."
hf upload "$repo" "$bundle" . --repo-type dataset --private --commit-message "Data bundle $(date +%Y-%m-%d)" >/dev/null
echo "done: https://huggingface.co/datasets/$repo"
