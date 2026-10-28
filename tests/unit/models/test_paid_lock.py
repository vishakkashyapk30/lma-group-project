"""The paid-provider lock (models/paid_lock.py, owner decision 2026-10-28): OpenAI and Sarvam refuse every call unless VS_ALLOW_PAID names them.

A locked call must not touch the network (the mock transport records nothing) and must not write a ledger row; the factory answers
from the local client; the labeler, teacher, driver and sweep script refuse at once with the message that names the unlock.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from vakeel_sahayak.models import factory, paid_lock
from vakeel_sahayak.models.openai import OpenAILocked, OpenAIPolicyError
from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
from vakeel_sahayak.models.openai.api import OpenAIApi
from vakeel_sahayak.models.openai.http import OpenAIHttp
from vakeel_sahayak.models.openai.ledger import Ledger
from vakeel_sahayak.models.sarvam import SarvamLocked, SarvamPolicyError, authorize, public_scope
from vakeel_sahayak.models.sarvam.api import SarvamApi
from vakeel_sahayak.models.sarvam.http import SarvamHttp
from vakeel_sahayak.models.sarvam.policy import DataClass

REPO = Path(__file__).resolve().parents[3]
MSG = [{"role": "user", "content": "Say ok."}]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("VS_ALLOW_PAID", "VS_LLM_BACKEND", "VS_LABELER", "VS_TEACHER", "VS_SARVAM"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.setenv("VS_EXTERNAL", "public")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET-0123456789")
    monkeypatch.setenv("SARVAM_API_KEY", "sv-test-SECRET-0123456789")
    factory.reset_clients()
    yield
    factory.reset_clients()


def _recording():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    return seen, httpx.MockTransport(handler)


def test_default_is_locked_and_the_message_names_the_unlock():
    assert not paid_lock.paid_unlocked("openai") and not paid_lock.paid_unlocked("sarvam")
    msg = paid_lock.lock_message("openai")
    assert "VS_ALLOW_PAID=openai" in msg and "2026-10-28" in msg and "owner" in msg


def test_unlock_variable_names_providers_one_by_one(monkeypatch):
    monkeypatch.setenv("VS_ALLOW_PAID", "openai")
    assert paid_lock.paid_unlocked("openai") and not paid_lock.paid_unlocked("sarvam")
    monkeypatch.setenv("VS_ALLOW_PAID", " OpenAI , sarvam ")
    assert paid_lock.paid_unlocked("openai") and paid_lock.paid_unlocked("sarvam")


def test_free_and_local_backends_are_never_locked():
    for name in ("offline", "local", "gemini", "vllm"):
        assert paid_lock.paid_unlocked(name)


def test_lock_errors_are_policy_errors_so_existing_fallbacks_catch_them():
    assert issubclass(OpenAILocked, OpenAIPolicyError) and issubclass(OpenAILocked, paid_lock.PaidProviderLocked)
    assert issubclass(SarvamLocked, SarvamPolicyError) and issubclass(SarvamLocked, paid_lock.PaidProviderLocked)


def test_authorize_refuses_locked_providers_before_anything_else():
    with public_scope(), pytest.raises(OpenAILocked, match="VS_ALLOW_PAID"):
        authorize("chat", provider="openai")
    with public_scope(), pytest.raises(SarvamLocked, match="VS_ALLOW_PAID"):
        authorize("chat", provider="sarvam")


def test_locked_openai_sends_nothing_and_writes_no_ledger_row(tmp_path):
    seen, transport = _recording()
    ledger = Ledger(tmp_path / "l.sqlite")
    api = OpenAIApi(OpenAIHttp(transport=transport), ledger=ledger)
    with pytest.raises(OpenAILocked):
        api.chat(MSG, temperature=0.5)
    client = OpenAILLMClient(api=api, data=DataClass.PUBLIC)
    with public_scope(), pytest.raises(OpenAILocked):
        client.chat(MSG)
    with pytest.raises(OpenAILocked):
        OpenAIHttp(transport=transport).request("POST", "/v1/chat/completions", json={})
    assert seen == []
    rep = ledger.report()
    assert rep["calls"] == rep["in_flight"] == rep["released"] == rep["cache_hits"] == 0


def test_locked_sarvam_sends_nothing(tmp_path):
    seen, transport = _recording()
    http = SarvamHttp(transport=transport)
    with pytest.raises(SarvamLocked):
        http.request("POST", "/v1/chat/completions", json={})
    with pytest.raises(SarvamLocked):
        SarvamApi(http).chat(MSG)
    with pytest.raises(SarvamLocked):
        SarvamApi(http).translate("नमस्ते", "hi", "en")
    assert seen == []


def test_unlocked_openai_reaches_the_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("VS_ALLOW_PAID", "openai")
    seen, transport = _recording()
    api = OpenAIApi(OpenAIHttp(transport=transport), ledger=Ledger(tmp_path / "l.sqlite"))
    assert api.chat(MSG, temperature=0.5).text == "ok"
    assert len(seen) == 1


def test_factory_treats_a_locked_provider_like_off(monkeypatch):
    for backend in ("openai", "sarvam"):
        monkeypatch.setenv("VS_LLM_BACKEND", backend)
        factory.reset_clients()
        client = factory.get_llm("agents_14b")
        assert type(client).__name__ != "FallbackLLM"
        assert not isinstance(client, OpenAILLMClient)


def test_explicit_model_on_a_locked_provider_is_refused(monkeypatch):
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    with pytest.raises(OpenAILocked):
        factory.get_llm_model("agents_14b", "gpt-6-luna")


def test_labeler_and_teacher_refuse_at_once():
    from vakeel_sahayak.models.base import LabelerUnavailable
    from vakeel_sahayak.models.labeler import EvalLabeler
    from vakeel_sahayak.models.teacher import TeacherClient

    for backend in ("openai", "sarvam"):
        with pytest.raises(LabelerUnavailable, match="VS_ALLOW_PAID"):
            EvalLabeler(backend=backend).client()
        with pytest.raises(paid_lock.PaidProviderLocked):
            _ = TeacherClient(backend=backend).client


def test_driver_refuses_to_start_on_a_locked_backend(monkeypatch, capsys):
    from vakeel_sahayak.eval.runners import driver

    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    assert driver.main(["run", "--system", "full"]) == 3
    assert "VS_ALLOW_PAID" in capsys.readouterr().err
    assert driver.paid_backend_locked() is not None
    monkeypatch.setenv("VS_LLM_BACKEND", "offline")
    assert driver.paid_backend_locked() is None


def test_check_cli_exit_code(monkeypatch, capsys):
    assert paid_lock.main(["check", "openai"]) == 3
    assert "VS_ALLOW_PAID" in capsys.readouterr().err
    assert paid_lock.main(["check", "gemini"]) == 0


def test_sweep_script_skips_locked_arms_and_refuses_locked_backends(monkeypatch):
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sweep_dev
    finally:
        sys.path.pop(0)
    cfg = {"backends": {"openai": {"env": {"VS_LLM_BACKEND": "openai"}}, "offline": {"env": {"VS_LLM_BACKEND": "offline"}}},
           "arms": [{"id": "A2", "phase": 2, "backend": "openai", "n": 5, "status": "planned"},
                    {"id": "A8", "phase": 2, "backend": "openai", "n": 5, "status": "locked"},
                    {"id": "S4", "phase": 2, "backend": "offline", "n": 5, "status": "planned"}]}
    import argparse

    jobs = sweep_dev.jobs_for(cfg, argparse.Namespace(phase=2, backend=None, arms=None, n=None, include_done=False))
    assert [j["system"] for j in jobs] == ["A2", "S4"]
    msgs = sweep_dev.locked_backends(cfg, jobs)
    assert len(msgs) == 1 and "VS_ALLOW_PAID=openai" in msgs[0]
    monkeypatch.setenv("VS_ALLOW_PAID", "openai")
    assert sweep_dev.locked_backends(cfg, jobs) == []


def test_block_scripts_fail_fast_while_locked(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    for script in ("sweep_openai_block.sh", "sweep_sarvam_block.sh"):
        text = (REPO / "scripts" / script).read_text(encoding="utf-8")
        assert "vakeel_sahayak.models.paid_lock check" in text
    out = subprocess.run([sys.executable, "-m", "vakeel_sahayak.models.paid_lock", "check", "sarvam"], cwd=REPO, env={**env, "PYTHONPATH": str(REPO / "src")},
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 3 and "VS_ALLOW_PAID=sarvam" in out.stderr
