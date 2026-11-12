# API reference

The live API is served by `vakeel_sahayak.api.asgi:app`.

- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI document: `http://localhost:8000/openapi.json`
- Versioned export: `docs/api/openapi.json`

Start it locally with:

```bash
.venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8000
```

All product endpoints live under `/api`. The schema is the source of truth for request bodies, response models, status codes and examples. Endpoint groups are:

| Group | Purpose |
|---|---|
| `/api/cases` | Case creation, dossier, dates, rights, drafting, brief, sparring, hearing preparation and budgets. |
| `/api/cases/{case_id}/upload`, `/audio` | Local-file upload and dictated-audio intake. |
| `/api/cases/{case_id}/chat`, `/events` | Counsel chat/history and replayable server-sent events. |
| `/api/cases/{case_id}/gates`, `/export` | Gate checklist/approval and counsel-gated document export. Export remains unavailable before Gate 2. |
| `/api/desk` | Batch intake and the triage board. |
| `/api/library` | Precedent search, citation graph and IPC-to-BNS bridge. |

If `VS_API_TOKEN` is set, send `Authorization: Bearer <token>` on `/api` requests. The OpenAPI export contains no keys or case data. Regenerate it after an API-schema change with:

```bash
.venv/bin/python -c 'import json; from vakeel_sahayak.api.asgi import app; open("docs/api/openapi.json", "w").write(json.dumps(app.openapi(), indent=2) + "\\n")'
```
