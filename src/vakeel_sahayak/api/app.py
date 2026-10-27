"""FastAPI application factory; mounts routers; the demo reaches Ada's 14B agents over an SSH tunnel (plan §13.1)."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vakeel_sahayak.api.auth import BearerTokenMiddleware
from vakeel_sahayak.api.routers import cases, chat, desk, events, export, gates, library, upload

ROUTERS = (cases, upload, chat, events, gates, export, desk, library)


def _origins() -> list[str]:
    raw = os.environ.get("VS_CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(config_dir: str | None = None) -> FastAPI:
    """Create the app, include routers, configure CORS for the Next.js dev server.

    Args:
        config_dir: config directory; when given it sets `VS_CONFIG_DIR` for the dependencies (plan §13.1).

    Returns:
        FastAPI app serving `/api/...` (plus FastAPI's own docs routes).
    """
    if config_dir:
        os.environ["VS_CONFIG_DIR"] = config_dir
    app = FastAPI(title="Vakeel-Sahayak.ai", description="Bail-preparation assistant API (plan §13).")
    # `include_router` wires each router so routing and `dependency_overrides` work (this FastAPI resolves included
    # routers lazily at request time). It also means the routes do not appear in `app.routes` until the app is built, so
    # we additionally append each router's concrete routes for enumeration (route-listing tests, OpenAPI). Routing still
    # goes through the included routers, which are matched first; the appended copies are never matched.
    for module in ROUTERS:
        app.include_router(module.router)
    for module in ROUTERS:
        app.router.routes.extend(module.router.routes)
    app.add_middleware(BearerTokenMiddleware)  # opt-in (VS_API_TOKEN); added first so CORS stays outermost and 401/403 answers carry the CORS headers
    app.add_middleware(
        CORSMiddleware, allow_origins=_origins(), allow_methods=["*"], allow_headers=["*"], allow_credentials=False
    )
    return app
