"""record/event_log.EventLog: append-only SQLite event log (plan §3.3).

Every agent action is an Event (who, tool, inputs, outputs, sources, time). The log assigns id and time when missing,
returns events in append order, filters by kind/actor/since, walks causal children via parent_id (used by truth
maintenance, plan §10), is append-only, persists across instances, and feeds a live subscription (the agent trace).
(That logs hold pseudonymised text only, plan §16, is a caller obligation and is not enforceable here.)
"""

from __future__ import annotations

import queue
import threading
from datetime import datetime


from tests.unit.record._helpers import make_event
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import Event

CASE = "case-0007"


# ---------------------------------------------------------------------------------------------------------------------
# surface checks (pass today)
# ---------------------------------------------------------------------------------------------------------------------
def test_event_log_is_append_only_by_construction():
    """No public method updates, deletes or rewrites events (plan §3.3 audit trail)."""
    forbidden = ("update", "delete", "remove", "clear", "drop", "truncate", "edit", "set", "overwrite", "rewrite", "replace", "pop")
    public = [n for n in dir(EventLog) if not n.startswith("_")]
    assert {"append", "read", "children", "subscribe"} <= set(public)
    assert not [n for n in public if n.startswith(forbidden)]


def test_event_schema_matches_plan_fields():
    """An Event carries who, tool, inputs, outputs, sources, time and a causal parent (plan §3.3)."""
    assert set(Event.model_fields) == {
        "event_id", "case_id", "ts", "kind", "actor", "tool", "inputs", "outputs", "sources", "parent_id"
    }


# ---------------------------------------------------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------------------------------------------------
def test_append_assigns_event_id_and_ts_when_missing(new_log):
    """An event appended with empty id and time is stored with a non-empty id and an ISO-8601 UTC time."""
    event_log = new_log()
    stored = event_log.append(make_event(CASE))
    assert stored.event_id
    assert stored.ts
    datetime.fromisoformat(stored.ts.replace("Z", "+00:00"))
    assert [e.event_id for e in event_log.read(CASE)] == [stored.event_id]


def test_append_assigns_distinct_ids(new_log):
    """Two appended events never share an assigned id."""
    event_log = new_log()
    ids = {event_log.append(make_event(CASE)).event_id for _ in range(20)}
    assert len(ids) == 20


def test_append_keeps_given_id_and_ts(new_log):
    """Explicit event_id and ts are preserved verbatim."""
    event_log = new_log()
    stored = event_log.append(make_event(CASE, event_id="ev-fixed", ts="2025-02-03T09:01:00Z"))
    assert (stored.event_id, stored.ts) == ("ev-fixed", "2025-02-03T09:01:00Z")
    assert event_log.read(CASE)[0].event_id == "ev-fixed"


def test_append_returns_the_stored_event_with_payload_intact(new_log, sample_events):
    """The returned and the re-read event equal the input on every field except assigned ones."""
    event_log = new_log()
    src = sample_events[2]  # STORE_WRITE with nested outputs and a SourceRef
    stored = event_log.append(src)
    assert stored == src
    assert event_log.read(CASE)[0] == src
    assert event_log.read(CASE)[0].sources[0].quote == "...arrested on 20.08.2024..."


def test_enum_kind_and_agent_actor_survive_roundtrip(new_log):
    """kind comes back as an EventKind and an agent actor compares equal to its name."""
    event_log = new_log()
    event_log.append(make_event(CASE, EventKind.GATE_APPROVED, "counsel"))
    event_log.append(make_event(CASE, EventKind.TOOL_CALL, "MUNSHI"))
    kinds = [e.kind for e in event_log.read(CASE)]
    assert kinds == [EventKind.GATE_APPROVED, EventKind.TOOL_CALL]
    assert str(getattr(event_log.read(CASE)[1].actor, "value", event_log.read(CASE)[1].actor)) == "MUNSHI"


# ---------------------------------------------------------------------------------------------------------------------
# read
# ---------------------------------------------------------------------------------------------------------------------
def test_read_returns_events_in_append_order(new_log):
    """Events come back in the order they were appended, regardless of id values."""
    event_log = new_log()
    ids = ["zz-3", "aa-1", "mm-2"]  # not sorted: order must come from append order
    for i, eid in enumerate(ids):
        event_log.append(make_event(CASE, event_id=eid, ts=f"2025-02-03T09:0{i}:00Z"))
    assert [e.event_id for e in event_log.read(CASE)] == ids


def test_read_scopes_to_case(new_log):
    """read(case_id) returns only that case's events."""
    event_log = new_log()
    event_log.append(make_event("case-0007", event_id="a"))
    event_log.append(make_event("case-0008", event_id="b"))
    event_log.append(make_event("case-0007", event_id="c"))
    assert [e.event_id for e in event_log.read("case-0007")] == ["a", "c"]
    assert [e.event_id for e in event_log.read("case-0008")] == ["b"]
    assert event_log.read("case-9999") == []


def test_read_filters_by_kind(new_log, sample_events):
    """kind= keeps only that EventKind: case-0007 has 6 STORE_WRITE, 1 GATE_APPROVED and 1 BUDGET_HIT."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    assert len(event_log.read(CASE)) == 17
    assert [e.event_id for e in event_log.read(CASE, kind=EventKind.STORE_WRITE)] == [f"ev00{i}" for i in range(3, 9)]
    assert [e.event_id for e in event_log.read(CASE, kind=EventKind.GATE_APPROVED)] == ["ev011"]
    assert [e.event_id for e in event_log.read(CASE, kind=EventKind.BUDGET_HIT)] == ["ev014"]
    assert event_log.read(CASE, kind=EventKind.GATE_REJECTED) == []


def test_read_filters_by_actor(new_log, sample_events):
    """actor= matches the actor name: 'counsel' acted twice, SUTRADHAR four times."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    assert [e.event_id for e in event_log.read(CASE, actor="counsel")] == ["ev011", "ev015"]
    assert [e.event_id for e in event_log.read(CASE, actor="SUTRADHAR")] == ["ev012", "ev013", "ev014", "ev016"]
    assert event_log.read(CASE, actor="PAIROKAR") == []


