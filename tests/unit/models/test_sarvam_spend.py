"""Sarvam spend ledger: hard cap, worst-case reservation, cache hits cost nothing, price lookup, env overrides (offline, no network)."""

from __future__ import annotations

import json

import httpx
import pytest

from vakeel_sahayak.models.openai.ledger import ResponseCache
from vakeel_sahayak.models.sarvam import SarvamBudgetExceeded, SarvamError
from vakeel_sahayak.models.sarvam import spend as sp
from vakeel_sahayak.models.sarvam.api import AsyncSarvamApi, SarvamApi
from vakeel_sahayak.models.sarvam.errors import BudgetExhausted
from vakeel_sahayak.models.sarvam.fallback import FALLBACK_ERRORS
from vakeel_sahayak.models.sarvam.http import SarvamHttp

# RECONCILED: paid providers are locked by default since the owner decision of 2026-10-28 (models/paid_lock.py); these tests exercise the
# mocked OpenAI/Sarvam paths, so they run with the providers unlocked. The lock itself is tested in tests/unit/models/test_paid_lock.py.
pytestmark = pytest.mark.usefixtures("paid_unlocked")


MSG = [{"role": "user", "content": "x" * 400}]


def chat_json(pt=100, ct=20, text="ok"):
    return {"model": "sarvam-105b", "choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"prompt_tokens": pt, "completion_tokens": ct}}


def make_api(tmp_path, cap, calls, *, run_cap=None, body=None):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json=body or chat_json())

    http = SarvamHttp("k", transport=httpx.MockTransport(handler), async_transport=httpx.MockTransport(handler))
    ledger = sp.SarvamLedger(tmp_path / "l.sqlite", cap_inr=cap, run_cap_inr=run_cap, run_id="t")
    meter = sp.Meter(ledger, ResponseCache(tmp_path / "c.sqlite"))
    return SarvamApi(http, meter=meter), ledger


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for v in (sp.CAP_ENV, sp.RUN_CAP_ENV, sp.NO_CACHE_ENV, sp.RUN_ID_ENV):
        monkeypatch.delenv(v, raising=False)


def test_price_lookup_table_from_dashboard():
    p = sp.price_of("sarvam-105b")
    assert (float(p.input), float(p.cached_input), float(p.output)) == (15, 5, 60)
    assert float(sp.price_of("MiMo-V2.6-Flash").output) == 25
    assert float(sp.price_of("mimo-v2.6-pro").input) == 40
    assert float(sp.price_of("deepseek-v4.1-flash").output) == 105
    assert float(sp.price_of("glm-5.3-flash").cached_input) == 2.5
    assert float(sp.price_of("gemma-4").output) == 90
    assert sp.price_of("no-such-model") is None


def test_cost_arithmetic_rounds_up_and_micro_units():
    p = sp.price_of("sarvam-105b")
    # 1M input tokens at INR 15 = INR 15 = 15e6 micro-INR; cached cheaper
    assert sp.cost_micro(p, 1_000_000, 0, 0) == 15_000_000
    assert sp.cost_micro(p, 1_000_000, 1_000_000, 0) == 5_000_000
    assert sp.cost_micro(p, 1, 0, 1) == 75
    assert sp.char_cost_micro(sp.char_price("translate"), 10_000) == 20_000_000


def test_cap_env_override_and_default(monkeypatch):
    assert sp.effective_cap_inr() == 25.0  # configs/eval/runs.yaml budgets.sarvam_cap_inr
    monkeypatch.setenv(sp.CAP_ENV, "100")
    assert sp.effective_cap_inr() == 100.0
    monkeypatch.setenv(sp.CAP_ENV, "junk")
    assert sp.effective_cap_inr() == 25.0
    monkeypatch.setenv(sp.CAP_ENV, "10")
    monkeypatch.setenv(sp.RUN_CAP_ENV, "50")
    assert sp.effective_run_cap_inr() == 10.0  # never above the total cap
    monkeypatch.setenv(sp.RUN_CAP_ENV, "3")
    assert sp.SarvamLedger(run_id="r").run_cap_micro == 3_000_000


def test_reservation_refuses_before_any_request(tmp_path):
    calls: list = []
    api, ledger = make_api(tmp_path, 0.0001, calls)
    with pytest.raises(SarvamBudgetExceeded) as e:
        api.chat(MSG, max_tokens=1000)
    assert calls == []  # nothing was sent
    assert e.value.scope == "total" and e.value.needed_micro > e.value.cap_micro
    assert isinstance(e.value, SarvamError) and isinstance(e.value, FALLBACK_ERRORS) and BudgetExhausted is SarvamBudgetExceeded
    assert ledger.spent_micro() == 0


def test_settle_replaces_reservation_by_real_cost(tmp_path):
    calls: list = []
    api, ledger = make_api(tmp_path, 25, calls)
    out = api.chat(MSG, max_tokens=512, purpose="t", case_id="c1")
    assert out.text == "ok" and len(calls) == 1
    assert ledger.spent_micro() == 100 * 15 + 20 * 60  # prompt 100 x 15 + completion 20 x 60 micro-INR
    rep = ledger.report()
    assert rep["calls"] == 1 and rep["in_flight"] == 0 and rep["by_purpose_inr"]["t"] == pytest.approx(0.0027)


