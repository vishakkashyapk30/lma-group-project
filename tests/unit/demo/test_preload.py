"""The evaluator demo (docs/handoff/evaluator-demo.md): pre-loading recorded cases at API start-up and the tour routes.

Offline and self-contained: a tiny synthetic snapshot is built in tmp_path (never the committed snapshots under demo/, except the last
test, which only validates their tour files against the contract).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from vakeel_sahayak.api import deps
from vakeel_sahayak.api.app import create_app
from vakeel_sahayak.demo import preload
from vakeel_sahayak.demo.preload import STAGES, Tour
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

REPO = Path(__file__).resolve().parents[3]
CASE = "demo-99"
SLUG = "99-fixture"
TABS = {"INTAKE": "dossier", "DOSSIER": "dossier", "GATE_1": "dossier", "RIGHTS": "rights", "BRIEF": "brief", "SPAR": "spar",
        "HEARING_PREP": "prep", "GATE_2": "brief", "FILE": "brief"}


def tour_doc(slug: str = SLUG, case_id: str = CASE) -> dict:
    """A minimal tour in the contract's shape."""
    return {
        "slug": slug, "case_id": case_id, "title": "Demo · fixture", "story": "A synthetic fixture case.",
        "variant": {"offence": "x", "custody": "y", "record": "z", "parity": "w"},
        "recorded": {"date": "2026-11-14", "backend": "offline", "model": "offline", "cost_inr": 0.0},
        "steps": [{"stage": s, "tab": TABS[s], "title": s.title(), "caption": f"What happened at {s}.", "agent": None,
                   "filled": [{"label": "l", "value": "v"}], "action": "approve_gate_2" if s == "GATE_2" else None} for s in STAGES],
    }


