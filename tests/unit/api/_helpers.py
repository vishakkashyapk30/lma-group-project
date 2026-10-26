"""Helpers for the API router tests (plan §13.1, §13.5; FastAPI TestClient, no network, no GPU).

The wiring is the one of `tests/system/_helpers.Scenario` (the single place that knows how the API finds its log, stores,
model clients and tools); this module adds JSON builders and a terminating event log for the SSE tests.

ASSUMPTIONS shared by the router tests (the plan fixes behaviour, not HTTP codes or JSON keys):
* unknown case: 404; a request body that fails validation: 422; export before Gate 2: 403 (the router docstring);
  approving a gate whose checklist is not cleared, or drafting before Gate 1: 409; an unsupported media type: 415;
* a case exists as soon as its record (event log) has events; new case ids look like `case-0001`;
* a paths below `$VS_DATA_DIR/cases/<case_id>/` are the laptop-only store of raw files.
"""

from __future__ import annotations

import json
from typing import Any

from tests.fakes.log import InMemoryEventLog
from tests.system import _helpers as sh
from vakeel_sahayak.schemas.enums import EventKind, GateId, RightsCheckName, RightsStatus
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport

CASE = sh.CASE_ID
G1, G2 = GateId.GATE_1_DOSSIER.value, GateId.GATE_2_EXPORT.value
NOT_FOUND, INVALID, CHECKLIST_OPEN, EXPORT_REFUSED, UNSUPPORTED_MEDIA = 404, 422, sh.HTTP_CHECKLIST_OPEN, sh.HTTP_EXPORT_REFUSED, 415

PDF_BYTES = b"%PDF-1.4\n% stub\n"


def scenario(tmp_path, monkeypatch, **kw) -> sh.Scenario:
    """A wired scenario; build it inside the test body so an unimplemented module fails the test, not a fixture."""
    return sh.Scenario(tmp_path, monkeypatch, **kw)


def urgent_rights(case_id: str = CASE) -> RightsReport:
    """A radar with an urgent chip first-in-importance: the default-bail window opens in 6 days (plan §13.4 chip text)."""
    return RightsReport(case_id=case_id, as_of=sh.AS_OF, checks=[
        RightsCheckResult(check=RightsCheckName.UNDERTRIAL_LIMIT, status=RightsStatus.CHECK,
                          detail="167 days in custody. Antecedents unknown.", rule="BNSS s.479"),
        RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.NOT_YET,
                          detail="Default-bail window opens in 6 days (BNSS s.187(3)).", rule="BNSS s.187(3)"),
    ])


class FiniteLog(InMemoryEventLog):
    """An event log whose `subscribe` ends after the `live` events (a real subscription never ends, and TestClient cannot
    stream forever). ASSUMPTION: the SSE route replays `read(case_id)` events after `Last-Event-ID`, then yields `subscribe`."""

    def __init__(self) -> None:
        super().__init__()
        self.live: list[Event] = []

    def subscribe(self, case_id: str):
        yield from [e for e in self.live if e.case_id == case_id]


def sse_frames(body: str) -> list[dict[str, str]]:
    """Parse a text/event-stream body into frames {id, event, data}."""
    frames = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        frame: dict[str, str] = {}
        for line in block.split("\n"):
            if line.startswith(":") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            frame[key.strip()] = value.strip()
        frames.append(frame)
    return frames


def make_events(n: int, case_id: str = CASE) -> list[Event]:
    # RECONCILED: cycle from (i-1) so the first event (ev0001) is a TOOL_CALL, as test_frame_carries_the_kind_and_the_event_json expects.
    kinds = [EventKind.TOOL_CALL, EventKind.TOOL_RESULT, EventKind.STORE_WRITE, EventKind.AGENT_MESSAGE]
    return [Event(event_id=f"ev{i:04d}", case_id=case_id, ts=f"2025-02-03T09:{i:02d}:00Z", kind=kinds[(i - 1) % 4], actor="MUNSHI",
                  tool="inspect_page" if (i - 1) % 4 < 2 else None, inputs={"page": i}) for i in range(1, n + 1)]


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)
