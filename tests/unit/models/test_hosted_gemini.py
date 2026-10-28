"""Hosted providers by configuration (models/registry.py, models/hosted) and the Gemini free tier as the first one.

Everything runs against `httpx.MockTransport` with fake keys; nothing here touches the network. Shapes follow the Gemini API docs
(generateContent: contents/systemInstruction/generationConfig, usageMetadata, error details QuotaFailure/RetryInfo; header x-goog-api-key).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from vakeel_sahayak.models import factory
from vakeel_sahayak.models.hosted import planner
from vakeel_sahayak.models.hosted.client import _BAD_KEYS, HostedLLMClient
from vakeel_sahayak.models.hosted.errors import (
    HostedPolicyError,
    HostedQuotaExceeded,
    HostedRateLimited,
    HostedRequestTooLarge,
)
from vakeel_sahayak.models.hosted.keys import fingerprint, pool
from vakeel_sahayak.models.hosted.quota import DayFull, QuotaLedger, Slot, Wait, format_report, provider_report, quota_stops
from vakeel_sahayak.models.hosted.protocols import Modes, adapt, error_info, to_gemini_schema
from vakeel_sahayak.models.registry import get_provider
from vakeel_sahayak.models.sarvam.fallback import FallbackLLM
from vakeel_sahayak.models.sarvam.policy import DataClass, authorize, case_text_scope, public_scope, public_source_scope, record_consent, sarvam_scope
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog

REPO = Path(__file__).resolve().parents[3]
KEY = "AIzaFAKE-test-key-0123456789abcdef"
KEY2 = "AIzaFAKE-second-key-9876543210fedcba"
CASE = "case-0042"
MSG = [{"role": "system", "content": "You label court orders."}, {"role": "user", "content": "Say ok."}]
SCHEMA = {"type": "object", "properties": {"labels": {"type": "array", "items": {"enum": ["a", "b"]}}}, "required": ["labels"]}
T0 = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def ok_body(text: str = '{"labels": ["a"]}', version: str = "gemini-3.1-flash-lite-001") -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 5, "thoughtsTokenCount": 0}, "modelVersion": version}


def err_body(code: int, status: str, message: str, *, per_day: bool = False, retry: str | None = None) -> dict:
    details: list = []
    if per_day or code == 429:
        qid = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if per_day else "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"
        details.append({"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaMetric": "generate_content_free_tier_requests", "quotaId": qid}]})
    if retry:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry})
    return {"error": {"code": code, "message": message, "status": status, "details": details}}


class Clock:
    def __init__(self, t: float = T0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class Server:
    """A scripted fake API: responses popped in order (the last one repeats); every request recorded."""

    def __init__(self, *responses: httpx.Response | dict) -> None:
        self.responses = list(responses) or [ok_body()]
        self.requests: list[httpx.Request] = []

    def handler(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(req)
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return r if isinstance(r, httpx.Response) else httpx.Response(200, json=r)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def body(self, i: int = -1) -> dict:
        return json.loads(self.requests[i].content)


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    for var in ("VS_LLM_BACKEND", "VS_LABELER", "VS_TEACHER", "VS_EXTERNAL", "VS_SARVAM", "VS_ALLOW_PAID", "VS_HOSTED_FAILOVER", "GEMINI_API_KEYS",
                "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "VS_GEMINI_RPM", "VS_GEMINI_RPD", "VS_GEMINI_TPM", "VS_PROVIDERS_FILE", "OPENAI_API_KEY", "SARVAM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setenv("VS_GEMINI", "public")
    monkeypatch.setenv("VS_PROVIDERS_FILE", str(tmp_path / "no-override.yaml"))
    _BAD_KEYS.clear()
    factory.reset_clients()
    yield
    _BAD_KEYS.clear()
    factory.reset_clients()


@pytest.fixture()
def ledger(tmp_path):
    return QuotaLedger(tmp_path / "quota.sqlite", clock=Clock())


def client(server: Server, ledger: QuotaLedger, *, model: str | None = None, data=DataClass.PUBLIC, sleeps: list | None = None, **kw) -> HostedLLMClient:
    rec = sleeps if sleeps is not None else []

    def sleep(s: float) -> None:
        rec.append(s)
        ledger.clock.t += s  # time passes while we wait

    return HostedLLMClient("gemini", model, data=data, transport=server.transport, ledger=ledger, cache=_NoCache(), sleep=sleep, jitter=lambda: 0.0, **kw)


class _NoCache:
    def get(self, key):  # noqa: ANN001
        return None

    def put(self, *a):  # noqa: ANN002
        pass


# ----------------------------------------------------------------------------------------------------- registry


def test_gemini_is_configured_public_only_free_and_per_model_limits():
    spec = get_provider("gemini")
    assert spec is not None and spec.protocol == "gemini_native" and spec.free and not spec.paid
    assert spec.data_class_allowed == "public_only" and spec.auth_header == "x-goog-api-key" and spec.key_env == "GEMINI_API_KEY"
    assert spec.limits_for("gemini-3.1-flash-lite") == {"rpm": 15, "rpd": 500, "tpm": 250000}
    assert spec.limits_for("gemma-4-31b-it") == {"rpm": 30, "rpd": 14400, "tpm": 16000}
    assert spec.limits_for("gemini-2.5-flash") == {"rpm": 5, "rpd": 20, "tpm": 250000}
    assert spec.family_of("gemini-3.1-flash-lite") == "gemini" and spec.family_of("gemma-4-26b-it") == "gemma"


def test_env_overrides_limits(monkeypatch):
    monkeypatch.setenv("VS_GEMINI_RPD", "7")
    assert get_provider("gemini").limits_for("gemini-3.1-flash-lite")["rpd"] == 7


# ----------------------------------------------------------------------------------------------------- privacy


@pytest.mark.parametrize("mode", ["public", "pseudonymised", "consented"])
def test_gemini_refuses_client_text_and_raw_in_every_mode_even_with_consent(monkeypatch, mode):
    monkeypatch.setenv("VS_GEMINI", mode)
    log = EventLog()
    record_consent(log, CASE, True, provider="gemini")
    for data in (DataClass.CLIENT_TEXT, DataClass.CLIENT_RAW):
        with sarvam_scope(data, case_id=CASE, event_log=log), pytest.raises(HostedPolicyError, match="public data only"):
            authorize("chat", text="Accused-1 was arrested.", provider="gemini")
    with public_scope():
        authorize("chat", text="public order text", provider="gemini")


def test_gemini_takes_public_source_eval_cases_and_still_runs_the_boundary(monkeypatch):
    monkeypatch.setenv("VS_GEMINI", "pseudonymised")
    with public_source_scope("eval-full"), sarvam_scope(DataClass.CLIENT_TEXT) as _:
        pass  # a nested sarvam_scope replaces the declaration; the agents' pinned class is what matters (below)
    server, led = Server(), QuotaLedger(Path(str(pytest.importorskip("tempfile").mkdtemp())) / "q.sqlite", clock=Clock())
    llm = client(server, led, data=DataClass.CLIENT_TEXT)
    with public_source_scope("eval-full"):
        assert llm.chat([{"role": "user", "content": "The accused Accused-1 was arrested on 20.08.2024."}], max_tokens=50)
        with pytest.raises(PrivacyBoundaryError):
            llm.chat([{"role": "user", "content": "The accused Rajesh Kumar, phone 9876543210, was arrested."}], max_tokens=50)
    assert len(server.requests) == 1


def test_client_text_in_a_product_case_never_leaves(ledger):
    server = Server()
    llm = client(server, ledger, data=DataClass.CLIENT_TEXT)
    log = EventLog()
    record_consent(log, CASE, True, provider="gemini")
    with case_text_scope(CASE, event_log=log), pytest.raises(HostedPolicyError):
        llm.chat(MSG)
    assert server.requests == []


def test_mode_off_refuses(monkeypatch, ledger):
    monkeypatch.setenv("VS_GEMINI", "off")
    with public_scope(), pytest.raises(HostedPolicyError, match="off"):
        client(Server(), ledger).chat(MSG)


# ----------------------------------------------------------------------------------------------------- the wire


def test_request_shape_key_in_header_not_url(ledger):
    server = Server()
    with public_scope():
        out = client(server, ledger).chat(MSG, max_tokens=100, json_schema=SCHEMA)
    assert out == '{"labels": ["a"]}'
    req = server.requests[0]
    assert req.headers["x-goog-api-key"] == KEY and KEY not in str(req.url) and "key=" not in str(req.url)
    assert str(req.url) == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"
    body = server.body()
    assert body["systemInstruction"]["parts"][0]["text"] == "You label court orders."
    assert body["contents"] == [{"role": "user", "parts": [{"text": "Say ok."}]}]
    gen = body["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and gen["thinkingConfig"] == {"thinkingBudget": 0} and gen["maxOutputTokens"] == 100
    assert gen["responseSchema"]["properties"]["labels"]["items"] == {"type": "STRING", "enum": ["a", "b"]}


def test_schema_conversion_inlines_refs_and_marks_nullable():
    schema = {"$defs": {"F": {"type": "object", "properties": {"x": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}}, "required": ["x"]}},
              "type": "object", "properties": {"f": {"$ref": "#/$defs/F"}, "n": {"type": "integer", "title": "N"}}, "additionalProperties": False}
    out = to_gemini_schema(schema)
    assert out["properties"]["f"]["properties"]["x"] == {"type": "STRING", "nullable": True}
    assert out["properties"]["n"] == {"type": "INTEGER"} and "additionalProperties" not in out
    assert to_gemini_schema({"type": "object", "additionalProperties": {"type": "string"}}) is None  # no properties: JSON mode only
    recursive = {"$defs": {"N": {"type": "object", "properties": {"k": {"$ref": "#/$defs/N"}}}}, "$ref": "#/$defs/N"}
    assert to_gemini_schema(recursive) is None


def test_unconvertible_schema_uses_json_mode_only(ledger):
    server = Server()
    with public_scope():
        client(server, ledger).chat(MSG, json_schema={"type": "object", "additionalProperties": {"type": "string"}})
    gen = server.body()["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and "responseSchema" not in gen


def test_key_never_in_logs_errors_repr_or_ledger(ledger, caplog):
    caplog.set_level(logging.DEBUG)
    echo = httpx.Response(401, json=err_body(401, "UNAUTHENTICATED", f"API key not valid: {KEY}"))
    llm = client(Server(echo), ledger)
    with public_scope(), pytest.raises(Exception) as exc:
        llm.chat(MSG)
    assert KEY not in str(exc.value) and KEY not in repr(llm) and KEY not in caplog.text
    assert KEY not in str(pool("GEMINI_API_KEY")) and fingerprint(KEY) in str(pool("GEMINI_API_KEY"))
    assert KEY.encode() not in Path(ledger.path).read_bytes()
    assert fingerprint(KEY) not in KEY and len(fingerprint(KEY)) == 10


# ----------------------------------------------------------------------------------------------------- the ledger


LIM = {"rpm": 2, "rpd": 3, "tpm": 1000}


def test_per_minute_window_and_spacing(ledger):
    a = ledger.try_reserve("gemini", "k-1", "m", LIM, 10)
    assert isinstance(a, Slot)
    b = ledger.try_reserve("gemini", "k-1", "m", LIM, 10)
    assert isinstance(b, Wait) and b.seconds == pytest.approx(30.0)  # spacing 60/rpm
    ledger.clock.t += 30
    assert isinstance(ledger.try_reserve("gemini", "k-1", "m", LIM, 10), Slot)
    ledger.clock.t += 15
    w = ledger.try_reserve("gemini", "k-1", "m", LIM, 10)
    assert isinstance(w, Wait) and w.seconds == pytest.approx(15.0)  # two requests in the last 60 s: the window is full until t=60
    ledger.clock.t += 15
    assert isinstance(ledger.try_reserve("gemini", "k-1", "m", LIM, 10), Slot)  # the request at t=0 has left the window
    assert isinstance(ledger.try_reserve("gemini", "k-2", "m", LIM, 10), Slot)  # another key (project) has its own window


def test_tokens_per_minute_waits(ledger):
    lim = {"rpm": 100, "rpd": 100, "tpm": 1000}
    assert isinstance(ledger.try_reserve("gemini", "k", "m", lim, 800), Slot)
    ledger.clock.t += 1
    w = ledger.try_reserve("gemini", "k", "m", lim, 300)
    assert isinstance(w, Wait) and w.seconds == pytest.approx(59.0)


def test_daily_cap_refuses_and_resets_at_the_utc_day(tmp_path):
    clock = Clock(datetime(2026, 10, 28, 23, 50, tzinfo=timezone.utc).timestamp())
    led = QuotaLedger(tmp_path / "q.sqlite", clock=clock)
    lim = {"rpm": 60, "rpd": 2, "tpm": 0}
    for _ in range(2):
        assert isinstance(led.try_reserve("gemini", "k", "m", lim), Slot)
        clock.t += 5
    full = led.try_reserve("gemini", "k", "m", lim)
    assert isinstance(full, DayFull) and full.used == 2 and full.source == "ledger"
    assert full.reset_ts == datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
    assert led.remaining_today("gemini", "k", "m", lim) == 0
    clock.t = datetime(2026, 10, 29, 0, 0, 30, tzinfo=timezone.utc).timestamp()
    assert isinstance(led.try_reserve("gemini", "k", "m", lim), Slot)
    assert led.remaining_today("gemini", "k", "m", lim) == 1


def test_failed_requests_count_and_unsent_ones_do_not(ledger):
    lim = {"rpm": 60, "rpd": 10, "tpm": 0}
    s1 = ledger.try_reserve("gemini", "k", "m", lim)
    ledger.fail(s1, 500)
    ledger.clock.t += 2
    s2 = ledger.try_reserve("gemini", "k", "m", lim)
    ledger.not_sent(s2)
    assert ledger.remaining_today("gemini", "k", "m", lim) == 9


def test_ledger_stores_no_prompt_text(ledger):
    with public_scope("gold-g1"):
        client(Server(), ledger).chat([{"role": "user", "content": "SECRET-PROMPT-TEXT"}])
    assert b"SECRET-PROMPT-TEXT" not in Path(ledger.path).read_bytes()
    con = sqlite3.connect(ledger.path)
    row = con.execute("SELECT key_fp, model, status, input_tokens, output_tokens, served_model, purpose FROM requests").fetchone()
    assert row == (fingerprint(KEY), "gemini-3.1-flash-lite", "settled", 12, 5, "gemini-3.1-flash-lite-001", "gold-g1")


# ----------------------------------------------------------------------------------------------------- retries and learning


def test_429_honours_retry_after_and_lowers_the_rate(ledger):
    server = Server(httpx.Response(429, headers={"Retry-After": "7"}, json=err_body(429, "RESOURCE_EXHAUSTED", "Resource has been exhausted")), ok_body())
    sleeps: list = []
    with public_scope():
        assert client(server, ledger, sleeps=sleeps).chat(MSG)
    assert len(server.requests) == 2 and sleeps and sleeps[0] >= 7.0  # at least the Retry-After (the halved rate's spacing may be longer)
    assert ledger._effective_rpm(sqlite3.connect(ledger.path), "gemini", fingerprint(KEY), "gemini-3.1-flash-lite", 15, ledger.clock()) == 7


def test_retry_info_detail_is_read():
    msg, code, retry, per_day = error_info(429, {}, err_body(429, "RESOURCE_EXHAUSTED", "quota", retry="39s"))
    assert code == "RESOURCE_EXHAUSTED" and retry == 39.0 and not per_day
    assert error_info(429, {}, err_body(429, "RESOURCE_EXHAUSTED", "quota", per_day=True))[3] is True


def test_per_day_429_blocks_the_key_and_raises_quota_exceeded_then_sends_nothing(ledger):
    server = Server(httpx.Response(429, json=err_body(429, "RESOURCE_EXHAUSTED", "daily quota", per_day=True)))
    llm = client(server, ledger)
    before = quota_stops()
    with public_scope(), pytest.raises(HostedQuotaExceeded) as exc:
        llm.chat(MSG)
    assert exc.value.source == "server" and exc.value.remaining == 0 and quota_stops() == before + 1
    n = len(server.requests)
    with public_scope(), pytest.raises(HostedQuotaExceeded):
        llm.chat(MSG)
    assert len(server.requests) == n == 1


def test_daily_cap_of_the_ledger_refuses_before_sending(monkeypatch, ledger):
    monkeypatch.setenv("VS_GEMINI_RPD", "1")
    server = Server()
    llm = client(server, ledger)
    with public_scope():
        llm.chat(MSG)
        ledger.clock.t += 120
        with pytest.raises(HostedQuotaExceeded, match="0 remain"):
            llm.chat([{"role": "user", "content": "another"}])
    assert len(server.requests) == 1


def test_5xx_bounded_exponential_backoff(ledger):
    unavailable = httpx.Response(503, json=err_body(503, "UNAVAILABLE", "overloaded"))
    sleeps: list = []
    server = Server(unavailable, unavailable, ok_body())
    with public_scope():
        assert client(server, ledger, sleeps=sleeps).chat(MSG)
    assert sleeps[0] == 2.0 and 4.0 in sleeps[1:] and len(server.requests) == 3  # 2 s, then 4 s (plus the spacing waits of the window)
    with public_scope(), pytest.raises(HostedRateLimited):
        client(Server(unavailable), ledger).chat([{"role": "user", "content": "again"}])


def test_per_minute_wait_beyond_max_wait_raises(monkeypatch, ledger):
    monkeypatch.setenv("VS_GEMINI_RPM", "1")
    server = Server()
    llm = client(server, ledger)
    object.__setattr__(llm.spec, "max_wait_s", 10.0)
    with public_scope():
        llm.chat(MSG)
        with pytest.raises(HostedRateLimited, match="max_wait_s"):
            llm.chat([{"role": "user", "content": "second"}])


# ----------------------------------------------------------------------------------------------------- key pool


def test_key_pool_reads_every_form_dedups_and_rotates_on_a_daily_429(monkeypatch, ledger):
    monkeypatch.setenv("GEMINI_API_KEYS", f"{KEY}, {KEY2}")
    monkeypatch.setenv("GEMINI_API_KEY_1", KEY2)
    assert [k.fp for k in pool("GEMINI_API_KEY")] == [fingerprint(KEY), fingerprint(KEY2)]
    day = httpx.Response(429, json=err_body(429, "RESOURCE_EXHAUSTED", "daily", per_day=True))
    server = Server(day, ok_body())
    with public_scope():
        assert client(server, ledger).chat(MSG)
    used = [r.headers["x-goog-api-key"] for r in server.requests]
    assert len(set(used)) == 2  # the second request went out on the other key
    rep = provider_report("gemini", ledger)
    text = format_report(rep)
    assert fingerprint(KEY) in text and fingerprint(KEY2) in text and KEY not in text and KEY2 not in text
    blocked = [v for v in rep["by_key_model"].values() if v["blocked_until"]]
    assert len(blocked) == 1


def test_bad_key_is_dropped_and_the_other_key_answers(monkeypatch, ledger):
    monkeypatch.setenv("GEMINI_API_KEYS", f"{KEY},{KEY2}")
    server = Server(httpx.Response(403, json=err_body(403, "PERMISSION_DENIED", "denied")), ok_body())
    with public_scope():
        assert client(server, ledger).chat(MSG)
    assert len(server.requests) == 2


def test_waits_only_when_every_key_must_wait(monkeypatch, ledger):
    monkeypatch.setenv("GEMINI_API_KEYS", f"{KEY},{KEY2}")
    monkeypatch.setenv("VS_GEMINI_RPM", "1")
    sleeps: list = []
    server = Server()
    llm = client(server, ledger, sleeps=sleeps)
    with public_scope():
        for i in range(3):
            llm.chat([{"role": "user", "content": f"q{i}"}])
    assert len(sleeps) == 1 and sleeps[0] == pytest.approx(60.0, abs=0.5)


# ----------------------------------------------------------------------------------------------------- modes (Gemma)


def test_gemma_style_rejections_fold_the_system_text_and_use_json_in_prompt(ledger):
    no_system = httpx.Response(400, json=err_body(400, "INVALID_ARGUMENT", "Developer instruction is not enabled for models/gemini-x"))
    no_json = httpx.Response(400, json=err_body(400, "INVALID_ARGUMENT", "JSON mode is not enabled for models/gemini-x"))
    server = Server(no_system, no_json, ok_body('```json\n{"labels": ["b"]}\n```'))
    llm = client(server, ledger)
    with public_scope():
        assert "labels" in llm.chat(MSG, json_schema=SCHEMA)
    last = server.body()
    assert "systemInstruction" not in last and "responseMimeType" not in last["generationConfig"]
    assert last["contents"][0]["parts"][0]["text"].startswith("Instructions:\nYou label court orders.")
    assert "JSON schema" in last["contents"][0]["parts"][0]["text"]
    assert llm.last_mode == "fold+prompt"
    assert ledger.modes("gemini", "gemini-3.1-flash-lite") == {"system": "fold", "structured": "prompt", "thinking": "on"}
    with public_scope():  # learned: the next call starts in the working mode
        llm.chat([{"role": "user", "content": "next"}], json_schema=SCHEMA)
    assert len(server.requests) == 4


def test_configured_gemma_starts_folded_without_thinking(ledger):
    server = Server()
    with public_scope():
        client(server, ledger, model="gemma-4-31b-it").chat(MSG, json_schema=SCHEMA, max_tokens=200)
    body = server.body()
    assert "systemInstruction" not in body and "thinkingConfig" not in body["generationConfig"] and "responseMimeType" not in body["generationConfig"]


def test_request_larger_than_the_tpm_is_refused_before_sending(ledger):
    server = Server()
    big = [{"role": "user", "content": "x" * 60000}]  # about 20K tokens by the estimate; Gemma's TPM is 16K
    with public_scope(), pytest.raises(HostedRequestTooLarge, match="16000"):
        client(server, ledger, model="gemma-4-31b-it").chat(big)
    assert server.requests == []
    with public_scope():
        client(server, ledger, model="gemma-4-31b-it").chat([{"role": "user", "content": "x" * 42000}], max_tokens=4096)
    assert server.body()["generationConfig"]["maxOutputTokens"] < 4096  # the answer limit was lowered to fit


def test_adapt_without_a_known_feature_gives_up():
    assert adapt(Modes(), "some other problem", True) is None
    assert adapt(Modes(), "Unknown name thinkingConfig", True).thinking == "off"


def test_failover_is_opt_in_and_used_when_the_first_model_is_spent(monkeypatch, ledger):
    monkeypatch.setenv("VS_GEMINI_RPD", "1")
    server = Server()
    llm = client(server, ledger)
    with public_scope():
        llm.chat([{"role": "user", "content": "one"}])
        with pytest.raises(HostedQuotaExceeded):
            llm.chat([{"role": "user", "content": "two"}])
        monkeypatch.setenv("VS_HOSTED_FAILOVER", "1")
        llm.chat([{"role": "user", "content": "three"}])
    assert str(server.requests[-1].url).endswith("/gemini-3.5-flash-lite:generateContent")
    assert llm.models_used == {"gemini-3.1-flash-lite": 1, "gemini-3.5-flash-lite": 1}
    assert ledger.run_models("gemini") == {"gemini-3.1-flash-lite": 1, "gemini-3.5-flash-lite": 1}


# ----------------------------------------------------------------------------------------------------- factory, labeler, teacher


@pytest.fixture()
def no_network(monkeypatch):
    def refuse(*_a, **_k):  # noqa: ANN002, ANN003
        raise AssertionError("the network was called")

    monkeypatch.setattr(HostedLLMClient, "_send", refuse)


def _offline_fallback(monkeypatch):
    from vakeel_sahayak.models.offline_llm import OfflineLLM

    monkeypatch.setattr(factory, "_resolve", lambda role, cfg, mode: OfflineLLM(role=role, where=str(cfg.get("where") or "ada")))


def test_factory_wraps_gemini_and_falls_back_locally_for_product_cases(monkeypatch, no_network):
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    _offline_fallback(monkeypatch)
    llm = factory.get_llm("agents_14b")
    assert isinstance(llm, FallbackLLM) and isinstance(llm.primary, HostedLLMClient) and llm.primary.data is DataClass.CLIENT_TEXT
    with case_text_scope(CASE):
        llm.chat([{"role": "user", "content": "Accused-1 was arrested."}])
    assert llm.fallbacks and llm.fallbacks[-1]["error"] == "HostedPolicyError"


def test_factory_falls_back_when_the_daily_quota_is_spent(monkeypatch, no_network):
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    monkeypatch.setenv("VS_GEMINI", "pseudonymised")
    monkeypatch.setenv("VS_GEMINI_RPD", "0")
    _offline_fallback(monkeypatch)
    llm = factory.get_llm("agents_14b")
    with public_source_scope("eval-full"):
        llm.chat([{"role": "user", "content": "Accused-1 was arrested."}])
    assert llm.fallbacks[-1]["error"] == "HostedQuotaExceeded"


def test_factory_uses_local_client_without_key_or_mode(monkeypatch):
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY")
    assert not isinstance(factory.get_llm("agents_14b"), FallbackLLM)
    factory.reset_clients()
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setenv("VS_GEMINI", "off")
    assert not isinstance(factory.get_llm("agents_14b"), FallbackLLM)
    monkeypatch.setenv("VS_MODELS", "offline")
    factory.reset_clients()
    assert factory.get_llm("agents_14b").is_offline


def test_default_offline_path_is_untouched(monkeypatch):
    monkeypatch.setenv("VS_MODELS", "offline")
    assert factory.llm_backend() is None and factory.get_llm("agents_14b").is_offline


def test_labeler_on_gemini_has_family_gemini_and_public_data(monkeypatch):
    from vakeel_sahayak.models.labeler import EvalLabeler

    monkeypatch.setenv("VS_LABELER", "gemini")
    lab = EvalLabeler()
    assert lab.backend() == "gemini" and lab.family == "gemini" and lab.model_name() == "gemini-3.1-flash-lite"
    c = EvalLabeler(backend="gemini").client()
    assert isinstance(c, HostedLLMClient) and c.data is DataClass.PUBLIC and c.role == "eval_labeler"


def test_labeler_family_rule_against_the_judged_system(monkeypatch):
    monkeypatch.setenv("VS_LABELER", "gemini")
    monkeypatch.setenv("VS_TEACHER", "offline")
    lab, _ = factory.assert_independent_families(teacher="qwen")
    assert lab == "gemini"  # the judged system is offline or local here: independent
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    with pytest.raises(ValueError, match="self-labelled"):
        factory.assert_independent_families(teacher="qwen")
    assert factory.llm_family("gemini", "gemma-4-31b-it") == "gemma"


def test_teacher_on_gemini_is_public(monkeypatch):
    from vakeel_sahayak.models.teacher import TeacherClient

    t = TeacherClient(backend="gemini")
    assert t.family == "gemini" and t.where == "api" and t.model_id == "gemini-3.1-flash-lite"
    assert t.client.data is DataClass.PUBLIC


def test_run_stamp_records_provider_model_quota_and_modes(monkeypatch):
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    stamp = factory.describe_run_models()
    role = stamp["roles"]["agents_14b"]
    assert role["provider"] == "gemini" and role["model"] == "gemini-3.1-flash-lite" and role["family"] == "gemini"
    block = stamp["hosted"]["gemini"]
    assert block["free"] and block["data_class_allowed"] == "public_only" and block["limits"]["gemini-3.1-flash-lite"]["rpd"] == 500
    assert block["quota_today"]["keys"] == [fingerprint(KEY)] and "run_models" in block
    assert KEY not in json.dumps(stamp)


def test_b0l_uses_the_configured_larger_model(monkeypatch):
    from vakeel_sahayak.eval.baselines.b0_single_pass import b0l_model_id

    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    assert b0l_model_id() == "gemini-3-flash"


def test_paid_lock_does_not_touch_gemini():
    from vakeel_sahayak.models.paid_lock import paid_unlocked

    assert paid_unlocked("gemini")


# ----------------------------------------------------------------------------------------------------- a provider added by configuration only


ACME = """
providers:
  acme:
    protocol: openai_compat
    base_url: https://api.acme.test/v1
    auth_header: Authorization
    auth_scheme: Bearer
    key_env: ACME_API_KEY
    data_class_allowed: pseudonymised
    paid: true
    structured: json_mode
    default_model: acme-small
    models: {acme-small: {rpm: 60, rpd: 1000, tpm: 100000, family: acme}}
