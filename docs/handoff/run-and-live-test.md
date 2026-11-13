# Running the app and the live end-to-end test (handoff)

How to start the whole stack, use it, and run `frontend/e2e/live_flow.spec.ts` against the real API. Written 13 Nov 2026 after the first complete live run. Models are the offline stand-ins, so the drafts are placeholders: this checks the flow and the gates, not legal quality.

## Run and use the app (Docker)
```bash
cd <repo root>
./install.sh                     # first time: checks Docker, disk and ports, seeds the vs_data volume from data/, builds and starts
docker compose up -d --build     # later starts (drop --build when no code changed)
docker compose ps                # backend and frontend should both be running
```
UI http://localhost:3000, API http://localhost:8000 (Swagger at `/docs`).

1. Open `/cases`, click **New case**, upload a PDF (for example `data/testsets/t2/bundles/t1-003_K1.pdf`).
2. Stages: Add documents, Review facts (confirm to pass Gate 1), Check rights, Draft grounds, Prepare for the hearing, Export (approve Gate 2, then download).
3. Export is refused until Gate 2 is approved.

```bash
docker compose logs -f backend          # live API log
docker compose down                     # stop, keep data
docker compose down -v                  # stop and delete the data volume (seed again afterwards)
```

## Run without Docker
```bash
# terminal 1, repo root
source .venv/bin/activate
VS_MODELS=offline VS_LLM_BACKEND=offline python -m uvicorn vakeel_sahayak.api.asgi:app --port 8000

# terminal 2
cd frontend && npm ci
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build
NEXT_PUBLIC_API_BASE=http://localhost:8000 npx next start -p 3000
```
`NEXT_PUBLIC_API_BASE` is baked in at build time: it must be set on `npm run build`, not only on `next start`. A build without it runs in sample-data mode.

## Run the live end-to-end test
Start the stack first and check all three answer before running the test:
```bash
docker compose ps
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/openapi.json    # 200
curl -s -o /dev/null -w "%{http_code}\n" localhost:3000                 # 200
```
Then:
```bash
cd frontend
npm ci                           # once
E2E_LIVE_API=1 npx playwright test e2e/live_flow.spec.ts --project=chromium            # headless
E2E_LIVE_API=1 npx playwright test e2e/live_flow.spec.ts --project=chromium --headed   # watch it
```
The test creates a case, uploads the bundle, confirms the facts (Gate 1), checks rights, drafts, resolves what Gate 2 needs, reads the hearing card, approves Gate 2, exports and downloads the application. It fails on any 5xx from `/api/`. It takes up to 15 minutes; the first complete run took 44 s. It skips itself without `E2E_LIVE_API=1` or without the bundle (`E2E_LIVE_PDF` overrides the path).

The other Playwright specs mock the backend and need no stack: `npx playwright test --project=chromium` (145 passed, 1 skipped on 12 Nov). Unit tests: `npm test`, `npm run typecheck`.

## Failures we hit, and the cause
| Symptom | Cause | Fix |
|---|---|---|
| Mode chip says "Local · Sample data" and the first check fails | Nothing answered on port 3000, so Playwright started its own `next dev` with no API address | Start the stack first; check the three commands above |
| `Gate 2 has not been opened: no brief to approve yet`, `budget_exhausted` in the planner events | The data directory had no stores (an empty `VS_DATA_DIR`, or an unseeded Docker volume) | Use `./install.sh` (seeds the volume), or leave `VS_DATA_DIR` unset so the repo's `data/` is used |
| Docker build stops on `react/no-unescaped-entities` in `AboutPage.tsx` | `next build` lints; the dev server does not | Escape the apostrophe (`&apos;`); run `npx next lint` before a Docker build |
| `ports are not available ... 8000: address already in use` | A leftover uvicorn or `next start` | `lsof -i :8000 -i :3000`, then `kill <pid>` |
| `application.docx` served as `application/octet-stream` | `FileResponse` guessed the type from the name; the slim image has no MIME table | The media type is now set in `api/routers/export.py` (test in `tests/unit/api/test_export_router.py`); rebuild the backend image |

## Not done
Hindi interface labels (no translation layer yet; Sarvam is locked unless the owner sets `VS_ALLOW_PAID`), the Gemini shard (needs a personal key), and a look at the withheld-sentence and grouped-objection views in a browser.
