"""GET /healthz reports the server's effective model and privacy settings for the Settings page, and never a key (plan §13.5, §16)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from vakeel_sahayak.api.asgi import build

SETTINGS = {"models", "llm_backend", "external", "sarvam", "openai", "data_dir"}


def test_healthz_lists_the_settings(monkeypatch):
    monkeypatch.setenv("VS_MODELS", "offline")
    monkeypatch.setenv("VS_EXTERNAL", "off")
    monkeypatch.delenv("VS_SARVAM", raising=False)
    body = TestClient(build()).get("/healthz").json()
    assert body["status"] == "ok" and SETTINGS <= set(body)
    assert body["models"] == "offline" and body["external"] == "off" and body["sarvam"] == "off" and body["openai"] == "off"


def test_healthz_follows_the_environment(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.setenv("VS_SARVAM", "public")
    body = TestClient(build()).get("/healthz").json()
    assert body["external"] == "pseudonymised" and body["sarvam"] == "public" and body["openai"] == "pseudonymised"


def test_healthz_never_carries_a_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("SARVAM_API_KEY", "sv-test-not-a-real-key")
    text = json.dumps(TestClient(build()).get("/healthz").json())
    assert "not-a-real-key" not in text and "api_key" not in text.lower()


def test_a_bad_setting_does_not_fail_the_health_check(monkeypatch):
    monkeypatch.setenv("VS_MODELS", "nonsense")
    res = TestClient(build()).get("/healthz")
    assert res.status_code == 200 and res.json()["models"] is None
