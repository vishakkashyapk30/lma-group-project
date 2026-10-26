"""The SSE stream over the real SQLite record (plan §3.3 use 4, §13.1) never blocks the server.

`EventLog.subscribe` sleeps between polls; iterated inside the async SSE route it froze every other request of the API as soon as a browser
opened a case. The route now follows the record with `EventLog.follow` (database reads in a worker thread, waits with asyncio.sleep).
These tests use a real `EventLog` and drive `api.sse.event_stream` directly, because a TestClient cannot read a stream that never ends.
"""

from __future__ import annotations

import asyncio
import json

from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

CASE = "case-0007"


def note(text: str, case_id: str = CASE) -> Event:
    return Event(event_id="", ts="", case_id=case_id, kind=EventKind.USER_ACTION, actor=COUNSEL, inputs={"note": text}, outputs={})


def wired_log(tmp_path, monkeypatch) -> EventLog:
    log = EventLog(str(tmp_path / "record.sqlite"))
    patch_everywhere(monkeypatch, "vakeel_sahayak.api.deps", "get_event_log", lambda case_id=None: log)
    return log


def frame_note(frame: str) -> str:
    data = next(line for line in frame.splitlines() if line.startswith("data: "))[len("data: "):]
    return json.loads(data)["inputs"]["note"]


def test_replays_stored_events_then_follows_live_ones_without_blocking(tmp_path, monkeypatch):
    log = wired_log(tmp_path, monkeypatch)
    log.append(note("one"))
    log.append(note("two"))
    log.append(note("other case", case_id="case-0008"))

    async def run() -> tuple[list[str], int]:
        from vakeel_sahayak.api.sse import event_stream

        ticks = 0

        async def ticker() -> None:  # other work on the event loop must keep running while the stream waits
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        async def later() -> None:
            await asyncio.sleep(0.4)
            await asyncio.to_thread(log.append, note("three"))

        stream = event_stream(CASE, None)
        tick_task, add_task = asyncio.create_task(ticker()), asyncio.create_task(later())
        got = [frame_note(await asyncio.wait_for(stream.__anext__(), timeout=5)) for _ in range(3)]
        tick_task.cancel()
        await add_task
        await stream.aclose()
        return got, ticks

    got, ticks = asyncio.run(run())
    assert got == ["one", "two", "three"]  # stored events in order, then the live one; never another case's events
    assert ticks >= 10, f"the event loop was blocked while the stream waited ({ticks} ticks in about 0.4 s)"


def test_resumes_after_the_last_event_id(tmp_path, monkeypatch):
    log = wired_log(tmp_path, monkeypatch)
    first = log.append(note("one"))
    log.append(note("two"))

    async def run() -> str:
        from vakeel_sahayak.api.sse import event_stream

        stream = event_stream(CASE, first.event_id)
        frame = await asyncio.wait_for(stream.__anext__(), timeout=5)
        await stream.aclose()
        return frame_note(frame)

    assert asyncio.run(run()) == "two"
