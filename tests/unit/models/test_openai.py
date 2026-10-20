"""OpenAI integration (models/openai): transport, hard spending cap and ledger, response cache, privacy gate, structured output,
adapter, fallback, factory wiring, families and the run stamp.

Everything runs against `httpx.MockTransport`; nothing here touches the network and the real key (if any) is never used.
The fixtures follow the shapes in the OpenAI docs (developers.openai.com, checked 2026-10-24): `Authorization: Bearer`, chat
`/v1/chat/completions`, `usage.prompt_tokens_details.cached_tokens`, `response_format` json_schema / json_object.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time

import httpx
import pytest

from vakeel_sahayak.models import factory
from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, model_family
from vakeel_sahayak.models.openai import (
    HARD_MAX_USD,
    BudgetExceeded,
    Ledger,
    OpenAIAuthError,
    OpenAIError,
    OpenAIPolicyError,
    OpenAIQuotaError,
    OpenAIRateLimited,
    OpenAIUnavailable,
    ResponseCache,
    effective_cap_usd,
)
from vakeel_sahayak.models.openai import http as http_mod
from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
from vakeel_sahayak.models.openai.api import AsyncOpenAIApi, OpenAIApi, strictify
from vakeel_sahayak.models.openai.config import openai_config, price_of
from vakeel_sahayak.models.openai.http import OpenAIHttp
from vakeel_sahayak.models.openai.ledger import cost_micro, format_report, input_token_bound, worst_case_micro
from vakeel_sahayak.models.sarvam import DataClass, SarvamMode, SarvamScope, authorize, public_scope, record_consent, sarvam_mode, sarvam_scope
from vakeel_sahayak.models.sarvam.fallback import FallbackLLM
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog

KEY = "sk-test-SECRET-0123456789"  # obviously fake
CASE = "case-0042"
CLEAN = "The accused Accused-1 was arrested on 20.08.2024."
RAW_NAME = "The accused Rajesh Kumar was arrested on 20.08.2024."
MSG = [{"role": "user", "content": "Say ok."}]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No external-provider state leaks between tests; the real key (if any) is never used here."""
    for var in (
        "VS_SARVAM", "VS_EXTERNAL", "VS_MODELS", "VS_LABELER", "VS_TEACHER", "VS_LLM_BACKEND", "SARVAM_API_KEY", "OPENAI_API_KEY",
        "VS_OPENAI_CAP_USD", "VS_OPENAI_RUN_CAP_USD", "VS_OPENAI_RUN_ID", "MISTRAL_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    factory.reset_clients()
    yield
    factory.reset_clients()


@pytest.fixture()
def calls():
    """Recorded requests of the mocked server."""
    return []


def reply(text="ok", pt=11, ct=3, cached=0, finish="stop", model="gpt-6-luna-2026-09-01"):
    return {
        "id": "chatcmpl-x", "object": "chat.completion", "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
        "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct, "prompt_tokens_details": {"cached_tokens": cached}},
    }  # fmt: skip


def server(calls, answer=None):
    """A mock OpenAI: records every request, answers with `answer` (a dict, an httpx.Response or callable(request))."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        out = answer(request) if callable(answer) else (answer if answer is not None else reply())
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

    return handler


def make_api(tmp_path, calls, answer=None, cap_usd=1.0, **kw) -> OpenAIApi:
    http = OpenAIHttp(KEY, transport=httpx.MockTransport(server(calls, answer)), sleep=lambda s: None, **kw)
    return OpenAIApi(http, ledger=Ledger(tmp_path / "ledger.sqlite", cap_usd=cap_usd, run_id="run-a"), cache=ResponseCache(tmp_path / "cache.sqlite"))


def bodies(calls):
    return [json.loads(r.content) for r in calls]


# ------------------------------------------------------------------------------------------------ transport and mapping


def test_request_mapping_auth_header_and_endpoint(tmp_path, calls):
    api = make_api(tmp_path, calls)
    res = api.chat(MSG, max_tokens=50, temperature=0.0, purpose="unit")
    req = calls[0]
    assert req.method == "POST" and str(req.url) == "https://api.openai.com/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = bodies(calls)[0]
    assert body["model"] == "gpt-6-luna" and body["messages"] == MSG and body["max_completion_tokens"] == 50
    assert body["temperature"] == 0.0 and body["reasoning_effort"] == "none" and "max_tokens" not in body and "response_format" not in body
    assert (res.text, res.prompt_tokens, res.completion_tokens, res.model) == ("ok", 11, 3, "gpt-6-luna-2026-09-01")


def test_max_tokens_is_capped_by_config(tmp_path, calls):
    make_api(tmp_path, calls).chat(MSG, max_tokens=100000)
    assert bodies(calls)[0]["max_completion_tokens"] == 4096


def test_structured_output_strict_json_schema_when_schema_allows(tmp_path, calls):
    schema = {"type": "object", "title": "T", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}}, "required": ["a", "b"]}
    make_api(tmp_path, calls).chat(MSG, json_schema=schema)
    fmt = bodies(calls)[0]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True and fmt["json_schema"]["name"] == "output"
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False and "title" not in fmt["json_schema"]["schema"]


def test_structured_output_non_strict_when_optional_fields(tmp_path, calls):
    schema = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer", "default": 0}}, "required": ["a"]}
    assert strictify(schema) is None
    make_api(tmp_path, calls).chat(MSG, json_schema=schema)
    js = bodies(calls)[0]["response_format"]["json_schema"]
    assert js["strict"] is False and js["schema"] == schema


def test_strictify_handles_nested_defs_and_arrays():
    schema = {
        "type": "object", "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/I"}}}, "required": ["items"],
        "$defs": {"I": {"type": "object", "properties": {"x": {"type": "string", "default": ""}}, "required": ["x"]}},
    }  # fmt: skip
    out = strictify(schema)
    assert out is not None and out["$defs"]["I"]["additionalProperties"] is False and "default" not in out["$defs"]["I"]["properties"]["x"]
    assert "additionalProperties" not in schema["$defs"]["I"]  # the input is untouched


def test_response_format_rejection_falls_back_to_non_strict_then_json_object(tmp_path, calls):
    def answer(request):
        fmt = json.loads(request.content).get("response_format", {})
        if fmt.get("type") == "json_schema":
            return httpx.Response(400, json={"error": {"message": "Invalid schema for response_format 'output'", "param": "response_format", "code": "invalid_json_schema"}})
        return reply('{"a": "x"}')

    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    api = make_api(tmp_path, calls, answer)
    res = api.chat(MSG, json_schema=schema)
    kinds = [b["response_format"]["type"] for b in bodies(calls)]
    assert kinds == ["json_schema", "json_schema", "json_object"] and res.text == '{"a": "x"}'
    assert "json" in " ".join(m["content"].lower() for m in bodies(calls)[-1]["messages"])  # json_object needs the word JSON
    rep = api.ledger.report()
    assert rep["calls"] == 1 and rep["in_flight"] == 0 and rep["released"] == 0  # rejected requests are not billed, one reservation settled


def test_rejected_temperature_is_dropped_and_remembered(tmp_path, calls):
    def answer(request):
        if "temperature" in json.loads(request.content):
            return httpx.Response(400, json={"error": {"message": "Unsupported value: 'temperature' does not support 0.0 with this model.", "param": "temperature", "code": "unsupported_value"}})
        return reply()

    api = make_api(tmp_path, calls, answer)
    api.chat(MSG, temperature=0.0)
    api.chat([{"role": "user", "content": "another"}], temperature=0.0)
    sent = bodies(calls)
    assert "temperature" in sent[0] and "temperature" not in sent[1] and "temperature" not in sent[2]


def test_usage_cached_tokens_and_cost_recorded(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(pt=1000, ct=200, cached=400))
    res = api.chat(MSG, purpose="p1", case_id=CASE)
    assert (res.prompt_tokens, res.cached_tokens, res.completion_tokens) == (1000, 400, 200)
    assert res.cost_micro == 164  # 600 x 0.10 + 400 x 0.01 + 200 x 0.50 micro-USD
    rep = api.ledger.report()
    assert rep["spent_usd"] == pytest.approx(0.000164) and rep["cached_tokens"] == 400


def test_empty_answer_at_length_limit_is_an_error_but_still_billed(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(text="", pt=10, ct=50, finish="length"))
    with pytest.raises(OpenAIError, match="token limit"):
        api.chat(MSG, max_tokens=50)
    assert api.ledger.report()["spent_usd"] > 0


def test_refusal_is_an_error(tmp_path, calls):
    data = reply(text="")
    data["choices"][0]["message"]["refusal"] = "no"
    with pytest.raises(OpenAIError, match="refused"):
        make_api(tmp_path, calls, data).chat(MSG)


def test_retries_only_429_and_5xx_with_backoff(tmp_path, calls):
    seq = iter([httpx.Response(429, json={"error": {"code": "rate_limit_exceeded", "message": "slow"}}), httpx.Response(503, json={}), None])

    def answer(_):
        r = next(seq)
        return r if r is not None else reply()

    api = make_api(tmp_path, calls, answer)
    delays: list[float] = []
    api.http._sleep = delays.append
    assert api.chat(MSG).text == "ok" and len(calls) == 3 and delays == [1.0, 2.0]


@pytest.mark.parametrize("status,exc", [(400, OpenAIError), (401, OpenAIAuthError), (404, OpenAIError), (422, OpenAIError)])
def test_no_retry_on_client_errors(tmp_path, calls, status, exc):
    api = make_api(tmp_path, calls, httpx.Response(status, json={"error": {"message": "nope"}}))
    with pytest.raises(exc):
        api.chat(MSG)
    assert len(calls) == 1
    assert api.ledger.report()["spent_usd"] == 0  # an error response is not billed: the reservation was released


def test_quota_error_not_retried_and_persistent_429_is_rate_limited(tmp_path, calls):
    api = make_api(tmp_path, calls, httpx.Response(429, json={"error": {"code": "insufficient_quota", "message": "credit"}}))
    with pytest.raises(OpenAIQuotaError):
        api.chat(MSG)
    assert len(calls) == 1
    calls.clear()
    (tmp_path / "b").mkdir()
    api2 = make_api(tmp_path / "b", calls, httpx.Response(429, json={"error": {"code": "rate_limit_exceeded", "message": "slow"}}), max_retries=2)
    with pytest.raises(OpenAIRateLimited):
        api2.chat(MSG)
    assert len(calls) == 3


def test_no_key_raises_unavailable_without_a_request(tmp_path, calls):
    http = OpenAIHttp(None, transport=httpx.MockTransport(server(calls)))
    api = OpenAIApi(http, ledger=Ledger(tmp_path / "l.sqlite", cap_usd=1), cache=ResponseCache(tmp_path / "c.sqlite"))
    with pytest.raises(OpenAIUnavailable, match="OPENAI_API_KEY"):
        api.chat(MSG)
    assert calls == [] and api.ledger.report()["spent_usd"] == 0


def test_transport_timeout_keeps_the_reservation_but_connect_error_releases(tmp_path):
    def boom(exc):
        def handler(request):
            raise exc

        return handler

    for exc, billed in ((httpx.ReadTimeout("t"), True), (httpx.ConnectError("c"), False)):
        http = OpenAIHttp(KEY, transport=httpx.MockTransport(boom(exc)), sleep=lambda s: None, max_retries=1)
        led = Ledger(tmp_path / f"{billed}.sqlite", cap_usd=1)
        api = OpenAIApi(http, ledger=led, cache=ResponseCache(tmp_path / f"{billed}c.sqlite"))
        with pytest.raises(OpenAIUnavailable):
            api.chat(MSG)
        assert (led.report()["spent_usd"] > 0) is billed


def test_async_chat_matches_sync(tmp_path, calls):
    http = OpenAIHttp(KEY, async_transport=httpx.MockTransport(server(calls)), asleep=lambda s: asyncio.sleep(0))
    api = AsyncOpenAIApi(http, ledger=Ledger(tmp_path / "l.sqlite", cap_usd=1), cache=ResponseCache(tmp_path / "c.sqlite"))
    res = asyncio.run(api.chat(MSG, purpose="async"))
    assert res.text == "ok" and calls[0].headers["authorization"] == f"Bearer {KEY}"
    assert api._sync.ledger.report()["by_purpose_usd"].keys() == {"async"}


# ------------------------------------------------------------------------------------------------ the key never leaks


def test_key_never_in_repr_logs_errors_ledger_or_cache(tmp_path, calls, caplog):
    caplog.set_level(logging.DEBUG)
    leak = {"error": {"message": f"Incorrect API key provided: {KEY}.", "code": "invalid_api_key"}}
    api = make_api(tmp_path, calls, httpx.Response(401, json=leak))
    with pytest.raises(OpenAIAuthError) as ei:
        api.chat(MSG)
    assert KEY not in str(ei.value) and "***" in str(ei.value)
    (tmp_path / "ok").mkdir()
    api2 = make_api(tmp_path / "ok", calls)
    api2.chat(MSG, purpose="x", case_id=CASE)
    client = OpenAILLMClient(api=api2)
    texts = [repr(api.http), repr(api2.http), repr(api2.ledger), repr(client), str(api.http.__dict__.get("base_url"))]
    assert all(KEY not in t for t in texts) and "key=set" in repr(api.http)
    assert KEY not in caplog.text
    for f in (tmp_path / "ledger.sqlite", tmp_path / "ok" / "ledger.sqlite", tmp_path / "ok" / "cache.sqlite"):
        if f.exists():
            assert KEY.encode() not in f.read_bytes()


def test_ledger_stores_no_prompt_or_response_text(tmp_path, calls):
    secret_prompt = "SECRET-PROMPT-TEXT-xyzzy"
    api = make_api(tmp_path, calls, reply(text="SECRET-REPLY-TEXT-plugh"))
    api.chat([{"role": "user", "content": secret_prompt}], purpose="p", case_id=CASE)
    con = sqlite3.connect(tmp_path / "ledger.sqlite")
    dump = json.dumps(con.execute("SELECT * FROM calls").fetchall())
    assert "xyzzy" not in dump and "plugh" not in dump and CASE in dump
    raw = b"".join(p.read_bytes() for p in tmp_path.glob("ledger.sqlite*"))
    assert b"xyzzy" not in raw and b"plugh" not in raw


# ------------------------------------------------------------------------------------------------ cost arithmetic


def test_price_table_matches_the_verified_prices():
    p = price_of("gpt-6-luna")
    assert (float(p.input), float(p.cached_input), float(p.output)) == (0.10, 0.01, 0.50)
    assert float(price_of("gpt-5-nano").output) == 0.40 and float(price_of("gpt-5.6-luna").input) == 0.20
    assert price_of("gpt-6-luna-2026-09-01") is not None  # a dated snapshot of a listed model
    assert price_of("some-unlisted-model") is None


def test_cost_arithmetic_for_known_token_counts():
    p = price_of("gpt-6-luna")
    assert cost_micro(p, 1_000_000, 0, 0) == 100_000  # 0.10 USD
    assert cost_micro(p, 1_000_000, 1_000_000, 0) == 10_000  # all cached: 0.01 USD
    assert cost_micro(p, 0, 0, 1_000_000) == 500_000
    assert cost_micro(p, 1000, 400, 200) == 164
    assert cost_micro(p, 1, 0, 1) == 1  # rounds up: 0.1 + 0.5 = 0.6 micro-USD -> 1
    assert cost_micro(p, 100, 500, 0) == cost_micro(p, 100, 100, 0)  # cached cannot exceed the prompt


def test_input_bound_is_at_least_the_token_count_for_any_text():
    hindi = "अभियुक्त को जमानत दी जाती है " * 50
    msgs = [{"role": "user", "content": hindi}]
    assert input_token_bound(msgs) >= len(hindi.encode("utf-8"))  # >= tokens, since a token covers at least one byte
    assert input_token_bound(msgs, {"type": "object"}) > input_token_bound(msgs)
    assert worst_case_micro(price_of("gpt-6-luna"), MSG, 1000) == cost_micro(price_of("gpt-6-luna"), input_token_bound(MSG), 0, 1000)


def test_unpriced_model_is_refused_before_any_request(tmp_path, calls):
    api = make_api(tmp_path, calls)
    with pytest.raises(OpenAIUnavailable, match="no price"):
        api.chat(MSG, model="mystery-model")
    assert calls == []


# ------------------------------------------------------------------------------------------------ the hard cap


def test_cap_defaults_and_clamp(monkeypatch, caplog):
    assert effective_cap_usd() == 4.50 and HARD_MAX_USD == 5.00
    monkeypatch.setenv("VS_OPENAI_CAP_USD", "3.25")
    assert effective_cap_usd() == 3.25
    for raw in ("5.01", "100", "1e9", "inf"):
        monkeypatch.setenv("VS_OPENAI_CAP_USD", raw)
        with caplog.at_level(logging.WARNING):
            assert effective_cap_usd() <= 5.00, raw
    monkeypatch.setenv("VS_OPENAI_CAP_USD", "100")
    assert effective_cap_usd() == 5.00 and "clamped" in caplog.text
    monkeypatch.setenv("VS_OPENAI_CAP_USD", "-3")
    assert effective_cap_usd() == 0.0
    monkeypatch.setenv("VS_OPENAI_CAP_USD", "lots")
    assert effective_cap_usd() == 4.50


def test_cap_cannot_be_raised_above_five_by_config_or_constructor(monkeypatch, tmp_path):
    from vakeel_sahayak.models.openai import config as cfg

    monkeypatch.setattr(cfg, "openai_config", lambda: {**openai_config(), "cap_usd": 50})
    assert cfg.effective_cap_usd() == 5.00
    assert Ledger(tmp_path / "l.sqlite", cap_usd=99).cap_micro == 5_000_000


def test_call_that_would_exceed_cap_is_refused_before_any_http_request(tmp_path, calls):
    api = make_api(tmp_path, calls, cap_usd=0.0004)  # worst case of a 1000-token answer is ~0.0005 USD
    with pytest.raises(BudgetExceeded) as ei:
        api.chat(MSG, max_tokens=1000)
    assert calls == [] and ei.value.scope == "total" and ei.value.needed_micro > ei.value.cap_micro - ei.value.spent_micro
    assert isinstance(ei.value, ModelUnavailable) and isinstance(ei.value, OpenAIError)
    api.chat(MSG, max_tokens=100)  # a smaller worst case still fits
    assert len(calls) == 1


def test_cumulative_spend_blocks_the_call_that_no_longer_fits(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(pt=10, ct=1000), cap_usd=0.0011)  # each call costs 501 micro-USD, worst case 510
    api.chat([{"role": "user", "content": "one"}], max_tokens=1000)
    api.chat([{"role": "user", "content": "two"}], max_tokens=1000)
    with pytest.raises(BudgetExceeded):
        api.chat([{"role": "user", "content": "three"}], max_tokens=1000)
    assert len(calls) == 2 and api.ledger.report()["spent_usd"] <= 0.0011


def test_ledger_total_never_exceeds_cap_under_20_concurrent_threads(tmp_path):
    calls: list = []
    lock = threading.Lock()

    def answer(request):
        time.sleep(0.01)  # overlap the in-flight reservations
        with lock:
            calls.append(request)
        return httpx.Response(200, json=reply(pt=20, ct=1000))  # costs 502 micro-USD, below its worst case

    http = OpenAIHttp(KEY, transport=httpx.MockTransport(answer), sleep=lambda s: None)
    path = tmp_path / "ledger.sqlite"
    cap = 0.003
    outcomes: list[str] = []

    def worker(i):
        api = OpenAIApi(http, ledger=Ledger(path, cap_usd=cap, run_id=f"t{i}"), cache=ResponseCache(tmp_path / f"c{i}.sqlite"))  # separate objects: cross-connection safety
        try:
            api.chat([{"role": "user", "content": f"call {i}"}], max_tokens=1000)
            outcome = "ok"
        except BudgetExceeded:
            outcome = "refused"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rep = Ledger(path, cap_usd=cap).report()
    assert rep["spent_usd"] <= cap and rep["in_flight"] == 0
    assert outcomes.count("ok") == len(calls) == rep["calls"] and 1 <= outcomes.count("ok") <= 5 and outcomes.count("refused") >= 15


def test_run_cap_is_a_soft_cap_per_run(tmp_path, calls):
    http = OpenAIHttp(KEY, transport=httpx.MockTransport(server(calls, reply(pt=10, ct=1000))), sleep=lambda s: None)
    cache = ResponseCache(tmp_path / "c.sqlite")
    path = tmp_path / "l.sqlite"
    run1 = OpenAIApi(http, ledger=Ledger(path, cap_usd=1.0, run_cap_usd=0.0006, run_id="r1"), cache=cache)
    run1.chat([{"role": "user", "content": "a"}], max_tokens=1000)
    with pytest.raises(BudgetExceeded) as ei:
        run1.chat([{"role": "user", "content": "b"}], max_tokens=1000)
    assert ei.value.scope == "run" and len(calls) == 1
    run2 = OpenAIApi(http, ledger=Ledger(path, cap_usd=1.0, run_cap_usd=0.0006, run_id="r2"), cache=cache)
    run2.chat([{"role": "user", "content": "c"}], max_tokens=1000)  # a new run has its own allowance
    assert len(calls) == 2


def test_run_cap_env_is_clamped_to_total_cap(monkeypatch):
    from vakeel_sahayak.models.openai.config import effective_run_cap_usd

    assert effective_run_cap_usd() is None
    monkeypatch.setenv("VS_OPENAI_RUN_CAP_USD", "1.5")
    assert effective_run_cap_usd() == 1.5
    monkeypatch.setenv("VS_OPENAI_RUN_CAP_USD", "9")
    assert effective_run_cap_usd() == 4.5


def test_ledger_persists_across_reopen_and_reports(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(pt=1000, ct=200, cached=400))
    api.chat(MSG, purpose="alpha")
    api.chat([{"role": "user", "content": "second"}], purpose="beta")
    again = Ledger(tmp_path / "ledger.sqlite", cap_usd=1.0, run_id="run-b")
    rep = again.report()
    assert rep["spent_usd"] == pytest.approx(0.000328) and rep["calls"] == 2 and rep["remaining_usd"] == pytest.approx(1.0 - 0.000328)
    assert rep["by_model_usd"] == {"gpt-6-luna": pytest.approx(0.000328)} and set(rep["by_purpose_usd"]) == {"alpha", "beta"}
    text = format_report(rep)
    assert "per model" in text and "per purpose" in text and "alpha" in text and "remaining" in text
    assert again.last_served_model("gpt-6-luna") == "gpt-6-luna-2026-09-01"


def test_cli_report_prints_totals(tmp_path, calls, monkeypatch, capsys):
    from vakeel_sahayak.models.openai import ledger as ledger_mod

    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    led = Ledger()
    http = OpenAIHttp(KEY, transport=httpx.MockTransport(server(calls)), sleep=lambda s: None)
    OpenAIApi(http, ledger=led, cache=ResponseCache()).chat(MSG, purpose="cli")
    assert ledger_mod.main([]) == 0
    out = capsys.readouterr().out
    assert "OpenAI spend" in out and "cli" in out and KEY not in out
    assert ledger_mod.main(["--json"]) == 0 and json.loads(capsys.readouterr().out)["calls"] == 1


def test_in_flight_reservations_count_against_the_cap(tmp_path):
    led = Ledger(tmp_path / "l.sqlite", cap_usd=0.001)
    r = led.reserve("gpt-6-luna", 600, "a")
    with pytest.raises(BudgetExceeded):
        led.reserve("gpt-6-luna", 500, "b")
    led.release(r)
    led.reserve("gpt-6-luna", 500, "b")  # the released slice is free again


# ------------------------------------------------------------------------------------------------ response cache


def test_identical_temperature_zero_call_is_free_the_second_time(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(pt=100, ct=50))
    first = api.chat(MSG, purpose="eval")
    second = api.chat(MSG, purpose="eval")
    assert len(calls) == 1 and second.from_cache and second.cost_micro == 0 and second.text == first.text
    rep = api.ledger.report()
    assert rep["cache_hits"] == 1 and rep["calls"] == 1 and rep["spent_usd"] == pytest.approx(first.cost_micro / 1e6)


def test_cache_hit_needs_no_budget_and_survives_a_new_process(tmp_path, calls):
    api = make_api(tmp_path, calls)
    api.chat(MSG)
    broke = OpenAIApi(
        OpenAIHttp(KEY, transport=httpx.MockTransport(server(calls))), ledger=Ledger(tmp_path / "ledger.sqlite", cap_usd=0.0), cache=ResponseCache(tmp_path / "cache.sqlite")
    )
    assert broke.chat(MSG).from_cache and len(calls) == 1  # cap spent entirely, the cached answer still works


def test_cache_key_covers_model_messages_schema_temperature(tmp_path, calls):
    api = make_api(tmp_path, calls)
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    api.chat(MSG)
    api.chat(MSG, json_schema=schema)
    api.chat(MSG, model="gpt-5-nano")
    api.chat([{"role": "user", "content": "different"}])
    assert len(calls) == 4
    api.chat(MSG, json_schema=schema)
    assert len(calls) == 4


def test_nonzero_temperature_is_never_cached(tmp_path, calls):
    api = make_api(tmp_path, calls)
    api.chat(MSG, temperature=0.7)
    api.chat(MSG, temperature=0.7)
    assert len(calls) == 2


def test_truncated_answers_are_not_cached(tmp_path, calls):
    api = make_api(tmp_path, calls, reply(text="partial", finish="length"))
    api.chat(MSG)
    api.chat(MSG)
    assert len(calls) == 2


# ------------------------------------------------------------------------------------------------ privacy gate


def test_external_mode_resolution_and_sarvam_alias(monkeypatch):
    from vakeel_sahayak.models.sarvam.policy import provider_mode

    assert provider_mode("openai") is SarvamMode.OFF and sarvam_mode() is SarvamMode.OFF  # default off
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    assert provider_mode("openai") is SarvamMode.PSEUDONYMISED and sarvam_mode() is SarvamMode.PSEUDONYMISED
    monkeypatch.setenv("VS_SARVAM", "public")  # the alias wins for Sarvam only
    assert sarvam_mode() is SarvamMode.PUBLIC and provider_mode("openai") is SarvamMode.PSEUDONYMISED
    monkeypatch.delenv("VS_EXTERNAL")
    assert provider_mode("openai") is SarvamMode.OFF  # VS_SARVAM never enables OpenAI
    monkeypatch.setenv("VS_EXTERNAL", "everything")
    with pytest.raises(ValueError, match="VS_EXTERNAL"):
        provider_mode("openai")


def test_off_blocks_every_data_class_for_openai():
    for data in DataClass:
        with pytest.raises(OpenAIPolicyError, match="off"):
            authorize("chat", SarvamScope(data, case_id=CASE, event_log=EventLog()), text=CLEAN, provider="openai")


def test_public_mode_allows_public_only(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "public")
    authorize("chat", SarvamScope(DataClass.PUBLIC), text="A public order.", provider="openai")
    with pytest.raises(OpenAIPolicyError, match="pseudonymised"):
        authorize("chat", SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE), text=CLEAN, provider="openai")
    with pytest.raises(OpenAIPolicyError, match="consented"):
        authorize("chat", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=EventLog()), text=CLEAN, provider="openai")


def test_pseudonymised_mode_checks_the_boundary(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    scope = SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog())
    authorize("chat", scope, payload={"messages": [{"role": "user", "content": CLEAN}]}, provider="openai")
    with pytest.raises(PrivacyBoundaryError):
        authorize("chat", scope, payload={"messages": [{"role": "user", "content": RAW_NAME}]}, provider="openai")


def test_consented_mode_needs_a_per_case_openai_consent_event(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "consented")
    log = EventLog()
    raw = SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log)
    with pytest.raises(OpenAIPolicyError, match="consented"):
        authorize("chat", raw, text=RAW_NAME, provider="openai")
    record_consent(log, CASE, True, provider="sarvam")  # Sarvam consent does not cover OpenAI
    with pytest.raises(OpenAIPolicyError):
        authorize("chat", raw, text=RAW_NAME, provider="openai")
    record_consent(log, CASE, True, provider="openai")
    authorize("chat", raw, text=RAW_NAME, provider="openai")
    from vakeel_sahayak.models.sarvam.policy import has_consent

    record_consent(log, CASE, False, provider="openai")  # the latest event wins
    assert not has_consent(log, CASE, "openai") and has_consent(log, CASE, "sarvam")
    with pytest.raises(OpenAIPolicyError):
        authorize("chat", raw, text=RAW_NAME, provider="openai")
    with pytest.raises(OpenAIPolicyError, match="case id"):
        authorize("chat", SarvamScope(DataClass.CLIENT_RAW), text=RAW_NAME, provider="openai")


def test_client_data_calls_are_audited_without_payload(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    log = EventLog()
    authorize("chat", SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=log), payload={"messages": [{"role": "user", "content": CLEAN}]}, provider="openai")
    from vakeel_sahayak.schemas.enums import EventKind

    events = [e for e in log.read(CASE, kind=EventKind.TOOL_CALL) if e.tool == "openai.chat"]
    assert len(events) == 1 and "Accused-1" not in json.dumps(events[0].inputs)


def test_client_without_declared_scope_is_blocked_and_sends_nothing(monkeypatch, tmp_path, calls):
    api = make_api(tmp_path, calls)
    llm = OpenAILLMClient(api=api)  # data=None: the class comes from the caller's declared scope
    with pytest.raises(OpenAIPolicyError):
        llm.generate("hello")  # mode off
    monkeypatch.setenv("VS_EXTERNAL", "public")
    with pytest.raises(OpenAIPolicyError, match="client_raw"):
        llm.generate("hello")  # no declared scope = the most restricted class
    assert calls == []
    with public_scope("unit"):
        assert llm.generate("hello") == "ok"
    assert len(calls) == 1


def test_declared_scope_purpose_and_case_reach_the_ledger(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    api = make_api(tmp_path, calls)
    llm = OpenAILLMClient(api=api, data=DataClass.CLIENT_TEXT, where="ada", role="agents_14b")
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog(), purpose="draft"):
        llm.chat([{"role": "user", "content": CLEAN}])
    row = sqlite3.connect(tmp_path / "ledger.sqlite").execute("SELECT purpose, case_id FROM calls").fetchone()
    assert row == ("draft", CASE)


# ------------------------------------------------------------------------------------------------ adapter


def test_adapter_is_an_llm_client_with_usage_cost_and_cache_counters(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("VS_EXTERNAL", "public")
    llm = OpenAILLMClient(api=make_api(tmp_path, calls, reply("hi", 1000, 200, 400)), data=DataClass.PUBLIC)
    assert isinstance(llm, LLMClient) and llm.where == "api" and llm.name == "openai" and llm.model_id == "gpt-6-luna" and llm.family == "openai"
    done = llm.complete("Say hi")
    assert (done.text, done.prompt_tokens, done.completion_tokens, done.model) == ("hi", 1000, 200, "gpt-6-luna")
    assert llm.cached_tokens == 400 and llm.spend_usd() == pytest.approx(0.000164) and llm.version() == "gpt-6-luna-2026-09-01"
    llm.complete("Say hi")  # cache hit: free
    assert llm.cache_hits == 1 and llm.spend_usd() == pytest.approx(0.000164) and llm.usage.calls == 2


def test_structured_call_works_with_json_schema_mode_and_repairs(monkeypatch, tmp_path, calls):
    from pydantic import BaseModel

    class Out(BaseModel):
        verdict: str
        score: int

    monkeypatch.setenv("VS_EXTERNAL", "public")
    answers = iter([reply("not json at all"), reply('{"verdict": "ok", "score": 3}')])
    api = make_api(tmp_path, calls, lambda r: next(answers))
    llm = OpenAILLMClient(api=api, data=DataClass.PUBLIC)
    out = llm.structured("Judge it.", Out)
    assert out == Out(verdict="ok", score=3) and len(calls) == 2
    fmt = bodies(calls)[0]["response_format"]["json_schema"]
    assert fmt["strict"] is True and set(fmt["schema"]["required"]) == {"verdict", "score"}
    assert "not json at all" in json.dumps(bodies(calls)[1])  # the repair prompt shows the bad answer


def test_agent_ask_works_through_the_openai_client(monkeypatch, tmp_path, calls):
    from pydantic import BaseModel

    class Ans(BaseModel):
        text: str

    monkeypatch.setenv("VS_EXTERNAL", "public")
    llm = OpenAILLMClient(api=make_api(tmp_path, calls, reply('{"text": "done"}')), data=DataClass.PUBLIC)
    from vakeel_sahayak.orchestration.structured_output import structured_call

    assert structured_call(llm, "Answer in JSON.", Ans).value == Ans(text="done")


# ------------------------------------------------------------------------------------------------ fallback


def test_fallback_to_offline_when_over_cap_blocked_or_failing(monkeypatch, tmp_path, calls):
    from vakeel_sahayak.models.offline_llm import OfflineLLM
    from vakeel_sahayak.models.openai.errors import OpenAIError as Err

    monkeypatch.setenv("VS_EXTERNAL", "public")
    errors = (Err, PrivacyBoundaryError)
    # over the cap
    api = make_api(tmp_path, calls, cap_usd=0.0)
    fb = FallbackLLM(OpenAILLMClient(api=api, data=DataClass.PUBLIC, where="ada"), lambda: OfflineLLM(role="agents_14b", where="ada"), "ada", errors=errors)
    fb.generate("Say hi")
    assert fb.last_engine is fb.local and fb.is_offline and calls == [] and fb.family == "offline"
    # policy-blocked (client text in public mode)
    (tmp_path / "x").mkdir()
    api2 = make_api(tmp_path / "x", calls)
    fb2 = FallbackLLM(OpenAILLMClient(api=api2, data=DataClass.CLIENT_TEXT, where="ada"), lambda: OfflineLLM(role="agents_14b", where="ada"), "ada", errors=errors)
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        fb2.generate(CLEAN)
    assert fb2.is_offline and calls == []
    # the API fails
    (tmp_path / "y").mkdir()
    api3 = make_api(tmp_path / "y", calls, httpx.Response(500, json={}), max_retries=1)
    fb3 = FallbackLLM(OpenAILLMClient(api=api3, data=DataClass.PUBLIC, where="ada"), lambda: OfflineLLM(role="agents_14b", where="ada"), "ada", errors=errors)
    fb3.generate("Say hi")
    assert fb3.is_offline and len(calls) == 2
    # and when it works, OpenAI answers
    (tmp_path / "z").mkdir()
    fb4 = FallbackLLM(OpenAILLMClient(api=make_api(tmp_path / "z", [], reply("from openai", 5, 2)), data=DataClass.PUBLIC), lambda: OfflineLLM(role="agents_14b", where="ada"), "ada", errors=errors)
    assert fb4.complete("Say hi").text == "from openai" and fb4.name == "openai" and (fb4.usage.prompt_tokens, fb4.usage.completion_tokens) == (5, 2)


# ------------------------------------------------------------------------------------------------ factory, families, run stamp


def use_mock_server(monkeypatch, calls, answer=None):
    """Every OpenAIHttp built by the adapters talks to the mock server (key from env, no sleeping)."""
    original = http_mod.OpenAIHttp.__init__

    def patched(self, *a, **kw):
        kw.setdefault("transport", httpx.MockTransport(server(calls, answer)))
        kw.setdefault("sleep", lambda s: None)
        original(self, *a, **kw)

    monkeypatch.setattr(http_mod.OpenAIHttp, "__init__", patched)


def _runtime_cfg(monkeypatch, role="agents_14b", runtime="openai", **extra):
    real = factory.role_config
    monkeypatch.setattr(factory, "role_config", lambda r: {**real(r), **({"runtime": runtime, **extra} if r == role else {})})


def test_factory_returns_exactly_the_local_clients_while_openai_is_off(monkeypatch):
    from vakeel_sahayak.models.vllm_client import VllmClient

    monkeypatch.setenv("OPENAI_API_KEY", KEY)  # a key alone changes nothing
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")  # the backend choice alone changes nothing either: the gate is off
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.delenv("OPENAI_API_KEY")  # and no key
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)


def test_env_backend_openai_wraps_agent_roles_with_fallback(monkeypatch, calls, tmp_path):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    use_mock_server(monkeypatch, calls)
    for role in ("agents_14b", "munshi_4b", "extractor_4b"):
        llm = factory.get_llm(role)
        assert isinstance(llm, FallbackLLM) and isinstance(llm.primary, OpenAILLMClient) and llm.primary.data is DataClass.CLIENT_TEXT
        assert llm.where == factory.role_where(role) and llm.primary.model_id == "gpt-6-luna"
    from vakeel_sahayak.models.offline_llm import OfflineLLM

    llm = factory.get_llm("agents_14b")
    llm._local = OfflineLLM(role="agents_14b", where="ada")  # no vLLM in the test environment
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        assert llm.chat(MSG) == "ok"
        assert llm.name == "openai"
        llm.chat([{"role": "user", "content": RAW_NAME}])  # raw name: boundary refuses, the local client answers
        assert llm.last_engine is llm.local
    assert len(calls) == 1
    assert not isinstance(factory.get_llm("fallback_8b"), FallbackLLM)  # only the agent roles follow the env


def test_env_backend_local_and_offline(monkeypatch):
    from vakeel_sahayak.models.vllm_client import VllmClient

    _runtime_cfg(monkeypatch)  # yaml says openai
    monkeypatch.setenv("VS_LLM_BACKEND", "local")
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)  # local forces the built-in runtime
    monkeypatch.setenv("VS_LLM_BACKEND", "offline")
    assert factory.get_llm("agents_14b").is_offline
    monkeypatch.setenv("VS_LLM_BACKEND", "gpt")
    with pytest.raises(ValueError, match="VS_LLM_BACKEND"):
        factory.get_llm("agents_14b")


def test_yaml_runtime_openai_and_models_offline_wins(monkeypatch, calls, tmp_path):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    _runtime_cfg(monkeypatch, "teacher", model="gpt-5-nano")
    monkeypatch.setenv("VS_EXTERNAL", "public")
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    use_mock_server(monkeypatch, calls)
    llm = factory.get_llm("teacher")
    assert isinstance(llm, FallbackLLM) and llm.primary.model_id == "gpt-5-nano" and llm.primary.data is DataClass.PUBLIC and llm.where == "api"
    assert llm.generate("hi") == "ok"
    monkeypatch.setenv("VS_MODELS", "offline")
    assert factory.get_llm("teacher").is_offline


def test_env_backend_sarvam_uses_the_sarvam_default_model(monkeypatch):
    from vakeel_sahayak.models.sarvam.adapters import SarvamLLMClient

    monkeypatch.setenv("VS_LLM_BACKEND", "sarvam")
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")  # one gate: VS_EXTERNAL also switches Sarvam on
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    llm = factory.get_llm("agents_14b")
    assert isinstance(llm, FallbackLLM) and isinstance(llm.primary, SarvamLLMClient) and llm.primary.model_id == "sarvam-105b"


def test_labeler_and_teacher_can_use_openai_public_only(monkeypatch, tmp_path, calls):
    from vakeel_sahayak.models.labeler import EvalLabeler
    from vakeel_sahayak.models.teacher import TeacherClient

    monkeypatch.setenv("VS_LABELER", "openai")
    monkeypatch.setenv("VS_TEACHER", "openai")
    lab, tea = EvalLabeler(), TeacherClient()
    assert (lab.backend(), lab.family, lab.model_name()) == ("openai", "openai", "gpt-6-luna")
    assert (tea.backend, tea.family, tea.model_id, tea.where) == ("openai", "openai", "gpt-6-luna", "api")
    for client in (lab.client(), tea.client):
        assert isinstance(client, OpenAILLMClient) and client.data is DataClass.PUBLIC and client.where == "api"
    with pytest.raises(OpenAIPolicyError):  # mode off: even public data is blocked
        lab.client().generate("a public order")
    monkeypatch.delenv("VS_LABELER")
    assert EvalLabeler().backend() == "local" and EvalLabeler().family == "llama"


def test_family_names():
    assert model_family("gpt-6-luna") == "openai" and model_family("gpt-5-nano-2025-08-07") == "openai" and model_family("o4-mini") == "openai"
    assert model_family("sarvam-105b") == "sarvam" and model_family("Qwen/Qwen3-14B-AWQ") == "qwen" and model_family("meta-llama/Llama-3.1-8B-Instruct") == "llama"
    assert [factory.llm_family(b) for b in ("openai", "sarvam", "offline")] == ["openai", "sarvam", "offline"]
    assert factory.llm_family("vllm", "Qwen/Qwen3-14B-AWQ") == "qwen" and factory.llm_family("local", "meta-llama/Llama-3.1-8B-Instruct") == "llama"
    from vakeel_sahayak.models.offline_llm import OfflineLLM

    assert OfflineLLM(role="agents_14b").family == "offline" and OpenAILLMClient().family == "openai"


def test_assert_independent_families(monkeypatch):
    assert factory.assert_independent_families() == ("llama", "qwen")  # defaults: Llama labels, Qwen teaches, Qwen is judged
    with pytest.raises(ValueError, match="labeler and the teacher"):
        factory.assert_independent_families("qwen", "qwen")
    with pytest.raises(ValueError, match="self-labelled"):
        factory.assert_independent_families("qwen", "openai")  # the judged agents are Qwen
    monkeypatch.setenv("VS_LABELER", "openai")
    monkeypatch.setenv("VS_TEACHER", "sarvam")
    assert factory.assert_independent_families() == ("openai", "sarvam")
    monkeypatch.setenv("VS_TEACHER", "openai")
    with pytest.raises(ValueError, match="labeler and the teacher"):
        factory.assert_independent_families()
    monkeypatch.setenv("VS_LABELER", "sarvam")
    monkeypatch.setenv("VS_LLM_BACKEND", "sarvam")
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    with pytest.raises(ValueError, match="self-labelled"):  # Sarvam judging a Sarvam-labelled gold set
        factory.assert_independent_families()


def test_describe_run_models_stamp(monkeypatch, tmp_path, calls):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    stamp = factory.describe_run_models()
    assert set(stamp["roles"]) == {"agents_14b", "munshi_4b", "extractor_4b"} and "openai" not in stamp
    assert stamp["roles"]["agents_14b"]["provider"] == "local" and stamp["roles"]["agents_14b"]["family"] == "qwen"
    assert stamp["labeler"]["family"] == "llama" and stamp["teacher"]["family"] == "qwen" and stamp["families_independent"] is True
    assert len(stamp["date"]) == 10 and all("version" in r and "date" in r for r in stamp["roles"].values())
    json.dumps(stamp)  # JSON-able, so it can go into a run record

    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    monkeypatch.setenv("VS_EXTERNAL", "public")
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    stamp = factory.describe_run_models()
    role = stamp["roles"]["agents_14b"]
    assert (role["provider"], role["model"], role["family"]) == ("openai", "gpt-6-luna", "openai")
    assert "alias" in role["version"] and stamp["openai"]["cap_usd"] == 4.50 and stamp["openai"]["spent_usd"] == 0 and stamp["openai"]["priced"] == {"gpt-6-luna": True}
    # after a real (mocked) call the snapshot OpenAI reported is stamped
    OpenAIApi(OpenAIHttp(KEY, transport=httpx.MockTransport(server(calls))), ledger=Ledger(), cache=ResponseCache()).chat(MSG)
    stamp = factory.describe_run_models()
    assert stamp["roles"]["agents_14b"]["version"] == "gpt-6-luna-2026-09-01" and stamp["openai"]["spent_usd"] > 0
    assert KEY not in json.dumps(stamp)
    assert stamp["families_independent"] is True  # llama labels an openai-judged system
    monkeypatch.setenv("VS_LABELER", "openai")
    assert factory.describe_run_models()["families_independent"] is False


def test_describe_run_models_offline(monkeypatch):
    monkeypatch.setenv("VS_MODELS", "offline")
    stamp = factory.describe_run_models()
    assert all(r["provider"] == "offline" and r["family"] == "offline" for r in stamp["roles"].values())


def test_unwritable_ledger_refuses_the_call_before_any_request(monkeypatch, tmp_path, calls):
    api = make_api(tmp_path, calls)

    def broken(self, *a, **kw):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(Ledger, "_reserve", broken)
    with pytest.raises(OpenAIError, match="ledger is unavailable"):
        api.chat(MSG)
    assert calls == []
