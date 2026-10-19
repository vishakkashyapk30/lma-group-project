# Running Vakeel-Sahayak.ai with Docker

One command from the repo root starts everything needed:

```bash
docker compose up            # or: make docker-up (detached, waits until healthy)
```

Open http://localhost:3000. Stop with `docker compose down` (named volumes are kept; `down -v` deletes the data).
Copy `.env.example` to an untracked `.env` to change ports, models or tags. Every variable is documented there.

## What starts by default

| Service | Image | Port | Notes |
|---|---|---|---|
| `backend` | `python:3.12-slim`, core dependencies only (no torch, no vLLM) | 8000 | uvicorn `vakeel_sahayak.api.asgi:app`, `VS_MODELS=offline`, `GET /healthz` |
| `frontend` | `node:20-alpine`, Next.js standalone build | 3000 | starts after the backend is healthy |

* Ports bind to `127.0.0.1` (`BIND_ADDR`) so nothing is exposed to the network by default (plan section 16).
* Data lives in the named volume `vs_data` (mounted at `/app/data`: stores, case event logs, SQLite files).
* Containers run as non-root with a read-only root filesystem, tmpfs `/tmp`, all capabilities dropped, `restart: unless-stopped`.
* The API routes are still stubs (Phase 5). `vakeel_sahayak.api.asgi` serves `/healthz` and answers `/api/*` with 503 while
  `create_app()` raises `NotImplementedError`; the frontend reacts to 5xx by switching to its built-in demo mode (case-0007), so
  the UI works. Once Phase 5 lands, the same entry point serves the real app.
* The browser talks to the backend through a same-origin proxy: `NEXT_PUBLIC_API_BASE=/backend`, and the Next server rewrites
  `/backend/*` to `http://backend:8000/*`. This works from any host without CORS. `NEXT_PUBLIC_*` values and the rewrite target
  are fixed at build time: after changing `NEXT_PUBLIC_API_BASE`, run `docker compose build frontend`.
  Set it to `http://localhost:8000` for direct browser-to-backend calls (then `VS_CORS_ORIGINS` must list the frontend origin), or
  `demo` to never probe the backend.

## Profiles (not started by default)

### `real`: real models on a local NVIDIA GPU machine

```bash
docker compose --profile real up vllm backend-real frontend-real     # UI on http://localhost:3001
```

* Needs the NVIDIA Container Toolkit (`docker info` must list an `nvidia` runtime) and a GPU with enough memory for
  Qwen3-14B-AWQ (about 24 GB is comfortable; lower `VLLM_GPU_UTIL` / `VLLM_MAX_MODEL_LEN` otherwise).
* Downloads multi-GB weights into the `hf_cache` volume on first start (set `HF_TOKEN` if a model is gated); the first start is slow.
* `backend-real` is built with `EXTRAS=ocr,speech,models,vision,translation` (a multi-GB image) and `VS_MODELS=real`.
* On the Ada cluster the team uses interactive sessions instead (plan section 17); this profile is for a local GPU machine.
* The real stack runs next to, and independently of, the default pair (ports 8001/3001) so the profile cannot clash with it.
  This profile has been validated with `docker compose --profile real config` only; it has not been run.

### `test`: tests inside containers

```bash
docker compose --profile test run --rm tests                 # pytest tests/unit tests/integration tests/system
docker compose --profile test run --rm tests pytest tests/unit/schemas tests/unit/stores tests/unit/ingestion   # chosen phases
docker compose --profile test run --rm frontend-tests        # Vitest
docker compose --profile test up -d frontend && docker compose --profile test run --rm e2e   # Playwright against the running frontend
```

Phases 1 to 3 are implemented (progress.md section 5); tests of later phases fail until their modules exist. The default pytest
markers skip `gpu` and `models` tests. The `e2e` service uses the official `mcr.microsoft.com/playwright` image matching
`@playwright/test` (`PLAYWRIGHT_VERSION`) and shares the frontend container's network, so `localhost:3000` is the production server;
the specs mock the backend themselves.

### `data`: dataset pipeline

```bash
docker compose --profile data run --rm data                  # runs scripts/build_stores.sh in the vs_data volume
docker compose --profile data run --rm data -c 'exec bash scripts/build_stores.sh --only reasoning citations'
```

The datasets (Open India Law, IPC2BNS-Verify) are not downloaded by this job: run `make datasets` and `make interim` on the host first (they write
`data/interim/orders.jsonl`, `statutes.jsonl` and `concordance_edges.jsonl`; see `data/README.md`). The job exits with code 2 and an error message if
`/app/data/interim/orders.jsonl` is absent or empty. Load inputs into the volume, for example:

```bash
docker run --rm -v vakeel-sahayak_vs_data:/d -v "$PWD/data/interim:/src:ro" alpine sh -c 'mkdir -p /d/interim && cp /src/orders.jsonl /src/statutes.jsonl /src/concordance_edges.jsonl /src/splits.json /d/interim/ && chown -R 10001:10001 /d'
```

## Sarvam AI (external, off by default)

Sarvam is a third-party API. `VS_SARVAM` defaults to `off`: no request leaves the machine. The key is read only from the
environment: put `SARVAM_API_KEY` in your untracked `.env` or shell. Compose passes it to the backend only as a runtime environment
variable (empty if unset); it is never in an image, label or log. Modes (`src/vakeel_sahayak/models/sarvam/policy.py`, `configs/models.yaml`):

* `off`: nothing is sent.
* `public`: public court orders and statute text only.
* `pseudonymised`: public material plus case text after the privacy layer replaced names and identifiers.
* `consented`: additionally raw client pages and audio, only for cases whose counsel recorded a Sarvam consent event.

Raw client files must not leave your machine (plan section 16), so stay at `public` unless you have decided otherwise. Set Sarvam's
workspace data retention to the shortest option before using anything above `public`.

## Make targets

`make docker-build`, `make docker-up`, `make docker-down`, `make docker-test`, `make docker-logs`.

## Image notes

* Backend: a `venv` stage installs from `pyproject.toml` only (BuildKit pip cache), the runtime stage copies the venv, then the source
  last. `--build-arg EXTRAS=...` (comma separated pyproject extras) adds heavy dependencies; build tools never reach the final image.
* Frontend: `npm ci` layer cached on the lockfile, `output: "standalone"`, only `.next/standalone`, `.next/static` and `public` are copied.
* Each build context has its own `.dockerignore` (`/.dockerignore` for the backend, `frontend/.dockerignore`).
