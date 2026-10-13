"""FastAPI application factory; mounts routers; the demo reaches Ada's 14B agents over an SSH tunnel (plan §13.1)."""

from __future__ import annotations

from fastapi import FastAPI


def create_app(config_dir: str | None = None) -> FastAPI:
    """Create the app, include routers, configure CORS for the Next.js dev server.

    Args:
        config_dir: see behaviour

    Returns:
        FastAPI app.
    """
    raise NotImplementedError