def test_cap_exhausted_after_spending_refuses_next(tmp_path):
    calls: list = []
    worst = sp.worst_case_micro(sp.price_of("sarvam-105b"), MSG, 512)
    api, ledger = make_api(tmp_path, (worst + worst // 2) / 1e6, calls)
    api.chat(MSG, max_tokens=512, temperature=0.7)  # temperature > 0: not cached; settles far below its worst case
    api.chat(MSG, max_tokens=512, temperature=0.7)
    with pytest.raises(SarvamBudgetExceeded):
        api.chat([{"role": "user", "content": "y" * 400}], max_tokens=100000, temperature=0.7)
    assert len(calls) == 2


def test_held_reservation_counts_against_cap(tmp_path):
    ledger = sp.SarvamLedger(tmp_path / "l.sqlite", cap_inr=0.01, run_id="t")
    r = ledger.reserve("m", 6000, "a")
    assert ledger.spent_micro() == 6000
    with pytest.raises(SarvamBudgetExceeded):
        ledger.reserve("m", 6000, "b")
    ledger.release(r)
    assert ledger.spent_micro() == 0
    ledger.reserve("m", 6000, "b")  # fits again once released
    ledger.mark_unknown(ledger.reserve("m", 3000))
    assert ledger.spent_micro() == 9000  # an unknown outcome keeps its worst case


def test_run_cap(tmp_path):
    calls: list = []
    api, ledger = make_api(tmp_path, 25, calls, run_cap=0.0001)
    with pytest.raises(SarvamBudgetExceeded) as e:
        api.chat(MSG, max_tokens=1000)
    assert e.value.scope == "run" and calls == []


def test_cache_hit_costs_nothing_and_sends_nothing(tmp_path):
    calls: list = []
    api, ledger = make_api(tmp_path, 25, calls)
    a = api.chat(MSG, max_tokens=512, temperature=0.0)
    spent = ledger.spent_micro()
    b = api.chat(MSG, max_tokens=512, temperature=0.0)
    assert b.text == a.text == "ok" and len(calls) == 1 and ledger.spent_micro() == spent
    assert ledger.report()["cache_hits"] == 1
    api.chat(MSG, max_tokens=512, temperature=0.5)  # temperature > 0 is never cached
    assert len(calls) == 2


def test_cache_off_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv(sp.NO_CACHE_ENV, "1")
    calls: list = []
    api, ledger = make_api(tmp_path, 25, calls)
    api.chat(MSG, max_tokens=64)
    api.chat(MSG, max_tokens=64)
    assert len(calls) == 2


def test_unpriced_model_refused(tmp_path):
    calls: list = []
    api, _ = make_api(tmp_path, 25, calls)
    with pytest.raises(SarvamError):
        api.chat(MSG, model="mystery-model")
    assert calls == []


def test_http_error_releases_reservation(tmp_path):
    http = SarvamHttp("k", transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"code": "invalid_request_error", "message": "bad"}})))
    ledger = sp.SarvamLedger(tmp_path / "l.sqlite", cap_inr=25, run_id="t")
    api = SarvamApi(http, meter=sp.Meter(ledger, ResponseCache(tmp_path / "c.sqlite")))
    with pytest.raises(SarvamError):
        api.chat(MSG)
    assert ledger.spent_micro() == 0 and ledger.report()["released"] == 1


def test_character_priced_endpoints_share_the_ledger(tmp_path):
    calls: list = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={"translated_text": "t", "language_code": "hi-IN", "script_code": "Deva"})

    ledger = sp.SarvamLedger(tmp_path / "l.sqlite", cap_inr=25, run_id="t")
    api = SarvamApi(SarvamHttp("k", transport=httpx.MockTransport(handler)), meter=sp.Meter(ledger, ResponseCache(tmp_path / "c.sqlite")))
    api.translate("a" * 1000, "hi", "en")
    assert ledger.spent_micro() == 2_000_000  # 1000 chars at INR 20 per 10k
    api.identify_language("b" * 100)
    assert ledger.report()["by_kind_inr"]["language_id"] == pytest.approx(0.035)
    tiny = SarvamApi(SarvamHttp("k", transport=httpx.MockTransport(handler)), meter=sp.Meter(sp.SarvamLedger(tmp_path / "l2.sqlite", cap_inr=0.01, run_id="t"), ResponseCache(tmp_path / "c.sqlite")))
    with pytest.raises(SarvamBudgetExceeded):
        tiny.translate("a" * 1000, "hi", "en")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_async_chat_is_metered_and_cached(tmp_path):
    pytest.importorskip("pytest_asyncio")
    calls: list = []
    sync, ledger = make_api(tmp_path, 25, calls)
    api = AsyncSarvamApi(sync.http, meter=sync.meter)
    a = await api.chat(MSG, max_tokens=64)
    b = await api.chat(MSG, max_tokens=64)
    assert a.text == b.text and len(calls) == 1 and ledger.report()["cache_hits"] == 1
    tight = AsyncSarvamApi(sync.http, meter=sp.Meter(sp.SarvamLedger(tmp_path / "x.sqlite", cap_inr=0.00001, run_id="t"), sync.meter.cache))
    with pytest.raises(SarvamBudgetExceeded):
        await tight.chat([{"role": "user", "content": "new text"}], max_tokens=64)


def test_cli_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    assert sp.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["cap_inr"] == 25.0
    assert sp.main([]) == 0
    assert "Sarvam spend" in capsys.readouterr().out
