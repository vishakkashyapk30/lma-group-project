#!/usr/bin/env bash
# Live demo: reach the model server of an Ada interactive session from the laptop through an SSH tunnel (plan §13.1, §17). Fallback: Qwen3-8B 4-bit on the laptop.
# 1. In the GPU session: bash scripts/ada/serve_qwen32b.sh   (it prints the node name and READY; the endpoint is port 8000 on that node)
# 2. On the laptop:      NODE=<node name> bash scripts/ada/tunnel_demo.sh      (keeps running; Ctrl-C closes the tunnel)
# Env: NODE (required), ADA_HOST (the ssh alias of the gateway, default ada), LOCAL_PORT (default 8001), REMOTE_PORT (default 8000).
# Then run the app with VS_LLM_BACKEND=local and the vLLM base URL http://localhost:$LOCAL_PORT/v1 (configs/models.yaml, role `teacher`). Nothing but the model's prompts and answers crosses the tunnel.
set -euo pipefail
NODE="${NODE:?set NODE to the compute node that serve_qwen32b.sh printed, for example NODE=gnode042}"
HOST="${ADA_HOST:-ada}"; LP="${LOCAL_PORT:-8001}"; RP="${REMOTE_PORT:-8000}"
echo "tunnel: localhost:$LP -> $NODE:$RP via $HOST  (VS_LLM_BACKEND=local, base URL http://localhost:$LP/v1)"
exec ssh -N -o ExitOnConfigFailure=yes -o ServerAliveInterval=30 -L "$LP:$NODE:$RP" "$HOST"
