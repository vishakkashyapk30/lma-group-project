"""Router `events` and `sse` (plan §13.1, §3.3 use 4): agent events streamed to the UI as Server-Sent Events, feeding the live
trace and the agent animations.

ASSUMPTIONS (the plan names SSE, not the frame layout): one frame per event, `id:` the event id, `event:` the EventKind
value, `data:` the event as JSON; a request with `Last-Event-ID` resumes after that event; the stream replays the stored events of
the case, then follows `EventLog.subscribe`. A real subscription never ends, so the tests use `FiniteLog` (see `_helpers.py`).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from tests.unit.api._helpers import CASE, FiniteLog, make_events, sse_frames
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.schemas.enums import EventKind


@pytest.fixture()
def finite(monkeypatch):
    """A FiniteLog wired in as the event log of every case (dependency override and module aliases)."""
    log = FiniteLog()
    for e in make_events(5):
        log.append(e)
    log.live = make_events(7)[5:]
    patch_everywhere(monkeypatch, "vakeel_sahayak.api.deps", "get_event_log", lambda case_id=None: log)
    return log


def client_for(log):
    from fastapi.testclient import TestClient

    from vakeel_sahayak.api import deps
    from vakeel_sahayak.api.app import create_app

    app = create_app()
    app.dependency_overrides[deps.get_event_log] = lambda case_id=None: log
    return TestClient(app)


def test_stream_has_the_event_stream_content_type(finite):
    res = client_for(finite).get(f"/api/cases/{CASE}/events")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in res.headers.get("cache-control", "")


def test_frames_replay_then_follow_in_order(finite):
    """Five stored events are replayed in order, then the two live ones follow: seven frames, ids ev0001..ev0007."""
    frames = sse_frames(client_for(finite).get(f"/api/cases/{CASE}/events").text)
    assert [f["id"] for f in frames] == [f"ev{i:04d}" for i in range(1, 8)]


def test_frame_carries_the_kind_and_the_event_json(finite):
    frames = sse_frames(client_for(finite).get(f"/api/cases/{CASE}/events").text)
    first = frames[0]
    assert first["event"] == EventKind.TOOL_CALL.value
    data = json.loads(first["data"])
    assert data["event_id"] == "ev0001" and data["case_id"] == CASE and data["tool"] == "inspect_page"


def test_last_event_id_resumes_after_that_event(finite):
    """A reconnecting browser sends Last-Event-ID: only newer events come back, none twice."""
    res = client_for(finite).get(f"/api/cases/{CASE}/events", headers={"Last-Event-ID": "ev0004"})
    assert [f["id"] for f in sse_frames(res.text)] == ["ev0005", "ev0006", "ev0007"]


def test_other_cases_events_are_not_streamed(finite):
    for e in make_events(3, case_id="case-0008"):
        finite.append(e.model_copy(update={"event_id": f"x{e.event_id}"}))
    frames = sse_frames(client_for(finite).get(f"/api/cases/{CASE}/events").text)
    assert all(json.loads(f["data"])["case_id"] == CASE for f in frames)


# ---- the async generator itself ----------------------------------------------------------------------------------
async def collect(agen, n: int, timeout: float = 2.0) -> list[str]:
    out: list[str] = []
    for _ in range(n):
        out.append(await asyncio.wait_for(agen.__anext__(), timeout))
    await agen.aclose()
    return out


async def test_event_stream_yields_sse_formatted_chunks(finite):
    from vakeel_sahayak.api.sse import event_stream

    chunks = await collect(event_stream(CASE), 3)
    frames = sse_frames("".join(chunks))
    assert [f["id"] for f in frames] == ["ev0001", "ev0002", "ev0003"]
    assert all(c.endswith("\n\n") for c in chunks)


async def test_event_stream_resumes_after_last_event_id(finite):
    from vakeel_sahayak.api.sse import event_stream

    chunks = await collect(event_stream(CASE, last_event_id="ev0006"), 1)
    assert sse_frames(chunks[0])[0]["id"] == "ev0007"
