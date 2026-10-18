"""Sarvam integration (models/sarvam): transport, privacy policy, request/response mapping, adapters, fallback and factory.

Everything runs against `httpx.MockTransport`; nothing here touches the network. The fixtures follow the shapes in the
Sarvam docs (docs.sarvam.ai, fetched 2026-10-19): header `api-subscription-key`; chat `/v1/chat/completions`;
`/translate` -> translated_text; `/text-lid` -> language_code + script_code; `/speech-to-text` -> transcript;
`/text-to-speech` -> audios (base64 WAV); `/doc-ai/v1/job/digitise` -> job_id, status, download-url, ZIP.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import wave
import zipfile

import httpx
import pytest

from vakeel_sahayak.models import factory
from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, model_family
from vakeel_sahayak.models.sarvam import (
    DataClass,
    SarvamAuthError,
    SarvamError,
    SarvamMode,
    SarvamPolicyError,
    SarvamQuotaError,
    SarvamRateLimited,
    SarvamScope,
    SarvamUnavailable,
    authorize,
    has_consent,
    public_scope,
    record_consent,
    sarvam_mode,
    sarvam_scope,
)
from vakeel_sahayak.models.sarvam import http as http_mod
from vakeel_sahayak.models.sarvam.adapters import (
    SarvamAsr,
    SarvamLangId,
    SarvamLLMClient,
    SarvamTranslator,
    SarvamTts,
    SarvamVisionClient,
)
from vakeel_sahayak.models.sarvam.api import AsyncSarvamApi, SarvamApi, to_bcp47, unpack_digitised
from vakeel_sahayak.models.sarvam.fallback import FallbackLLM, FallbackTranslator, FallbackVision
from vakeel_sahayak.models.sarvam.http import SarvamHttp
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind

KEY = "sk-test-SECRET-0123456789"
CASE = "case-0007"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CLEAN = "The accused Accused-1 was arrested on 20.08.2024."
RAW_NAME = "The accused Rajesh Kumar was arrested on 20.08.2024."


# ------------------------------------------------------------------------------------------------ helpers


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No Sarvam state leaks between tests; the real key (if any) is never used here."""
    for var in ("VS_SARVAM", "VS_MODELS", "VS_LABELER", "VS_TEACHER", "SARVAM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    factory.reset_clients()
    yield
    factory.reset_clients()


@pytest.fixture()
def calls():
    """Recorded requests of the mocked server."""
    return []


def make_http(handler, **kw) -> SarvamHttp:
    """A transport with the test key, a mock server and no real sleeping."""
    delays: list[float] = []
    http = SarvamHttp(KEY, transport=httpx.MockTransport(handler), sleep=delays.append, **kw)
    http.delays = delays  # type: ignore[attr-defined]
    return http


def json_response(data, status=200):
    return httpx.Response(status, json=data)


def router(table: dict, calls: list):
    """A handler answering by URL path with a dict, a callable(request) or an httpx.Response."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        out = table[request.url.path]
        if callable(out):
            out = out(request)
        return out if isinstance(out, httpx.Response) else json_response(out)

    return handler


def chat_reply(text="ok", pt=11, ct=3, finish="stop"):
    return {"id": "x", "object": "chat.completion", "model": "sarvam-105b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}}  # fmt: skip


def api_with(table, calls) -> SarvamApi:
    return SarvamApi(make_http(router(table, calls)), sleep=lambda s: None)


def wav_bytes(seconds: int, rate: int = 1000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * (seconds * rate))
    return buf.getvalue()


def digitise_zip(text="# Order\n\nThe accused was arrested.") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("document.md", text)
        z.writestr("metadata/page_001.json", "{}")
        z.writestr("manifest.json", "{}")
    return buf.getvalue()


def vision_table(calls, status="completed", zip_blob=None, polls=("running", "completed")):
    seq = iter(polls)

    def st(_):
        return {"job_id": "job1", "status": next(seq, status), "usage": {"pages_total": 1, "pages_succeeded": 1, "pages_failed": 0}}

    return {
        "/doc-ai/v1/job/digitise": {"job_id": "job1", "status": "pending"},
        "/doc-ai/v1/job/job1/status": st,
        "/doc-ai/v1/job/job1/download-url": {"method": "GET", "url": "https://storage.example/out.zip"},
        "/out.zip": httpx.Response(200, content=zip_blob or digitise_zip()),
    }


def consented_log(granted=True) -> EventLog:
    log = EventLog()
    if granted is not None:
        record_consent(log, CASE, granted)
    return log


def use_mock_server(monkeypatch, table, calls):
    """Make every SarvamHttp built by the factory/adapters talk to the mock server (key from env, no sleeping)."""
    original = http_mod.SarvamHttp.__init__

    def patched(self, *a, **kw):
        kw.setdefault("transport", httpx.MockTransport(router(table, calls)))
        kw.setdefault("sleep", lambda s: None)
        original(self, *a, **kw)

    monkeypatch.setattr(http_mod.SarvamHttp, "__init__", patched)


# ------------------------------------------------------------------------------------------------ transport


def test_auth_header_is_sent_and_key_never_in_repr_logs_or_errors(caplog):
    seen = []
    http = make_http(lambda r: (seen.append(r), json_response({"ok": 1}))[1])
    with caplog.at_level(logging.DEBUG, logger="vakeel_sahayak.sarvam"):
        http.request("POST", "/translate", json={"input": "x"})
    assert seen[0].headers["api-subscription-key"] == KEY
    assert str(seen[0].url) == "https://api.sarvam.ai/translate"
    assert KEY not in repr(http) and KEY not in caplog.text
    echo = make_http(lambda r: json_response({"error": {"code": "invalid_request_error", "message": f"bad key {KEY}"}}, 400))
    with pytest.raises(SarvamError) as exc:
        echo.request("POST", "/translate", json={})
    assert KEY not in str(exc.value) and "invalid_request_error" in str(exc.value)


def test_missing_key_raises_unavailable_without_sending():
    sent = []
    http = SarvamHttp(None, transport=httpx.MockTransport(lambda r: sent.append(r) or json_response({})))
    with pytest.raises(SarvamUnavailable, match="SARVAM_API_KEY"):
        http.request("GET", "/x")
    assert sent == []


def test_key_comes_from_the_environment_only(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    assert SarvamHttp().has_key
    monkeypatch.delenv("SARVAM_API_KEY")
    assert not SarvamHttp().has_key


def test_retries_429_then_succeeds_with_exponential_backoff():
    answers = iter([429, 503, 500, 200])
    http = make_http(lambda r: json_response({"ok": 1} if (s := next(answers)) == 200 else {"error": {"code": "rate_limit_exceeded_error", "message": "slow"}}, s))
    assert http.request("POST", "/x").json() == {"ok": 1}
    assert http.delays == [1.0, 2.0, 4.0]  # type: ignore[attr-defined]


def test_backoff_is_capped_and_retries_are_bounded():
    n = []
    http = make_http(lambda r: n.append(1) or json_response({"error": {"code": "rate_limit_exceeded_error"}}, 429), max_retries=3, max_delay=3.0)
    with pytest.raises(SarvamRateLimited):
        http.request("POST", "/x")
    assert len(n) == 4 and http.delays == [1.0, 2.0, 3.0]  # type: ignore[attr-defined]


def test_retry_after_header_is_honoured_when_present():
    answers = iter([429, 200])
    http = make_http(lambda r: httpx.Response(next(answers), json={}, headers={"retry-after": "7"}))
    http.request("POST", "/x")
    assert http.delays == [7.0]  # type: ignore[attr-defined]


@pytest.mark.parametrize("status,exc", [(403, SarvamAuthError), (400, SarvamError), (422, SarvamError)])
def test_client_errors_are_not_retried(status, exc):
    n = []
    http = make_http(lambda r: n.append(1) or json_response({"error": {"code": "invalid_request_error", "message": "m"}}, status))
    with pytest.raises(exc):
        http.request("POST", "/x")
    assert len(n) == 1


def test_exhausted_credits_are_not_retried():
    n = []
    http = make_http(lambda r: n.append(1) or json_response({"error": {"code": "insufficient_quota_error", "message": "credits"}}, 429))
    with pytest.raises(SarvamQuotaError):
        http.request("POST", "/x")
    assert len(n) == 1


def test_transport_errors_retry_then_raise_unavailable():
    n = []

    def boom(request):
        n.append(1)
        raise httpx.ConnectError("down")

    http = make_http(boom, max_retries=2)
    with pytest.raises(SarvamUnavailable):
        http.request("GET", "/x")
    assert len(n) == 3


async def test_async_transport_retries_and_maps_chat():
    answers = iter([429, 200])
    sleeps = []

    async def asleep(s):
        sleeps.append(s)

    def handler(request):
        return json_response(chat_reply("hello") if next(answers) == 200 else {"error": {"code": "rate_limit_exceeded_error"}}, 200 if len(sleeps) else 429)

    http = SarvamHttp(KEY, async_transport=httpx.MockTransport(handler), asleep=asleep)
    api = AsyncSarvamApi(http)
    res = await api.chat([{"role": "user", "content": "ping"}])
    assert res.text == "hello" and sleeps == [1.0]


# ------------------------------------------------------------------------------------------------ policy


def test_mode_resolution_env_and_yaml(monkeypatch):
    assert sarvam_mode() is SarvamMode.OFF  # default
    for raw, want in (("public", SarvamMode.PUBLIC), ("Pseudonymised", SarvamMode.PSEUDONYMISED), ("consented", SarvamMode.CONSENTED), ("off", SarvamMode.OFF)):
        monkeypatch.setenv("VS_SARVAM", raw)
        assert sarvam_mode() is want
    monkeypatch.setenv("VS_SARVAM", "everything")
    with pytest.raises(ValueError, match="VS_SARVAM"):
        sarvam_mode()


def test_off_blocks_every_data_class(monkeypatch):
    for data in DataClass:
        with pytest.raises(SarvamPolicyError, match="off"):
            authorize("chat", SarvamScope(data, case_id=CASE, event_log=consented_log()), text=CLEAN)


def test_public_mode_allows_public_only(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "public")
    authorize("chat", SarvamScope(DataClass.PUBLIC), text="Judge Name J. decided the bail matter.")
    with pytest.raises(SarvamPolicyError, match="pseudonymised"):
        authorize("chat", SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE), text=CLEAN)
    with pytest.raises(SarvamPolicyError, match="consented"):
        authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log()), nbytes=10)


def test_pseudonymised_mode_checks_the_boundary_on_text(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    scope = SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog())
    authorize("translate", scope, text=CLEAN)
    with pytest.raises(PrivacyBoundaryError):
        authorize("translate", scope, text=RAW_NAME)
    with pytest.raises(PrivacyBoundaryError):
        authorize("translate", scope, text="Call 9876543210 now")
    with pytest.raises(PrivacyBoundaryError):  # binary content can never pass as pseudonymised text
        authorize("vision", scope, nbytes=100)
    with pytest.raises(PrivacyBoundaryError):  # chat messages are walked, not just one string
        authorize("chat", scope, payload={"messages": [{"role": "user", "content": RAW_NAME}]})
    with pytest.raises(SarvamPolicyError, match="consented"):  # raw data still needs the top mode
        authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log()), nbytes=1)


def test_pseudonymised_boundary_uses_the_case_alias_map(monkeypatch):
    from vakeel_sahayak.privacy.pseudonymise import PseudonymMap

    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    mapping = PseudonymMap()
    mapping.alias_for("Sunil Verma", "accused")
    scope = SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, mapping=mapping)
    with pytest.raises(PrivacyBoundaryError):
        authorize("chat", scope, text="Sunil Verma was arrested")
    authorize("chat", scope, text="Accused-1 was arrested")


def test_consented_mode_needs_a_counsel_consent_event(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "consented")
    with pytest.raises(SarvamPolicyError, match="consented to sending"):
        authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log(None)), nbytes=5)
    with pytest.raises(SarvamPolicyError, match="case id"):
        authorize("vision", SarvamScope(DataClass.CLIENT_RAW), nbytes=5)
    with pytest.raises(SarvamPolicyError):  # the default scope is the most restricted one
        authorize("vision", nbytes=5)
    log = consented_log()
    authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log), nbytes=5)


def test_consent_is_per_case_and_can_be_revoked(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "consented")
    log = consented_log()
    assert has_consent(log, CASE) and not has_consent(log, "case-0008")
    record_consent(log, CASE, granted=False)
    assert not has_consent(log, CASE)
    with pytest.raises(SarvamPolicyError):
        authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log), nbytes=5)
    record_consent(log, CASE, granted=True)
    assert has_consent(log, CASE)


def test_consent_by_a_non_counsel_actor_does_not_count():
    from vakeel_sahayak.schemas.events import Event

    log = EventLog()
    log.append(Event(event_id="", case_id=CASE, ts="", kind=EventKind.USER_ACTION, actor="MUNSHI", tool="sarvam_consent", inputs={"action": "sarvam_consent", "granted": True}))
    assert not has_consent(log, CASE)


def test_every_client_data_call_is_logged_without_payload_content(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "consented")
    log = consented_log()
    authorize("vision", SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log, purpose="munshi.read_file"), nbytes=2048)
    authorize("translate", SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=log), text=CLEAN)
    audit = [e for e in log.read(CASE, kind=EventKind.TOOL_CALL)]
    assert [e.tool for e in audit] == ["sarvam.vision", "sarvam.translate"]
    assert audit[0].inputs["bytes"] == 2048 and audit[1].inputs["chars"] == len(CLEAN)
    dumped = json.dumps([e.model_dump(mode="json") for e in audit])
    assert "Accused-1" not in dumped and "arrested" not in dumped


def test_public_calls_write_no_case_events(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "public")
    log = EventLog()
    authorize("chat", SarvamScope(DataClass.PUBLIC, case_id=CASE, event_log=log), text="public order")
    assert log.read(CASE) == []


def test_scope_context_manager_nests_and_restores():
    from vakeel_sahayak.models.sarvam import current_scope

    assert current_scope().data is DataClass.CLIENT_RAW
    with public_scope("t8"):
        assert current_scope().data is DataClass.PUBLIC
        with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE):
            assert current_scope().case_id == CASE
        assert current_scope().data is DataClass.PUBLIC
    assert current_scope().data is DataClass.CLIENT_RAW


# ------------------------------------------------------------------------------------------------ wrappers: request/response mapping


def test_chat_request_and_response_mapping(calls):
    api = api_with({"/v1/chat/completions": chat_reply("New Delhi.", 14, 4)}, calls)
    res = api.chat([{"role": "user", "content": "ping"}], max_tokens=99999, temperature=0.2)
    body = json.loads(calls[0].content)
    assert body["model"] == "sarvam-105b" and body["messages"] == [{"role": "user", "content": "ping"}]
    assert body["max_tokens"] == 4096  # the plan's cap from models.yaml
    assert "reasoning_effort" in body and body["reasoning_effort"] is None  # explicit null disables thinking
    assert "response_format" not in body
    assert (res.text, res.prompt_tokens, res.completion_tokens, res.finish_reason) == ("New Delhi.", 14, 4, "stop")


def test_chat_structured_output_sends_json_schema_and_falls_back_to_json_mode(calls):
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            return json_response({"error": {"code": "invalid_request_error", "message": "unsupported"}}, 400)
        return json_response(chat_reply('{"a": 1}'))

    api = SarvamApi(make_http(handler))
    assert api.chat([{"role": "user", "content": "x"}], json_schema=schema).text == '{"a": 1}'
    assert seen == ["json_schema", "json_object"]
    body = api.chat_body([], json_schema=schema)
    assert body["response_format"]["json_schema"]["schema"] == schema


def test_chat_empty_answer_at_the_token_limit_is_an_error(calls):
    api = api_with({"/v1/chat/completions": chat_reply("", finish="length")}, calls)
    with pytest.raises(SarvamError, match="token limit"):
        api.chat([{"role": "user", "content": "x"}])


def test_translate_mapping_and_limits(calls):
    api = api_with({"/translate": {"request_id": "r", "translated_text": "The accused was arrested on 20.08.2024", "source_language_code": "hi-IN"}}, calls)
    res = api.translate("अभियुक्त को 20.08.2024 को गिरफ्तार किया गया", "hi", "en")
    body = json.loads(calls[0].content)
    assert body["source_language_code"] == "hi-IN" and body["target_language_code"] == "en-IN"
    assert body["model"] == "sarvam-translate:v1" and body["mode"] == "formal" and body["numerals_format"] == "international"
    assert res.text.startswith("The accused") and res.source_language_code == "hi-IN"
    assert json.loads(calls[0].content)["input"].startswith("अभियुक्त")
    assert api.translate_body("x", None, "hi")["source_language_code"] == "auto"
    with pytest.raises(ValueError, match="2000"):
        api.translate_body("x" * 2001, "en", "hi")
    with pytest.raises(ValueError, match="1000"):
        api.translate_body("x" * 1001, "en", "hi", model="mayura:v1")


def test_language_id_mapping(calls):
    api = api_with({"/text-lid": {"request_id": "r", "language_code": "hi-IN", "script_code": "Deva"}}, calls)
    res = api.identify_language("मैं ऑफिस जा रहा हूँ" * 100)
    assert (res.language_code, res.script_code) == ("hi-IN", "Deva")
    assert len(json.loads(calls[0].content)["input"]) == 1000  # the 1000 character limit


def test_transliterate_mapping(calls):
    api = api_with({"/transliterate": {"transliterated_text": "main office ja raha hun", "source_language_code": "hi-IN"}}, calls)
    assert api.transliterate("मैं ऑफिस जा रहा हूँ", "hi", "en", spoken_form=True) == "main office ja raha hun"
    assert json.loads(calls[0].content) == {"input": "मैं ऑफिस जा रहा हूँ", "source_language_code": "hi-IN", "target_language_code": "en-IN", "spoken_form": True}


def test_speech_to_text_is_multipart_with_model_and_mode(calls):
    api = api_with({"/speech-to-text": {"request_id": "r", "transcript": "arrested on twentieth August", "language_code": "en-IN"}}, calls)
    res = api.speech_to_text(wav_bytes(1), "dictation.wav")
    req = calls[0]
    assert req.headers["content-type"].startswith("multipart/form-data")
    raw = req.content
    for part in (b'name="model"', b"saaras:v4", b'name="mode"', b"codemix", b'filename="dictation.wav"'):
        assert part in raw
    assert res.transcript.startswith("arrested") and res.language_code == "en-IN"


def test_text_to_speech_joins_then_decodes_the_base64_chunks(calls):
    wav = wav_bytes(1)
    half = base64.b64encode(wav).decode()
    cut = len(half) // 2 // 4 * 4  # chunk boundaries on base64 quads: the API says join, then decode
    api = api_with({"/text-to-speech": {"request_id": "r", "audios": [half[:cut], half[cut:]]}}, calls)
    out = api.text_to_speech("The accused was arrested.", "en")
    body = json.loads(calls[0].content)
    assert body["language_code"] == "en-IN" and body["model"] == "bulbul:v4-flash" and body["speaker"] and body["text"].startswith("The accused")
    assert out.audio == wav


def test_vision_digitise_job_flow_and_download_without_the_key(calls):
    api = api_with(vision_table(calls), calls)
    res = api.digitise(PNG, "page.png", "image/png", language="hi")
    submit, *rest = calls
    assert submit.url.path == "/doc-ai/v1/job/digitise" and submit.headers["api-subscription-key"] == KEY
    assert b'name="language"' in submit.content and b"hi-IN" in submit.content and b'name="output_format"' in submit.content and b"\r\nmd\r\n" in submit.content
    assert [r.url.path for r in rest] == ["/doc-ai/v1/job/job1/status"] * 2 + ["/doc-ai/v1/job/job1/download-url", "/out.zip"]
    assert "api-subscription-key" not in rest[-1].headers  # the pre-signed storage URL never gets the key
    assert res.text.startswith("# Order") and res.files == ["document.md"] and res.success_ratio == 1.0 and res.job_id == "job1"


@pytest.mark.parametrize("final", ["failed", "rejected"])
def test_vision_failed_job_raises(calls, final):
    api = api_with(vision_table(calls, polls=(final,)), calls)
    with pytest.raises(SarvamError, match=final):
        api.digitise(PNG, "page.png", "image/png")


def test_vision_poll_timeout(calls):
    api = api_with(vision_table(calls, polls=("running",) * 1000), calls)
    api.cfg = {**api.cfg, "vision": {**api.cfg["vision"], "timeout_s": 5.0, "poll_interval_s": 2.0}}
    with pytest.raises(SarvamError, match="did not finish"):
        api.digitise(PNG, "page.png", "image/png")


def test_unpack_digitised_skips_metadata_and_strips_html():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("out.html", "<html><p>Hello</p><p>world</p></html>")
        z.writestr("metadata/page_001.json", "{}")
    text, files = unpack_digitised(buf.getvalue(), "html")
    assert text == "Hello world" and files == ["out.html"]
    assert unpack_digitised(b"plain text", "md") == ("plain text", [])
    assert to_bcp47("hi") == "hi-IN" and to_bcp47("ta-IN") == "ta-IN" and to_bcp47(None) is None


# ------------------------------------------------------------------------------------------------ adapters


def test_translator_goes_through_policy_then_translates_line_by_line(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "public")
    answers = iter(["First line", "Second line"])
    api = api_with({"/translate": lambda r: {"translated_text": next(answers), "source_language_code": "hi-IN"}}, calls)
    with public_scope():
        out = SarvamTranslator(api).translate("पहली पंक्ति\n\nदूसरी पंक्ति")
    assert out == "First line\n\nSecond line" and len(calls) == 2  # blank lines kept, no call for them


def test_translator_splits_lines_over_the_model_limit(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "public")
    api = api_with({"/translate": lambda r: {"translated_text": "x", "source_language_code": "hi-IN"}}, calls)
    long_line = ("यह एक वाक्य है। " * 400).strip()  # about 6000 characters
    with public_scope():
        SarvamTranslator(api).translate(long_line)
    sizes = [len(json.loads(c.content)["input"]) for c in calls]
    assert len(sizes) >= 3 and max(sizes) <= 2000


def test_translator_blocks_raw_text_before_any_request(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    api = api_with({"/translate": {"translated_text": "x"}}, calls)
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        with pytest.raises(PrivacyBoundaryError):
            SarvamTranslator(api).translate("The accused Rajesh Kumar said")
        SarvamTranslator(api).translate("The accused Accused-1 said")
    assert len(calls) == 1  # only the clean text was sent


def test_asr_needs_consent_and_splits_long_wav(monkeypatch, calls, tmp_path):
    monkeypatch.setenv("VS_SARVAM", "consented")
    audio = tmp_path / "dictation.wav"
    audio.write_bytes(wav_bytes(70))
    answers = iter(["one", "two", "three"])
    api = api_with({"/speech-to-text": lambda r: {"transcript": next(answers), "language_code": "hi-IN"}}, calls)
    with pytest.raises(SarvamPolicyError):
        SarvamAsr(api).transcribe(str(audio))
    assert calls == []
    log = consented_log()
    with sarvam_scope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log):
        assert SarvamAsr(api).transcribe(str(audio), "hi") == "one two three"
    assert len(calls) == 3  # 70 s split into 30 s clips (the sync API limit)
    assert [e.inputs.get("bytes") for e in log.read(CASE, kind=EventKind.TOOL_CALL)][0] == audio.stat().st_size


def test_vision_client_transcribe_and_ocr_mapping(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "consented")
    api = api_with(vision_table(calls), calls)
    client = SarvamVisionClient(api, SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log()))
    assert client.name == "sarvam-vision"
    assert client.transcribe_page(PNG, "hi").startswith("# Order")
    text, conf, boxes = client.ocr(PNG, "hin+eng")
    assert text.startswith("# Order") and conf == 1.0 and boxes == []
    assert b"filename=\"page.png\"" in calls[0].content


def test_vision_client_refuses_without_consent_and_sends_nothing(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "consented")
    client = SarvamVisionClient(api_with(vision_table(calls), calls), SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log(None)))
    with pytest.raises(SarvamPolicyError):
        client.transcribe_page(PNG)
    assert calls == []


def test_llm_client_chat_boundary_usage_and_structured(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    api = api_with({"/v1/chat/completions": lambda r: chat_reply('{"label": "bail"}', 20, 5)}, calls)
    llm = SarvamLLMClient(api=api, where="ada", role="agents_14b")
    assert isinstance(llm, LLMClient) and llm.model_id == "sarvam-105b" and llm.where == "ada"
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        out = llm.structured("Classify: " + CLEAN, {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]})
        assert out == {"label": "bail"}
        assert llm.usage.prompt_tokens == 20 and llm.usage.completion_tokens == 5
        with pytest.raises(PrivacyBoundaryError):
            llm.chat([{"role": "user", "content": RAW_NAME}])
    assert all("Rajesh" not in c.content.decode() for c in calls)


def test_llm_client_public_class_may_name_judges_but_needs_public_mode(monkeypatch, calls):
    api = api_with({"/v1/chat/completions": chat_reply("{}")}, calls)
    llm = SarvamLLMClient(api=api, data=DataClass.PUBLIC, where="api")
    with pytest.raises(SarvamPolicyError, match="off"):
        llm.chat([{"role": "user", "content": "Shri Rajesh Kumar J. held that bail is the rule."}])
    monkeypatch.setenv("VS_SARVAM", "public")
    assert llm.chat([{"role": "user", "content": "Shri Rajesh Kumar J. held that bail is the rule."}]) == "{}"


def test_tts_only_inside_public_scope_for_constructed_text(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "public")
    api = api_with({"/text-to-speech": {"audios": [base64.b64encode(b"RIFFxxxx").decode()]}}, calls)
    tts = SarvamTts(api)
    with pytest.raises(SarvamPolicyError):  # the default scope is raw client data
        tts.synthesize("The accused was arrested on 20.08.2024")
    with public_scope("T8 synthetic dictation"):
        assert tts.synthesize("The accused was arrested on 20.08.2024") == b"RIFFxxxx"


def test_langid_script_labels(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "public")
    answers = iter([("hi-IN", "Deva"), ("en-IN", "Latn"), ("ta-IN", "Taml")])
    api = api_with({"/text-lid": lambda r: dict(zip(("language_code", "script_code"), next(answers), strict=True))}, calls)
    lid = SarvamLangId(api)
    with public_scope():
        assert lid.script("x") == "devanagari" and lid.script("x") == "latin" and lid.script("x") is None


# ------------------------------------------------------------------------------------------------ fallback and factory


class LocalVision:
    name = "local-vlm"

    def transcribe_page(self, image, lang_hint=None):
        return "local transcript"


def test_fallback_uses_local_when_policy_blocks_and_names_the_engine(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "consented")
    sarvam = SarvamVisionClient(api_with(vision_table(calls), calls), SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log(None)))
    fb = FallbackVision(sarvam, LocalVision)
    assert fb.name == "sarvam-vision"
    assert fb.transcribe_page(PNG) == "local transcript" and fb.name == "local-vlm"
    assert calls == [] and "SarvamPolicyError" in (fb.last_error or "")


def test_fallback_uses_sarvam_when_allowed(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "consented")
    sarvam = SarvamVisionClient(api_with(vision_table(calls), calls), SarvamScope(DataClass.CLIENT_RAW, case_id=CASE, event_log=consented_log()))
    fb = FallbackVision(sarvam, LocalVision)
    assert fb.transcribe_page(PNG).startswith("# Order") and fb.name == "sarvam-vision" and fb.last_error is None


def test_fallback_on_api_failure_and_boundary_failure(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")

    class Local:
        name = "indictrans2"
        is_identity = False

        def translate(self, text, src="hi", tgt="en"):
            return "local:" + text

    down = SarvamApi(make_http(lambda r: json_response({"error": {"code": "x"}}, 500), max_retries=1))
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        fb = FallbackTranslator(SarvamTranslator(down), Local)
        assert fb.translate("Accused-1 बोला") == "local:Accused-1 बोला" and fb.name == "indictrans2"
        fb2 = FallbackTranslator(SarvamTranslator(down), Local)
        assert fb2.translate("accused Rajesh Kumar बोला").startswith("local:")  # boundary failure: local answers, nothing sent


def test_fallback_llm_delegates_and_mirrors_usage(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    from vakeel_sahayak.models.offline_llm import OfflineLLM

    primary = SarvamLLMClient(api=api_with({"/v1/chat/completions": chat_reply("from sarvam", 7, 2)}, calls), where="ada")
    fb = FallbackLLM(primary, lambda: OfflineLLM(role="agents_14b", where="ada"), "ada")
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        done = fb.complete(CLEAN)
        assert done.text == "from sarvam" and (done.prompt_tokens, done.completion_tokens) == (7, 2) and fb.name == "sarvam"
        fb.generate(RAW_NAME)
        assert fb.last_engine is fb.local and fb.where == "ada"


def test_factory_returns_exactly_the_local_clients_while_sarvam_is_off(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", KEY)  # a key alone changes nothing
    from vakeel_sahayak.models.offline import GlossaryTranslator, OfflineAsrClient, OfflineVisionClient

    assert type(factory.get_vision()) is OfflineVisionClient
    assert type(factory.get_asr()) is OfflineAsrClient
    assert type(factory.get_translator()) is GlossaryTranslator
    assert factory.get_langid() is None
    with pytest.raises(ModelUnavailable):
        factory.get_tts()


def test_factory_stays_local_without_a_key_or_when_forced_offline(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "consented")
    from vakeel_sahayak.models.offline import GlossaryTranslator

    assert type(factory.get_translator()) is GlossaryTranslator  # no key
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    monkeypatch.setenv("VS_MODELS", "offline")
    factory.reset_clients()
    assert type(factory.get_translator()) is GlossaryTranslator and factory.get_langid() is None
    with pytest.raises(ModelUnavailable):
        factory.get_tts()


def test_factory_wraps_sarvam_when_active_and_respects_per_capability_switch(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "public")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    use_mock_server(monkeypatch, {"/translate": {"translated_text": "The accused was arrested on 20.08.2024", "source_language_code": "hi-IN"}}, calls)
    tr = factory.get_translator()
    assert isinstance(tr, FallbackTranslator)
    with public_scope():
        assert tr.translate("अभियुक्त को गिरफ्तार किया गया") .startswith("The accused") and tr.name == "sarvam-translate"
    assert calls[0].headers["api-subscription-key"] == KEY
    # no scope: the default is raw client data, so the same client answers locally and sends nothing
    n = len(calls)
    tr.translate("अभियुक्त")
    assert len(calls) == n and tr.name != "sarvam-translate"
    assert isinstance(factory.get_vision(), FallbackVision) and factory.get_langid() is not None and factory.get_tts() is not None
    from vakeel_sahayak.models.sarvam import config as cfg_mod

    monkeypatch.setattr(cfg_mod, "sarvam_config", lambda: {**cfg_mod.DEFAULTS, "use": {**cfg_mod.DEFAULTS["use"], "vision": False}})
    assert not isinstance(factory.get_vision(), FallbackVision)


def test_get_ocr_uses_sarvam_only_when_use_for_ocr_is_on(monkeypatch):
    monkeypatch.setenv("VS_SARVAM", "consented")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    from vakeel_sahayak.models.sarvam import config as cfg_mod
    from vakeel_sahayak.models.sarvam.fallback import FallbackOcr

    assert not isinstance(factory.get_ocr(), FallbackOcr)
    monkeypatch.setattr(cfg_mod, "sarvam_config", lambda: {**cfg_mod.DEFAULTS, "vision": {**cfg_mod.DEFAULTS["vision"], "use_for_ocr": True}})
    assert isinstance(factory.get_ocr(), FallbackOcr)


def _role_cfg(monkeypatch, role="agents_14b", **extra):
    real = factory.role_config
    monkeypatch.setattr(factory, "role_config", lambda r: {**real(r), **({"runtime": "sarvam", **extra} if r == role else {})})


def test_agent_role_configured_sarvam_falls_back_while_off(monkeypatch):
    from vakeel_sahayak.models.vllm_client import VllmClient

    _role_cfg(monkeypatch)
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)  # off: the Qwen/vLLM role as before
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    assert isinstance(factory.get_llm("agents_14b"), VllmClient)  # no key either


def test_agent_role_configured_sarvam_is_wrapped_ada_side_and_pseudonymised_only(monkeypatch, calls):
    _role_cfg(monkeypatch)
    monkeypatch.setenv("VS_SARVAM", "pseudonymised")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    use_mock_server(monkeypatch, {"/v1/chat/completions": chat_reply("hi")}, calls)
    llm = factory.get_llm("agents_14b")
    assert isinstance(llm, FallbackLLM) and llm.where == "ada" and isinstance(llm.primary, SarvamLLMClient)
    assert llm.primary.data is DataClass.CLIENT_TEXT
    with sarvam_scope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=EventLog()):
        assert llm.chat([{"role": "user", "content": CLEAN}]) == "hi"
    assert len(calls) == 1
    monkeypatch.setenv("VS_MODELS", "offline")
    assert factory.get_llm("agents_14b").is_offline  # offline still forces the deterministic client


def test_eval_labeler_sarvam_option_is_non_qwen_public_only_and_off_by_default(monkeypatch, calls):
    from vakeel_sahayak.models.base import LabelerUnavailable
    from vakeel_sahayak.models.labeler import EvalLabeler

    assert model_family("sarvam-105b") == "sarvam"
    monkeypatch.setenv("VS_LABELER", "sarvam")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    lab = EvalLabeler()
    client = lab.client()
    assert isinstance(client, SarvamLLMClient) and client.data is DataClass.PUBLIC and client.model_id == "sarvam-105b"
    with pytest.raises(LabelerUnavailable):  # Sarvam off: gold falls back to rule-only records, never a silent stand-in
        lab.label("The court granted bail.", ["bail_granted"])
    monkeypatch.setenv("VS_SARVAM", "public")
    use_mock_server(monkeypatch, {"/v1/chat/completions": chat_reply('{"labels": ["bail_granted"]}')}, calls)
    assert EvalLabeler().label("The court granted bail.", ["bail_granted", "bail_denied"]) == ["bail_granted"]
    assert json.loads(calls[0].content)["model"] == "sarvam-105b"
    with pytest.raises(ValueError, match="Qwen"):
        EvalLabeler(model="Qwen/Qwen3-32B").client()
    monkeypatch.delenv("VS_LABELER")
    assert not EvalLabeler()._use_sarvam()


def test_teacher_sarvam_backend_differs_in_family_from_the_labeler(monkeypatch):
    from vakeel_sahayak.models.teacher import TeacherClient, assert_families_differ

    t = TeacherClient(backend="sarvam")
    assert (t.where, t.model_id, t.is_offline) == ("api", "sarvam-105b", False)
    assert isinstance(t.client, SarvamLLMClient) and t.client.data is DataClass.PUBLIC
    assert_families_differ(t.model_id, "meta-llama/Llama-3.1-8B-Instruct")
    monkeypatch.setenv("VS_TEACHER", "sarvam")
    assert TeacherClient().backend == "sarvam"
    with pytest.raises(SarvamPolicyError):  # off: nothing is sent
        t.generate("x")


def test_detect_script_with_lid_only_asks_sarvam_for_mixed_text(monkeypatch, calls):
    from vakeel_sahayak.ingestion.hindi import detect_script, detect_script_with_lid

    mixed = "आरोपी को गिरफ्तार किया गया। The accused was arrested by the police on 20 August."
    assert detect_script(mixed) == "mixed"
    assert detect_script_with_lid(mixed) == "mixed"  # Sarvam off: the local label
    monkeypatch.setenv("VS_SARVAM", "public")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    use_mock_server(monkeypatch, {"/text-lid": {"language_code": "en-IN", "script_code": "Latn"}}, calls)
    with public_scope():
        assert detect_script_with_lid(mixed) == "latin"
        assert detect_script_with_lid("The accused was arrested.") == "latin"
        assert detect_script_with_lid("आरोपी को गिरफ्तार किया गया।") == "devanagari"
    assert len(calls) == 1  # clear text never leaves the machine
    calls.clear()
    assert detect_script_with_lid(mixed) == "mixed"  # default scope is raw client data: blocked, local answer
    assert calls == []


def test_the_api_key_never_reaches_events_across_a_consented_run(monkeypatch, calls):
    monkeypatch.setenv("VS_SARVAM", "consented")
    monkeypatch.setenv("SARVAM_API_KEY", KEY)
    use_mock_server(monkeypatch, vision_table(calls), calls)
    log = consented_log()
    with sarvam_scope(DataClass.CLIENT_RAW, case_id=CASE, event_log=log):
        assert factory.get_vision().transcribe_page(PNG, "hi").startswith("# Order")
    dumped = json.dumps([e.model_dump(mode="json") for e in log.read(CASE)])
    assert KEY not in dumped and "sarvam.vision" in dumped
