"""`VS_MODELS=auto` NLI: the real checker when it can run, else the offline checker with the reason recorded (never silently)."""

from __future__ import annotations

import logging

from vakeel_sahayak.models import factory, nli
from vakeel_sahayak.models.base import ModelUnavailable, NliClient
from vakeel_sahayak.models.nli import AutoNliClient, DebertaNliClient, OfflineNliClient, nli_status


class _Broken(NliClient):
    name = "broken-real"
    default_threshold = 0.7

    def entails(self, premise: str, hypothesis: str) -> float:
        raise ModelUnavailable("the checkpoint could not be loaded", "models")


class _Fine(NliClient):
    name = "fine-real"
    default_threshold = 0.7

    def entails(self, premise: str, hypothesis: str) -> float:
        return 0.9


def test_missing_dependencies_fall_back_and_say_so(monkeypatch, caplog):
    monkeypatch.setattr(DebertaNliClient, "available", staticmethod(lambda: False))
    with caplog.at_level(logging.WARNING):
        client = AutoNliClient()
    assert client.is_offline and "not installed" in client.fallback_reason
    assert nli_status()["backend"] == OfflineNliClient.name and nli_status()["fallback_reason"] == client.fallback_reason
    assert any("offline stand-in" in r.message for r in caplog.records)
    assert 0.0 <= client.entails("Charge sheet filed 02.11.2024.", "The charge sheet was filed on 02.11.2024.") <= 1.0


def test_a_real_client_that_fails_to_load_falls_back_once_and_records_the_reason():
    client = AutoNliClient(real=_Broken())
    assert not client.is_offline and client.fallback_reason is None
    score = client.entails("Charge sheet filed 02.11.2024.", "The charge sheet was filed on 02.11.2024.")
    assert client.is_offline and "checkpoint could not be loaded" in client.fallback_reason
    assert nli_status()["fallback_reason"] == client.fallback_reason and 0.0 <= score <= 1.0
    assert client.judge("Charge sheet filed 02.11.2024.", "The charge sheet was filed on 02.11.2024.").score == score


def test_a_working_real_client_is_used_without_a_fallback():
    client = AutoNliClient(real=_Fine())
    assert client.entails("p", "h") == 0.9 and client.fallback_reason is None and client.default_threshold == 0.7


def test_the_factory_returns_the_auto_client_in_auto_mode(monkeypatch):
    monkeypatch.delenv("VS_NLI", raising=False)
    monkeypatch.setenv("VS_MODELS", "auto")
    factory._nli_cached.cache_clear()
    try:
        assert isinstance(factory.get_nli(), AutoNliClient)
        monkeypatch.setenv("VS_NLI", "offline")
        assert isinstance(factory.get_nli(), OfflineNliClient)
    finally:
        factory._nli_cached.cache_clear()


def test_the_downloaded_checkpoint_is_preferred_to_the_hub_id(tmp_path, monkeypatch):
    (tmp_path / "Org--Model").mkdir()
    (tmp_path / "Org--Model" / "config.json").write_text("{}")
    monkeypatch.setenv("VS_MODELS_DIR", str(tmp_path))
    assert nli.local_checkpoint("Org/Model") == str(tmp_path / "Org--Model") and nli.local_checkpoint("Org/Other") is None