def make_snapshot(root: Path, slug: str = SLUG, case_id: str = CASE) -> Path:
    """demo/cases/<slug>/ with tour.json, events.jsonl (two events) and case/ holding one file."""
    folder = root / "cases" / slug
    (folder / "case").mkdir(parents=True)
    (folder / "case" / "01_fir.pdf").write_bytes(b"%PDF-1.4 fixture")
    (folder / "tour.json").write_text(json.dumps(tour_doc(slug, case_id)), encoding="utf-8")
    events = [
        Event(event_id=f"ev-{case_id}-1", ts="2026-11-14T10:00:00Z", case_id=case_id, kind=EventKind.USER_ACTION, actor=COUNSEL,
              inputs={"action": "create_case", "title": "Demo · fixture"}),
        Event(event_id=f"ev-{case_id}-2", ts="2026-11-14T10:00:01Z", case_id=case_id, kind=EventKind.USER_ACTION, actor=COUNSEL,
              inputs={"action": "upload", "files": ["01_fir.pdf"]}),
    ]
    (folder / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8")
    return folder


@pytest.fixture
def demo_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "demo"
    make_snapshot(root)
    monkeypatch.setenv("VS_DEMO_DIR", str(root))
    return root


def data_dir() -> Path:
    return deps._data_dir()


def test_import_copies_the_case_and_its_events(demo_root):
    log = EventLog(str(data_dir() / "record.sqlite"))
    assert preload.import_demo_cases(data_dir(), log) == [CASE]
    assert (data_dir() / "cases" / CASE / "01_fir.pdf").read_bytes() == b"%PDF-1.4 fixture"
    events = log.read(CASE)
    assert [e.event_id for e in events] == [f"ev-{CASE}-1", f"ev-{CASE}-2"]  # ids and times kept
    assert events[0].ts == "2026-11-14T10:00:00Z"


def test_import_is_idempotent(demo_root):
    log = EventLog(str(data_dir() / "record.sqlite"))
    assert preload.import_demo_cases(data_dir(), log) == [CASE]
    assert preload.import_demo_cases(data_dir(), log) == []
    assert len(log.read(CASE)) == 2


def test_import_never_overwrites_an_existing_case(demo_root):
    log = EventLog(str(data_dir() / "record.sqlite"))
    log.append(Event(event_id="mine", ts="", case_id=CASE, kind=EventKind.USER_ACTION, actor=COUNSEL, inputs={"action": "create_case", "title": "mine"}))
    folder = data_dir() / "cases" / CASE
    folder.mkdir(parents=True)
    (folder / "01_fir.pdf").write_bytes(b"counsel's own file")
    assert preload.import_demo_cases(data_dir(), log) == []
    assert (folder / "01_fir.pdf").read_bytes() == b"counsel's own file"
    assert [e.event_id for e in log.read(CASE)] == ["mine"]


def test_a_case_folder_alone_blocks_the_import(demo_root):
    log = EventLog(str(data_dir() / "record.sqlite"))
    (data_dir() / "cases" / CASE).mkdir(parents=True)
    assert preload.import_demo_cases(data_dir(), log) == []
    assert log.read(CASE) == []


def test_a_deleted_demo_case_stays_deleted(demo_root):
    log = EventLog(str(data_dir() / "record.sqlite"))
    preload.import_demo_cases(data_dir(), log)
    log.purge_case(CASE)
    import shutil

    shutil.rmtree(data_dir() / "cases" / CASE)
    assert preload.import_demo_cases(data_dir(), log) == []  # the marker remembers it was imported once


def test_create_app_imports_by_default(demo_root, monkeypatch):
    monkeypatch.delenv("VS_DEMO_CASES", raising=False)  # default: on
    create_app()
    assert len(EventLog(str(data_dir() / "record.sqlite")).read(CASE)) == 2


@pytest.mark.parametrize("value", ["off", "OFF", "0", "false"])
def test_demo_cases_off_imports_nothing(demo_root, monkeypatch, value):
    monkeypatch.setenv("VS_DEMO_CASES", value)
    create_app()
    assert EventLog(str(data_dir() / "record.sqlite")).read(CASE) == []
    assert not (data_dir() / "cases" / CASE).exists()


def test_a_broken_snapshot_does_not_stop_the_others(demo_root):
    bad = demo_root / "cases" / "00-broken"
    bad.mkdir(parents=True)
    (bad / "tour.json").write_text("{not json", encoding="utf-8")
    log = EventLog(str(data_dir() / "record.sqlite"))
    assert preload.import_demo_cases(data_dir(), log) == [CASE]


def test_tour_contract_rejects_steps_out_of_order():
    doc = tour_doc()
    doc["steps"][0], doc["steps"][1] = doc["steps"][1], doc["steps"][0]
    with pytest.raises(ValueError):
        Tour.model_validate(doc)
    doc = tour_doc()
    doc["steps"][2]["action"] = "approve_gate_2"  # only the GATE_2 step carries the action
    with pytest.raises(ValueError):
        Tour.model_validate(doc)


async def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def test_tour_routes_return_the_contract(demo_root, monkeypatch):
    monkeypatch.setenv("VS_DEMO_CASES", "on")
    async with await _client(create_app()) as client:
        listed = (await client.get("/api/demo/tours")).json()
        assert listed == [{**{k: tour_doc()[k] for k in ("slug", "case_id", "title", "story", "variant")}, "hi": None}]
        full = (await client.get(f"/api/demo/tours/{SLUG}")).json()
        # The optional Hindi text is null when the tour file has none.
        assert full.pop("hi") is None and all(s.pop("hi") is None for s in full["steps"])
        assert full == tour_doc()
        assert [s["stage"] for s in full["steps"]] == list(STAGES)
        assert (await client.get("/api/demo/tours/no-such-tour")).status_code == 404
        assert (await client.get(f"/api/cases/{CASE}")).json()["title"] == "Demo · fixture"  # the case is served by the ordinary routes


async def test_tours_list_is_empty_when_the_demo_is_off(demo_root, monkeypatch):
    monkeypatch.setenv("VS_DEMO_CASES", "off")
    async with await _client(create_app()) as client:
        assert (await client.get("/api/demo/tours")).json() == []
        assert (await client.get(f"/api/demo/tours/{SLUG}")).status_code == 404


async def test_reset_puts_the_case_back_as_recorded(demo_root, monkeypatch):
    monkeypatch.setenv("VS_DEMO_CASES", "on")
    async with await _client(create_app()) as client:
        await client.post(f"/api/cases/{CASE}/consent", json={"provider": "sarvam", "granted": False, "note": "evaluator"})
        assert len(EventLog(str(data_dir() / "record.sqlite")).read(CASE)) == 3
        res = await client.post(f"/api/demo/tours/{SLUG}/reset")
        assert res.status_code == 200 and res.json()["case_id"] == CASE
        assert [e.event_id for e in EventLog(str(data_dir() / "record.sqlite")).read(CASE)] == [f"ev-{CASE}-1", f"ev-{CASE}-2"]
        assert (await client.post("/api/demo/tours/no-such-tour/reset")).status_code == 404


async def test_create_case_with_a_chosen_id(monkeypatch):
    async with await _client(create_app()) as client:
        res = await client.post("/api/cases", json={"title": "t", "case_id": "demo-42"})
        assert res.status_code == 200 and res.json()["case_id"] == "demo-42"
        assert (await client.post("/api/cases", json={"title": "t", "case_id": "demo-42"})).status_code == 409
        assert (await client.post("/api/cases", json={"title": "t", "case_id": "../x"})).status_code == 422
        assert (await client.post("/api/cases", json={"title": "t"})).json()["case_id"] == "case-0001"


def test_every_committed_tour_matches_the_contract_and_its_snapshot():
    """Every demo/cases/*/tour.json validates, names its folder, and has a case snapshot whose events all belong to that case."""
    folders = preload.snapshot_dirs(REPO / "demo")
    for folder in folders:
        tour = preload.load_tour(folder)
        assert tour.slug == folder.name
        assert tour.title.startswith("Demo ·")
        assert (folder / "case").is_dir(), f"{folder.name}: no case/ snapshot"
        events = preload.read_events(folder)
        assert events and all(e.case_id == tour.case_id for e in events), f"{folder.name}: events.jsonl does not hold {tour.case_id}"
        assert any(e.inputs.get("action") == "create_case" for e in events)
        assert not any(e.kind == EventKind.GATE_APPROVED and e.inputs.get("gate") == "GATE_2_EXPORT" for e in events), "Gate 2 must be left open"
        assert [s.stage for s in tour.steps] == list(STAGES)


async def test_hindi_text_is_accepted_and_served(demo_root, monkeypatch):
    """A tour file with an optional `hi` object on the tour and on its steps is valid and is served as written; a file without is unchanged."""
    doc = tour_doc()
    doc["hi"] = {"title": "डेमो", "story": "कथा", "variant": {"offence": "अपराध"}, "src": {"title": "abc"}}
    doc["steps"][0]["hi"] = {"title": "शीर्षक", "caption": "विवरण", "filled": [{"label": "l", "value": "v"}], "src": {"caption": "d"}}
    (demo_root / "cases" / SLUG / "tour.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("VS_DEMO_CASES", "on")
    async with await _client(create_app()) as client:
        full = (await client.get(f"/api/demo/tours/{SLUG}")).json()
        assert full["hi"]["title"] == "डेमो" and full["hi"]["variant"] == {"offence": "अपराध"}
        assert full["steps"][0]["hi"]["caption"] == "विवरण" and full["steps"][0]["hi"]["filled"] == [{"label": "l", "value": "v"}]
        assert full["steps"][1]["hi"] is None
        assert (await client.get("/api/demo/tours")).json()[0]["hi"]["story"] == "कथा"