def test_read_filters_by_since_inclusive(new_log, sample_events):
    """since= is an inclusive ISO time lower bound (ASSUMPTION: inclusive, as in the in-memory mirror)."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    got = [e.event_id for e in event_log.read(CASE, since="2025-02-03T09:15:00Z")]
    assert got == ["ev015", "ev016", "ev017"]
    assert event_log.read(CASE, since="2025-02-03T09:18:00Z") == []
    assert len(event_log.read(CASE, since="2025-02-03T00:00:00Z")) == 17


def test_read_filters_combine(new_log, sample_events):
    """kind, actor and since combine with AND."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    got = event_log.read(CASE, kind=EventKind.STORE_WRITE, actor="PESHKAR", since="2025-02-03T09:07:00Z")
    assert [e.event_id for e in got] == ["ev007", "ev008"]


# ---------------------------------------------------------------------------------------------------------------------
# children (transitive descendants via parent_id)
# ---------------------------------------------------------------------------------------------------------------------
def test_children_returns_transitive_descendants(new_log, sample_events):
    """children('ev001') is every event reachable through parent_id: ev002 -> ev003..5 -> ev006, ev007 -> ev008."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    got = {e.event_id for e in event_log.children("ev001")}
    assert got == {"ev002", "ev003", "ev004", "ev005", "ev006", "ev007", "ev008"}


def test_children_excludes_root_and_unrelated_branches(new_log, sample_events):
    """The root itself and events of other branches (ev009, ev012..) are not descendants of ev003."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    got = {e.event_id for e in event_log.children("ev003")}
    assert got == {"ev006", "ev007", "ev008"}
    assert "ev003" not in got


def test_children_of_leaf_or_unknown_event_is_empty(new_log, sample_events):
    """A leaf event, an unlinked event and an unknown id have no children."""
    event_log = new_log()
    for e in sample_events:
        event_log.append(e)
    assert event_log.children("ev008") == []
    assert event_log.children("ev009") == []
    assert event_log.children("no-such-event") == []


def test_children_follow_a_deep_chain_in_append_order(new_log):
    """A 30-deep chain returns all 29 descendants, nearest first (append order)."""
    event_log = new_log()
    event_log.append(make_event(CASE, event_id="n0"))
    for i in range(1, 30):
        event_log.append(make_event(CASE, event_id=f"n{i}", parent_id=f"n{i - 1}"))
    got = [e.event_id for e in event_log.children("n0")]
    assert got == [f"n{i}" for i in range(1, 30)]


# ---------------------------------------------------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------------------------------------------------
def test_second_event_log_on_same_file_sees_earlier_events(db_path, sample_events):
    """Events persist: a new EventLog on the same SQLite file reads what an earlier instance appended."""
    first = EventLog(db_path)
    for e in sample_events[:5]:
        first.append(e)
    second = EventLog(db_path)
    assert [e.event_id for e in second.read(CASE)] == ["ev001", "ev002", "ev003", "ev004", "ev005"]
    second.append(sample_events[5])
    assert len(EventLog(db_path).read(CASE)) == 6
    assert len(first.read(CASE)) == 6


def test_separate_files_are_separate_logs(tmp_path):
    """One log file per case: appending to one file does not show up in another."""
    a, b = EventLog(str(tmp_path / "a.sqlite")), EventLog(str(tmp_path / "b.sqlite"))
    a.append(make_event(CASE, event_id="only-a"))
    assert b.read(CASE) == []


# ---------------------------------------------------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------------------------------------------------
def _subscribe_in_thread(log: EventLog, case_id: str, n: int):
    """Collect the next n events of a subscription in a daemon thread (so a broken subscribe cannot hang the run)."""
    box: queue.Queue = queue.Queue()
    started = threading.Event()

    def run():
        try:
            it = log.subscribe(case_id)
            started.set()
            box.put([next(it) for _ in range(n)])
        except BaseException as exc:  # re-raised in the test thread
            started.set()
            box.put(exc)

    threading.Thread(target=run, daemon=True).start()
    assert started.wait(5)
    return box


def _result(box: queue.Queue):
    got = box.get(timeout=10)
    if isinstance(got, BaseException):
        raise got
    return got


def test_subscribe_yields_new_events_in_order(new_log):
    """A subscriber receives events appended after it subscribed, in append order."""
    event_log = new_log()
    box = _subscribe_in_thread(event_log, CASE, 2)
    threading.Event().wait(0.3)  # let the subscriber start waiting
    event_log.append(make_event(CASE, event_id="s1", ts="2025-02-03T10:00:00Z"))
    event_log.append(make_event(CASE, event_id="s2", ts="2025-02-03T10:00:01Z"))
    assert [e.event_id for e in _result(box)] == ["s1", "s2"]


def test_subscribe_ignores_other_cases(new_log):
    """A subscription to one case never yields another case's events."""
    event_log = new_log()
    box = _subscribe_in_thread(event_log, CASE, 1)
    threading.Event().wait(0.3)
    event_log.append(make_event("case-0008", event_id="other"))
    event_log.append(make_event(CASE, event_id="mine"))
    assert [e.event_id for e in _result(box)] == ["mine"]
