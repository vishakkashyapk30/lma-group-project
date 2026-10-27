"""Optional bearer token for counsel's actions (VS_API_TOKEN): off by default, 401/403 on writes when on, reads and /healthz open unless VS_API_TOKEN_READS=1."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from tests.unit.api._helpers import CASE, G1, scenario
from vakeel_sahayak.api import auth
from vakeel_sahayak.api.asgi import build
from vakeel_sahayak.schemas.enums import EventKind

TOKEN = "s3cret-token-value"
APPROVE = f"/api/cases/{CASE}/gates/{G1}/approve"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("VS_API_TOKEN", raising=False)
    monkeypatch.delenv("VS_API_TOKEN_READS", raising=False)


def test_decide_unit_rules():
    assert auth.decide("POST", "/api/x", None, token=None) is None  # off
    assert auth.decide("POST", "/api/x", None, token="") is None
    assert auth.decide("POST", "/api/x", None, token=TOKEN)[0] == 401
    assert auth.decide("POST", "/api/x", "Basic abc", token=TOKEN)[0] == 401
    assert auth.decide("POST", "/api/x", "Bearer ", token=TOKEN)[0] == 401
    assert auth.decide("POST", "/api/x", "Bearer nope", token=TOKEN)[0] == 403
    assert auth.decide("POST", "/api/x", f"bearer {TOKEN}", token=TOKEN) is None
    assert auth.decide("GET", "/api/x", None, token=TOKEN, reads=False) is None
    assert auth.decide("GET", "/api/x", None, token=TOKEN, reads=True)[0] == 401
    assert auth.decide("OPTIONS", "/api/x", None, token=TOKEN, reads=True) is None
    assert auth.decide("GET", "/healthz", None, token=TOKEN, reads=True) is None
    assert auth.decide("GET", "/docs", None, token=TOKEN, reads=True) is None


def test_default_is_unchanged_without_a_token(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    res = sc.client().post(APPROVE, json={"acknowledged_fields": ["antecedents"]})
    assert res.status_code == 200 and len(sc.events(EventKind.GATE_APPROVED)) == 1


def test_writes_need_the_token_and_nothing_is_recorded_without_it(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_API_TOKEN", TOKEN)
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(approve_gate1=False)
    client = sc.client()
    body = {"acknowledged_fields": ["antecedents"]}
    r = client.post(APPROVE, json=body)
    assert r.status_code == 401 and "authorization required" in r.json()["detail"] and r.headers["www-authenticate"] == "Bearer"
    assert client.post(APPROVE, json=body, headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert sc.events(EventKind.GATE_APPROVED) == []
    ok = client.post(APPROVE, json=body, headers={"Authorization": f"Bearer {TOKEN}"})
    assert ok.status_code == 200 and len(sc.events(EventKind.GATE_APPROVED)) == 1
    for path in (f"/api/cases/{CASE}/draft", f"/api/cases/{CASE}/export", "/api/export", f"/api/cases/{CASE}/upload", "/api/cases"):
        assert client.post(path, json={}).status_code in (401, 403), path  # export, upload, draft and case creation are all behind the token
    assert client.get(f"/api/cases/{CASE}/rights").status_code != 401  # reads stay open


def test_reads_can_be_gated_too_and_healthz_stays_open(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_API_TOKEN", TOKEN)
    monkeypatch.setenv("VS_API_TOKEN_READS", "1")
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record()
    client = sc.client()
    assert client.get(f"/api/cases/{CASE}/rights").status_code == 401
    assert client.get(f"/api/cases/{CASE}/rights", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    assert build().router is not None
    assert TestClient(build()).get("/healthz").status_code == 200


def test_the_token_is_never_logged_or_echoed(monkeypatch, caplog):
    monkeypatch.setenv("VS_API_TOKEN", TOKEN)
    client = TestClient(build())
    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/cases", json={}, headers={"Authorization": "Bearer guess-guess"})
    assert r.status_code == 403 and "guess-guess" not in r.text and TOKEN not in r.text
    assert TOKEN not in caplog.text and "guess-guess" not in caplog.text
    assert TOKEN not in str(TestClient(build()).get("/healthz").json())


def test_compare_is_constant_time_function():
    import inspect

    assert "compare_digest" in inspect.getsource(auth.decide)
