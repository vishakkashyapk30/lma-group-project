"""ASGI entry point for containers: `uvicorn vakeel_sahayak.api.asgi:app`.

Wraps `create_app()` so the service can start before the Phase 5 routers exist: it always serves `GET /healthz`, applies CORS
from `VS_CORS_ORIGINS` (comma separated, default http://localhost:3000) and, while `create_app()` is still a stub, answers
`/api/*` with 503 so the frontend falls back to its built-in demo mode (it does that on 5xx and network errors, not on 404).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vakeel_sahayak.api.app import create_app


def _origins() -> list[str]:
    raw = os.environ.get("VS_CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def _settings() -> dict[str, object]:
    """The server's effective model and privacy settings for the frontend's Settings page (read-only; never a key or a secret).

    `models` (VS_MODELS: offline | real | auto), `llm_backend` (VS_LLM_BACKEND, None when each role follows configs/models.yaml),
    `external` (VS_EXTERNAL: the shared gate for hosted services), `sarvam` and `openai` (each provider's effective mode) and `data_dir`.
    A setting that cannot be read is reported as None rather than failing the health check.
    """
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.models.factory import llm_backend, models_mode
    from vakeel_sahayak.models.sarvam.policy import provider_mode

    out: dict[str, object] = {}
    readers = {
        "models": models_mode,
        "llm_backend": llm_backend,
        "external": lambda: (os.environ.get("VS_EXTERNAL") or "off").strip().lower(),
        "sarvam": lambda: provider_mode("sarvam").value,
        "openai": lambda: provider_mode("openai").value,
        "data_dir": lambda: str(load_config().paths.data_dir),
    }
    for key, read in readers.items():
        try:
            out[key] = read()
        except Exception:  # noqa: BLE001 - a broken setting must not take the health check down
            out[key] = None
    return out


def build() -> FastAPI:
    """Return the real app when implemented, otherwise a skeleton that reports 503 for every /api route."""
    try:
        application = create_app(os.environ.get("VS_CONFIG_DIR"))
        implemented = True
    except NotImplementedError:
        application = FastAPI(title="Vakeel-Sahayak.ai (skeleton)")
        implemented = False

        @application.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
        async def _not_implemented(path: str) -> JSONResponse:
            return JSONResponse({"detail": "API routes are not implemented yet (Phase 5)"}, status_code=503)

    if not any(getattr(r, "path", None) == "/healthz" for r in application.routes):

        @application.get("/healthz", include_in_schema=False)
        async def _healthz() -> dict[str, object]:
            return {"status": "ok", "api_implemented": implemented, **_settings()}

    if not any(isinstance(m.cls, type) and m.cls is CORSMiddleware for m in application.user_middleware):
        application.add_middleware(
            CORSMiddleware, allow_origins=_origins(), allow_methods=["*"], allow_headers=["*"], allow_credentials=False
        )
    return application


app = build()
