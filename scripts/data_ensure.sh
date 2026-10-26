#!/usr/bin/env bash
# `make data`: make sure the data a teammate cannot rebuild cheaply is in data/.
#
#   1. data/stores exists and `make data-check` passes: do nothing (exit 0).
#   2. else, with a Hugging Face token (HF_TOKEN in the environment or the untracked .env, or `hf auth login`): install the team bundle
#      (scripts/data_install.sh hf:Vakeel-Sahayak/vakeel-sahayak-data; FORCE=1 overwrites a partial data/).
#      Slow link or tight disk: HF_HUB_DOWNLOAD_TIMEOUT (60), HF_HUB_ETAG_TIMEOUT (30), HF_MAX_WORKERS (2), HF_TRIES (3), TMPDIR, VS_DOWNLOAD_DIR, RAW=0.
#   3. else print the two options and exit 1: ask the owner for access to the private dataset, or rebuild (make datasets interim stores).
#
# VS_DATA_DIR, PY, ENV_FILE (default .env) and BUNDLE_REPO (default Vakeel-Sahayak/vakeel-sahayak-data) are honoured. The token is never printed.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
command -v "$PY" >/dev/null 2>&1 || { echo "no $PY: run make setup first (it creates .venv and installs what the data scripts need)" >&2; exit 1; }
# shellcheck source=scripts/_hf_lib.sh
. scripts/_hf_lib.sh
DATA="${VS_DATA_DIR:-data}"
REPO="${BUNDLE_REPO:-Vakeel-Sahayak/vakeel-sahayak-data}"

if [ -d "$DATA/stores" ] && "$PY" scripts/_data_check.py --data "$DATA" >/dev/null 2>&1; then
  echo "data is in place ($DATA/stores exists and make data-check passes): nothing to do."
  exit 0
fi

export ENV_FILE="${ENV_FILE:-.env}"
hf_load_token "$ENV_FILE"
if [ -n "${HF_TOKEN:-}" ] || hf_has_login; then   # a token in the environment or .env, or a login left by `hf auth login`
  echo "data is missing or incomplete; installing the team bundle from hf:$REPO ..."
  # data_install.sh checks the token and the organisation access first (hf auth whoami, then a tiny file) and explains any 401 or 403.
  # Tight disk: TMPDIR=/bigger/disk make data (the download scratch); RAW=0 make data skips the 1.8 GB raw archive.
  exec scripts/data_install.sh $([ "${FORCE:-0}" = 1 ] && echo --force) "hf:$REPO"
fi

cat >&2 <<MSG
The data folder ($DATA) is missing or incomplete, and there is no Hugging Face token (HF_TOKEN in the environment or in .env).
Two ways forward:
  1. Ask the owner for read access to the private dataset $REPO, then put HF_TOKEN=... in .env
     (or run: hf auth login) and run: make data      (FORCE=1 make data overwrites a partial data/)
  2. Rebuild from the public sources (hours; see data/README.md):  make datasets interim stores
Then check what is there:  make data-check
MSG
exit 1
