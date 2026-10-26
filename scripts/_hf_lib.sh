#!/usr/bin/env bash
# Shared helpers for the scripts that talk to the Hugging Face Hub (sourced by data_install.sh, data_ensure.sh, data_publish.sh). Never prints a token.

# hf_load_token [ENV_FILE]: take HF_TOKEN from the environment, else from the untracked .env (an empty `HF_TOKEN=` line counts as unset).
hf_load_token() {
  local f="${1:-.env}"
  if [ -z "${HF_TOKEN:-}" ] && [ -f "$f" ]; then
    HF_TOKEN="$(sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}HF_TOKEN=//p' "$f" | head -1 | tr -d "\"' \r")"
  fi
  if [ -n "${HF_TOKEN:-}" ]; then export HF_TOKEN; else unset HF_TOKEN; fi
  return 0
}

# hf_has_login: true when `hf auth login` left a token file (HF_HOME or ~/.cache/huggingface).
hf_has_login() {
  [ -s "${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/token" ] || [ -s "$HOME/.huggingface/token" ]
}

# hf_find_bin: set HF to the hf command (HF_BIN, then .venv/bin/hf, then PATH), or print how to get it and return 1.
hf_find_bin() {
  HF="${HF_BIN:-}"
  [ -n "$HF" ] || { [ -x .venv/bin/hf ] && HF=.venv/bin/hf; } || HF="$(command -v hf 2>/dev/null || true)"
  if [ -z "$HF" ]; then
    echo "the hf command (Hugging Face CLI) is not installed. Run: make setup   (or: .venv/bin/pip install -U huggingface_hub)" >&2
    return 1
  fi
}

hf_access_help() {   # $1 = repo
  cat >&2 <<MSG
Hugging Face refused access to the dataset $1 (HTTP 401, 403 or 404). Check, in this order:
  1. A token is present: HF_TOKEN=hf_... in the untracked .env (or exported), or run: hf auth login
  2. You are a member of the Hugging Face organisation Vakeel-Sahayak: accept the invitation in your e-mail or at
     https://huggingface.co/Vakeel-Sahayak, or ask the owner to add you. A private dataset answers 404 to non-members.
  3. The token may read the organisation: with a fine-grained token open https://huggingface.co/settings/tokens, edit it and, under
     "Org permissions", add Vakeel-Sahayak with "Read access to contents of all repos". A token without that scope gets 403 even for members.
     (Or create a classic "Read" token.) Then put the new token in .env and run the command again.
MSG
}

# hf_set_timeouts: slow-link defaults (the user can override both).
hf_set_timeouts() {
  export HF_HUB_DOWNLOAD_TIMEOUT="${HF_HUB_DOWNLOAD_TIMEOUT:-60}" HF_HUB_ETAG_TIMEOUT="${HF_HUB_ETAG_TIMEOUT:-30}"
}

# hf_preflight REPO SCRATCH: whoami, then fetch the tiny SHA256SUMS file so that a missing, wrong or unauthorised token fails in seconds, not after 1 GB.
hf_preflight() {
  local repo="$1" probe="$2/.probe" who out
  if [ -z "${HF_TOKEN:-}" ] && ! hf_has_login; then
    echo "no Hugging Face token: put HF_TOKEN=hf_... in the untracked .env (or export it), or run: hf auth login" >&2
    hf_access_help "$repo"; return 1
  fi
  if ! who="$("$HF" auth whoami 2>&1)"; then
    echo "hf auth whoami failed: the token is missing, expired or wrong (the token itself is not shown)." >&2
    hf_access_help "$repo"; return 1
  fi
  echo "Hugging Face login ok ($(printf '%s' "$who" | head -1 | cut -c1-80))."
  mkdir -p "$probe"
  if ! out="$("$HF" download "$repo" SHA256SUMS --repo-type dataset --local-dir "$probe" 2>&1)"; then
    printf '%s\n' "$out" | tail -3 | sed 's/hf_[A-Za-z0-9]\{8,\}/hf_***/g' >&2
    case "$out" in
      *"401 "*|*"403 "*|*"404 "*|*"Error 40"*|*nauthorized*|*orbidden*|*"Not Found"*|*"not found"*|*gated*|*restricted*) hf_access_help "$repo";;
      *) echo "could not reach Hugging Face (network?). Try again, or set HTTPS_PROXY if you are behind one." >&2;;
    esac
    return 1
  fi
  rm -rf "$probe"
}

# hf_download_retry LOGFILE hf-download-args...: up to HF_TRIES (3) attempts; hf resumes partial files; progress stays visible.
hf_download_retry() {
  local log="$1" n=0 tries="${HF_TRIES:-3}"; shift
  : >"$log"
  while :; do
    n=$((n + 1))
    if "$HF" download "$@" --max-workers "${HF_MAX_WORKERS:-2}" 2>&1 | tee -a "$log"; then return 0; fi
    if grep -q "40[13] Client Error\|HTTP.\{0,3\}40[13]\|nauthorized\|orbidden" "$log"; then return 2; fi
    [ "$n" -lt "$tries" ] || return 1
    echo "download attempt $n of $tries failed; retrying in ${HF_RETRY_SLEEP:-5} s (finished files are kept and the rest resumes) ..." >&2
    sleep "${HF_RETRY_SLEEP:-5}"
  done
}
