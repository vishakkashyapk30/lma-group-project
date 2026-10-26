#!/usr/bin/env bash
# `make setup`: create .venv, upgrade pip, install the package with the light extras, copy .env.example to .env if there is no .env. Idempotent.
#
#   make setup                         # extras: dev,data,testsets (pytest, ruff, the hf command, pyarrow, test-set builders; no torch, no GPU libraries)
#   make setup-full                    # adds lance,eval,nli,ocr,speech (torch, docling, surya, ...: several GB; the real-model paths)
#   EXTRAS=dev,data,eval make setup    # any comma-separated list of the extras in pyproject.toml
#   PYTHON=python3.12 make setup       # pick the interpreter (needs 3.10 or newer; the default is the first of python3.12, 3.11, 3.10, python3 that is new enough)
#
# Re-running it only refreshes the installed packages. A .venv made with a too-old Python is refused (delete it and run again).
set -euo pipefail
cd "$(dirname "$0")/.."
MIN_MAJOR=3; MIN_MINOR=10
EXTRAS="${EXTRAS:-dev,data,testsets}"
[ "${1:-}" != "--full" ] || EXTRAS="${FULL_EXTRAS:-dev,data,testsets,lance,eval,nli,ocr,speech}"

ok_python() {   # $1 = command: true when it is Python >= 3.10
  command -v "$1" >/dev/null 2>&1 && "$1" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_MAJOR, $MIN_MINOR) else 1)" 2>/dev/null
}

if [ -x .venv/bin/python ]; then
  ok_python .venv/bin/python || { echo ".venv uses a Python older than $MIN_MAJOR.$MIN_MINOR ($(.venv/bin/python -V 2>&1)). Delete it (rm -rf .venv) and run make setup again." >&2; exit 1; }
  echo ".venv exists ($(.venv/bin/python -V 2>&1)); refreshing the packages."
else
  cands=()
  if [ -n "${PYTHON:-}" ]; then
    ok_python "$PYTHON" || { echo "PYTHON=$PYTHON is missing or older than $MIN_MAJOR.$MIN_MINOR." >&2; exit 1; }
    cands=("$PYTHON")
  else
    for c in python3.12 python3.11 python3.10 python3 python; do ok_python "$c" && cands+=("$c"); done
  fi
  if [ "${#cands[@]}" -eq 0 ]; then
    echo "no Python $MIN_MAJOR.$MIN_MINOR or newer found. Install one (Ubuntu: sudo apt install python3 python3-venv; macOS: brew install python@3.12; or conda/uv)," >&2
    echo "then run: make setup   (PYTHON=/path/to/python make setup to pick one)" >&2
    exit 1
  fi
  made=0
  for py in "${cands[@]}"; do   # the first interpreter that can make a venv with pip wins (some builds lack ensurepip)
    echo "creating .venv with $("$py" -V 2>&1) ($(command -v "$py"))"
    if "$py" -m venv .venv >/dev/null 2>&1 && .venv/bin/python -m pip --version >/dev/null 2>&1; then made=1; break; fi
    echo "  that interpreter cannot create a venv with pip; trying the next one" >&2
    rm -rf .venv
  done
  [ "$made" = 1 ] || { echo "could not create .venv with any of: ${cands[*]}. On Debian or Ubuntu install the venv module (sudo apt install python3-venv), or set PYTHON=/path/to/python3.11 make setup." >&2; exit 1; }
fi

PIP=(.venv/bin/python -m pip --disable-pip-version-check)
"${PIP[@]}" install --quiet --upgrade pip
echo "installing vakeel_sahayak[$EXTRAS] (editable) ..."
"${PIP[@]}" install -e ".[$EXTRAS]" || {
  echo "pip install failed (see above). A network problem: run make setup again (finished downloads are cached). A tight disk: set TMPDIR and PIP_CACHE_DIR to a bigger disk, or use fewer extras (EXTRAS=dev make setup)." >&2
  exit 1
}

if [ ! -e .env ] && [ -f .env.example ]; then cp .env.example .env && echo "created .env from .env.example (untracked; put HF_TOKEN and any API keys there)"; fi
.venv/bin/python -c "import vakeel_sahayak" && echo "setup done: use .venv/bin/python and .venv/bin/pytest (next: make hooks, make data, make data-check)."
