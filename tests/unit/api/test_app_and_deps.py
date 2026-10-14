"""`create_app` and the dependencies (plan §13.1): FastAPI app, routers mounted, CORS for the Next.js dev server; the config,
event log and gate guard are resolved through `api.deps`, so tests (and the demo) can override them.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.api._helpers import scenario
from vakeel_sahayak.api import deps
from vakeel_sahayak.api.app import create_app
from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.gates import GateGuard

EXPECTED_ROUTES = {
    ("GET", "/api/cases"), ("POST", "/api/cases"), ("GET", "/api/cases/{case_id}"),
    ("GET", "/api/cases/{case_id}/ingestion"), ("GET", "/api/cases/{case_id}/dossier"),
    ("PATCH", "/api/cases/{case_id}/dossier/{field}"), ("GET", "/api/cases/{case_id}/dates"),
    ("GET", "/api/cases/{case_id}/rights"), ("POST", "/api/cases/{case_id}/draft"), ("GET", "/api/cases/{case_id}/brief"),
    ("GET", "/api/cases/{case_id}/spar"), ("GET", "/api/cases/{case_id}/prep"), ("GET", "/api/cases/{case_id}/budget"),
    ("GET", "/api/cases/{case_id}/files/{doc_id}/pages/{page}"),
    ("POST", "/api/cases/{case_id}/upload"), ("POST", "/api/cases/{case_id}/audio"),
    ("POST", "/api/cases/{case_id}/chat"), ("GET", "/api/cases/{case_id}/chat"),
    ("GET", "/api/cases/{case_id}/events"),
    ("GET", "/api/cases/{case_id}/gates/{gate}"), ("POST", "/api/cases/{case_id}/gates/{gate}/approve"),
    ("POST", "/api/cases/{case_id}/export"),
    ("POST", "/api/desk/upload"), ("GET", "/api/desk/board"), ("POST", "/api/desk/{case_id}/open"),
    ("GET", "/api/library/search"), ("GET", "/api/library/citations/{doc_id}"), ("GET", "/api/library/bridge/{code}/{section}"),
}


def test_dependency_signatures():
    """deps: get_config() -> AppConfig, get_event_log(case_id), get_gate_guard()."""
    assert list(inspect.signature(deps.get_config).parameters) == []
    assert list(inspect.signature(deps.get_event_log).parameters) == ["case_id"]
    assert list(inspect.signature(deps.get_gate_guard).parameters) == []


def test_create_app_signature():
    assert list(inspect.signature(create_app).parameters) == ["config_dir"]


def test_deps_resolve_real_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert isinstance(deps.get_config(), AppConfig)
    assert isinstance(deps.get_gate_guard(), GateGuard)
    assert deps.get_event_log("case-0007") is not None


def test_all_planned_routes_are_mounted():
    """Every route of plan §13.5 exists with its method (cases, upload, chat, events, gates, export, desk, library)."""
    app = create_app()
    mounted = {(m, r.path) for r in app.routes if hasattr(r, "methods") for m in r.methods if m not in ("HEAD", "OPTIONS")}
    assert EXPECTED_ROUTES <= mounted, sorted(EXPECTED_ROUTES - mounted)


def test_no_route_outside_the_api_prefix_except_docs():
    """The app serves /api/... plus FastAPI's own docs routes; nothing else."""
    app = create_app()
    stray = [r.path for r in app.routes if hasattr(r, "path") and not r.path.startswith(("/api", "/docs", "/openapi", "/redoc"))]
    assert stray == []


def test_cors_allows_the_nextjs_dev_server(tmp_path, monkeypatch):
    """The UI (http://localhost:3000) may call the API (plan §13.1)."""
    client = scenario(tmp_path, monkeypatch).client()
    res = client.options("/api/cases", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.parametrize("origin", ["http://evil.example", "https://localhost:9999.evil.example"])
def test_cors_does_not_allow_other_origins(tmp_path, monkeypatch, origin):
    client = scenario(tmp_path, monkeypatch).client()
    res = client.options("/api/cases", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert res.headers.get("access-control-allow-origin") not in (origin, "*")


def test_dependency_override_replaces_the_event_log(tmp_path, monkeypatch):
    """Tests override the log through `app.dependency_overrides` (the convention of tests/README.md)."""
    from fastapi.testclient import TestClient

    from tests.fakes.log import InMemoryEventLog

    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    log = InMemoryEventLog()
    app = create_app()
    app.dependency_overrides[deps.get_event_log] = lambda case_id=None: log
    assert TestClient(app).get("/api/cases/case-0007/dossier").status_code == 404  # the overriding log is empty