"""


def test_a_made_up_provider_runs_from_yaml_alone(monkeypatch, tmp_path):
    path = tmp_path / "providers.local.yaml"
    path.write_text(ACME, encoding="utf-8")
    monkeypatch.setenv("VS_PROVIDERS_FILE", str(path))
    monkeypatch.setenv("ACME_API_KEY", "acme-FAKE-KEY-123")
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.setenv("VS_LLM_BACKEND", "acme")
    assert factory.llm_backend() == "acme" and factory.llm_family("acme", "acme-small") == "acme"
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"labels": []}'}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}, "model": "acme-small-v2"})

    led = QuotaLedger(tmp_path / "q.sqlite", clock=Clock())
    llm = HostedLLMClient("acme", data=DataClass.PUBLIC, transport=httpx.MockTransport(handler), ledger=led, cache=_NoCache(), sleep=lambda s: None)
    from vakeel_sahayak.models.paid_lock import PaidProviderLocked

    with public_scope(), pytest.raises(PaidProviderLocked, match="VS_ALLOW_PAID=acme"):  # paid: true -> behind the lock, by config
        llm.chat(MSG, json_schema=SCHEMA)
    monkeypatch.setenv("VS_ALLOW_PAID", "acme")
    with public_scope():
        assert llm.chat(MSG, json_schema=SCHEMA) == '{"labels": []}'
    req = seen[0]
    assert str(req.url) == "https://api.acme.test/v1/chat/completions" and req.headers["authorization"] == "Bearer acme-FAKE-KEY-123"
    body = json.loads(req.content)
    assert body["model"] == "acme-small" and body["response_format"] == {"type": "json_object"} and body["max_tokens"] > 0
    assert llm.version() == "acme-small-v2"
    log = EventLog()
    record_consent(log, CASE, True, provider="acme")
    with sarvam_scope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log), pytest.raises(HostedPolicyError, match="pseudonymised text at most"):
        authorize("chat", text="raw", provider="acme")


# ----------------------------------------------------------------------------------------------------- planner and scripts


def test_planner_bounds_and_choice():
    spec = get_provider("gemini")
    p = planner.plan_model(spec, "gemma-4-31b-it", 1000, 20000)
    assert not p["feasible"]  # one request is larger than Gemma's 16K TPM
    p = planner.plan_model(spec, "gemma-4-31b-it", 4000, 8000)
    assert p["tokens_per_day_cap"] == 16000 * 1440 and p["binding"] == "tpd" and p["days_by_tpd"] == 2 and p["days_by_rpd"] == 1
    p = planner.plan_model(spec, "gemini-3.1-flash-lite", 1500, 2500)
    assert p["days_by_rpd"] == 3 and p["binding"] == "rpd" and p["days"] == 3
    assert planner.plan_model(spec, "gemini-3.1-flash-lite", 1500, 2500, keys=3)["days"] == 1
    assert planner.plan_model(spec, "gemini-3.1-flash-lite", 600, 2500, remaining_today=0)["days"] == 3
    assert planner.pick_model(spec, 1500, 2500)["model"].startswith("gemma")
    assert planner.pick_model(spec, 100, 30000)["model"] in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite")
    sched = planner.failover_schedule(spec, ["gemini-3.1-flash-lite", "gemini-2.5-flash"], 530, 2000)
    assert sched[0] == {"gemini-3.1-flash-lite": 500, "gemini-2.5-flash": 20} and sched[1] == {"gemini-3.1-flash-lite": 10}


def test_paired_warnings():
    arms = [{"id": "full", "backend": "gemini", "model": "gemini-3.1-flash-lite"}, {"id": "A2", "backend": "gemini", "model": "gemini-3.1-flash-lite"}]
    assert planner.paired_warnings(arms) == []
    arms.append({"id": "A8", "backend": "gemini", "model": "gemma-4-31b-it"})
    assert any("mixes models" in w for w in planner.paired_warnings(arms))
    assert any("fail over" in w for w in planner.paired_warnings([{**arms[0], "failover": True}]))


def test_quota_plan_script_runs_offline():
    env = {"PATH": "/usr/bin:/bin", "VS_DATA_DIR": str(Path(pytest.importorskip("tempfile").mkdtemp()))}
    out = subprocess.run([sys.executable, str(REPO / "scripts/gemini_quota_plan.py"), "--n", "250", "--calls-per-item", "6", "--tokens-per-call", "2500"],
                         cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert "1500 requests" in out.stdout and "soonest:" in out.stdout and "AI Studio" in out.stdout


def test_usage_cli_prints_fingerprints_only(capsys):
    from vakeel_sahayak.models.hosted import quota

    assert quota.main(["--provider", "gemini"]) == 0
    text = capsys.readouterr().out
    assert fingerprint(KEY) in text and KEY not in text and "remaining" in text


# ----------------------------------------------------------------------------------------------------- probe


def test_probe_lists_models_with_paging_and_flags_missing_ids():
    from vakeel_sahayak.models.hosted import probe

    pages = [
        {"models": [{"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/text-embedding-9", "supportedGenerationMethods": ["embedContent"]}], "nextPageToken": "p2"},
        {"models": [{"name": "models/gemma-4-31b-it", "supportedGenerationMethods": ["generateContent", "countTokens"]}]},
    ]
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json=pages[len(seen) - 1])

    rep = probe.list_models(get_provider("gemini"), transport=httpx.MockTransport(handler))
    assert rep["keys"][fingerprint(KEY)]["models"] == ["gemini-3.1-flash-lite", "gemma-4-31b-it"]
    assert "gemini-2.5-flash" in rep["configured_missing"] and "gemma-4-31b-it" not in rep["configured_missing"]
    assert all(KEY not in str(r.url) and r.headers["x-goog-api-key"] == KEY for r in seen)
    assert seen[1].url.params["pageToken"] == "p2"


def test_probe_smoke_detects_the_working_mode(ledger):
    from vakeel_sahayak.models.hosted import probe

    no_system = httpx.Response(400, json=err_body(400, "INVALID_ARGUMENT", "Developer instruction is not enabled"))
    server = Server(no_system, ok_body('{"ok": true, "word": "bail"}', "gemma-4-31b-it"))
    def sleep(s: float) -> None:
        ledger.clock.t += s

    rep = probe.smoke(get_provider("gemini"), "gemini-3.1-flash-lite", transport=server.transport, ledger=ledger, cache=_NoCache(), sleep=sleep, jitter=lambda: 0.0)
    assert rep["json_ok"] and rep["mode"].startswith("fold+")
    assert ledger.modes("gemini", "gemini-3.1-flash-lite")["system"] == "fold"


def test_model_env_pins_one_model_for_the_agents(monkeypatch):
    monkeypatch.setenv("VS_GEMINI_MODEL", "gemma-4-31b-it")
    spec = get_provider("gemini")
    assert spec.model_for("agents") == "gemma-4-31b-it" and spec.model_for("labeler") == "gemini-3.1-flash-lite"
    monkeypatch.setenv("VS_LLM_BACKEND", "gemini")
    assert factory.describe_run_models()["roles"]["agents_14b"]["model"] == "gemma-4-31b-it"


def test_sweep_plan_has_a_gemini_block_with_one_model_and_locked_paid_phases():
    import yaml

    cfg = yaml.safe_load((REPO / "configs/eval/sweep_dev.yaml").read_text(encoding="utf-8"))
    assert cfg["backends"]["gemini"]["env"]["VS_LLM_BACKEND"] == "gemini"
    assert all(a["status"] in ("locked", "dropped", "done") for a in cfg["arms"] if a["backend"] in ("openai", "sarvam") and a["phase"] in (2, 3))
    paired = [{"id": a["id"], "backend": "gemini", "model": a.get("model") or cfg["backends"]["gemini"]["model"]} for a in cfg["arms"]
              if a["backend"] == "gemini" and a["id"] != "b0l"]
    assert planner.paired_warnings(paired) == []
