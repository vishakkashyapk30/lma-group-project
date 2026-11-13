#!/usr/bin/env bash
# Start a usable local Vakeel-Sahayak.ai stack from a checkout.
#
#   ./install.sh                 # offline stack, seed it with the local/team data bundle, then start it
#   ./install.sh --skip-data     # start the offline stack without stores (API/UI diagnostics only)
#   ./install.sh --real          # start the separate NVIDIA/vLLM profile after the normal checks
#   ./install.sh --no-start      # perform checks and data setup, but do not start containers
#
# The default never enables an external provider and never reads a secret from
# `.env`.  `make data` itself handles HF_TOKEN / an authenticated `hf` login.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: ./install.sh [--skip-data] [--real] [--no-start] [--help]

Checks Docker, free space and the configured localhost ports; ensures the team
data bundle is installed; seeds Docker's persistent data volume; then starts
the offline stack at http://127.0.0.1:${FRONTEND_PORT:-3000}.

--skip-data  Do not install or seed stores. Use only to inspect the empty API/UI.
--real       Start the separate NVIDIA/vLLM profile (http://127.0.0.1:3001).
--no-start   Stop after checks and data setup.
EOF
}

seed_data=1
real=0
start=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-data) seed_data=0 ;;
    --real) real=1 ;;
    --no-start) start=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }
}

need docker
docker compose version >/dev/null 2>&1 || {
  echo "Docker Compose v2 is required. Install the Docker Engine Compose plugin (docker-compose-plugin)." >&2
  exit 1
}

free_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
min_kb=$(( ${VS_INSTALL_MIN_FREE_GB:-8} * 1024 * 1024 ))
if [ "$free_kb" -lt "$min_kb" ]; then
  echo "only $((free_kb / 1024 / 1024)) GB free; need at least ${VS_INSTALL_MIN_FREE_GB:-8} GB for images, the data volume and case files." >&2
  echo "Free disk space or set VS_INSTALL_MIN_FREE_GB only if you understand the reduced safety margin." >&2
  exit 1
fi

env_value() {
  local key="$1" fallback="$2" value
  value="$(sed -n -E "s|^[[:space:]]*${key}=([^#[:space:]]+).*|\\1|p" .env 2>/dev/null | tail -n 1 || true)"
  value="${value%\"}"; value="${value#\"}"; value="${value%\'}"; value="${value#\'}"
  printf '%s' "${value:-$fallback}"
}

frontend_port="$(env_value FRONTEND_PORT 3000)"
backend_port="$(env_value BACKEND_PORT 8000)"
port_busy() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then ss -ltn "sport = :$port" 2>/dev/null | grep -q LISTEN
  elif command -v lsof >/dev/null 2>&1; then lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
  else return 1
  fi
}
existing_backend="$(docker compose ps -q backend 2>/dev/null || true)"
for port in "$frontend_port" "$backend_port"; do
  if port_busy "$port"; then
    if [ -z "$existing_backend" ]; then
      echo "port $port is already in use. Stop its owner or set FRONTEND_PORT/BACKEND_PORT in .env before installing." >&2
      exit 1
    fi
    echo "port $port is already occupied by the existing Compose stack; it will be reused."
  fi
done

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "created untracked .env from .env.example"
fi

if [ "$real" = 1 ]; then
  need nvidia-smi
  docker info 2>/dev/null | grep -qi nvidia || {
    echo "the Docker NVIDIA runtime is unavailable. Install NVIDIA Container Toolkit before using --real." >&2
    exit 1
  }
  echo "NVIDIA GPU detected: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)"
fi

host_data="${VS_DATA_DIR:-$ROOT/data}"
if [ "$seed_data" = 1 ] && [ ! -s "$host_data/stores/law/statutes.sqlite" ]; then
  need make
  echo "local stores are missing; installing the team bundle (requires HF_TOKEN or 'hf auth login') ..."
  make setup
  make data
fi

if [ "$start" = 0 ]; then
  echo "checks complete; no containers started (--no-start)."
  exit 0
fi

if [ "$real" = 1 ]; then
  docker compose --profile real up -d --build --wait vllm backend-real frontend-real
  echo "Vakeel-Sahayak.ai real profile is ready at http://127.0.0.1:$(env_value FRONTEND_REAL_PORT 3001)"
  exit 0
fi

docker compose up -d --build --wait

volume=""
if [ "$seed_data" = 1 ]; then
  [ -s "$host_data/stores/law/statutes.sqlite" ] || {
    echo "data setup completed without a statute store at $host_data; refusing to claim a usable product." >&2
    exit 1
  }
  backend_id="$(docker compose ps -q backend)"
  volume="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' "$backend_id")"
  [ -n "$volume" ] || { echo "could not locate the backend data volume" >&2; exit 1; }
  if ! docker run --rm -v "$volume:/target" alpine sh -c 'test -s /target/stores/law/statutes.sqlite'; then
    echo "seeding the persistent Docker volume from $host_data ..."
    docker run --rm -u 0 -v "$volume:/target" -v "$host_data:/source:ro" alpine sh -c \
      'cp -a /source/interim /source/stores /source/testsets /source/gaps /source/eval /target/ 2>/dev/null || true; chown -R 10001:10001 /target'
    docker compose restart backend frontend
  fi
fi

echo "Vakeel-Sahayak.ai is ready at http://127.0.0.1:$frontend_port"
if [ -n "$volume" ]; then
  echo "Persistent cases are in Docker volume '$volume'. Stop with: docker compose down (do not add -v unless you mean to erase cases)."
fi
