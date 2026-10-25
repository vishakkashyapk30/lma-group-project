"""PeshkarAgent (plan §3.2, §7.1-§7.4): class facts (pass today), List of Dates, Rights Radar call, change detection."""

from __future__ import annotations

import inspect

import pytest

from tests.fakes.data import build_world
from tests.fakes.toolbox import FakeToolbox
from tests.unit.agents._helpers import build_agent, make_state, models_yaml
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent


# ---- class facts -----------------------------------------------------------------------------------------------------
def test_class_facts():
    """Peshkar is a concrete BaseAgent named PESHKAR on the fine-tuned laptop 4B extractor."""
    assert issubclass(PeshkarAgent, BaseAgent) and not inspect.isabstract(PeshkarAgent)
    assert PeshkarAgent.NAME == AgentName.PESHKAR
    assert PeshkarAgent.ROLE_MODEL == "extractor_4b"
    spec = models_yaml()["llm"]["extractor_4b"]
    assert spec["where"] == "laptop" and spec["adapter"]  # QLoRA adapter attached


@pytest.mark.parametrize("method", ["run", "build_dossier", "build_list_of_dates", "run_rights_radar", "detect_changes"])
def test_method_exists(method):
    """The plan §7 steps exist as methods."""
    assert callable(getattr(PeshkarAgent, method))


# ---- List of Dates ---------------------------------------------------------------------------------------------------
def shuffled_world():
    world = build_world()
    from tests.fakes.stores import InMemoryTimelineStore

    events = list(world.timeline)
    world.stores[StoreName.CASE_TIMELINE] = InMemoryTimelineStore([events[i] for i in (4, 0, 6, 2, 5, 1, 3)])
    return world


def test_list_of_dates_is_sorted_with_a_source_on_every_row():
    """Seven events come back sorted by date, each with document and page (plan §7.2)."""
    toolbox = FakeToolbox(shuffled_world())
    agent, ctx, _ = build_agent(PeshkarAgent, toolbox=toolbox)
    rows = agent.build_list_of_dates(make_state())
    assert len(rows) == 7 and all(isinstance(r, TimelineEvent) for r in rows)
    dates = [r.date for r in rows]
    assert dates == sorted(dates)
    assert all(r.source and r.source.doc and r.source.page for r in rows)
    arrest = next(r for r in rows if r.label == "Arrest")
    assert (arrest.date, arrest.source.doc, arrest.source.page) == ("2024-08-20", "d2 (remand order)", 4)
    assert toolbox.count("get_timeline") >= 1  # built from case.timeline, not invented


# ---- Rights Radar ----------------------------------------------------------------------------------------------------
def test_rights_radar_calls_the_tool_once_and_returns_its_report(expected_rights_report):
    """run_rights_radar delegates to the deterministic rights_check tool exactly once (plan §7.3)."""
    agent, ctx, toolbox = build_agent(PeshkarAgent)
    report = agent.run_rights_radar(make_state())
    assert isinstance(report, RightsReport)
    assert report == expected_rights_report
    assert toolbox.count("rights_check") == 1
    assert ctx.log.tools_called().count("rights_check") == 1


# ---- change detection ------------------------------------------------------------------------------------------------
def test_duplicate_document_gives_an_empty_change_set():
    """No-op control (plan §7.4): filing a document that changes nothing yields an empty ChangeSet and no re-extraction."""
    agent, _, toolbox = build_agent(PeshkarAgent)
    change_set = agent.detect_changes(make_state())
    assert isinstance(change_set, ChangeSet)
    assert change_set.fields == [] and change_set.new_event_ids == [] and change_set.rights_changed == []
    # ASSUMPTION: nothing touched means nothing is re-extracted.
    assert toolbox.count("extract_dossier") == 0


def test_changed_field_is_re_extracted_alone_and_the_radar_re_run():
    """A diff that touches only charge_sheet re-extracts just that field and re-runs the Rights Radar."""
    toolbox = FakeToolbox(build_world())
    diff = ChangeSet(case_id="case-0007", trigger="new_document", fields=[FieldChange(field="charge_sheet", old_hash="h:0000", new_hash="h:1111")])
    toolbox.tools["diff_case_state"] = lambda case_id, since_hash=None: diff
    agent, _, _ = build_agent(PeshkarAgent, toolbox=toolbox)
    result = agent.detect_changes(make_state())
    assert [f.field for f in result.fields] == ["charge_sheet"]
    # ASSUMPTION: extract_dossier is called with fields=['charge_sheet'] only.
    extract_calls = [c for c in toolbox.calls if c.name == "extract_dossier"]
    assert extract_calls and all(c.kwargs.get("fields") == ["charge_sheet"] for c in extract_calls)
    assert toolbox.count("rights_check") == 1


# ---- parallel field reading (VS_PESHKAR_WORKERS) ---------------------------------------------------------------------
def test_peshkar_workers_env(monkeypatch):
    """Default: 1 worker with the offline backend, 4 with a hosted one; the variable overrides, clamped to 1..16."""
    from vakeel_sahayak.agents.peshkar.agent import peshkar_workers

    monkeypatch.delenv("VS_PESHKAR_WORKERS", raising=False)
    monkeypatch.setenv("VS_LLM_BACKEND", "offline")
    assert peshkar_workers() == 1
    monkeypatch.setenv("VS_LLM_BACKEND", "openai")
    assert peshkar_workers() == 4
    monkeypatch.setenv("VS_PESHKAR_WORKERS", "0")
    assert peshkar_workers() == 1
    monkeypatch.setenv("VS_PESHKAR_WORKERS", "99")
    assert peshkar_workers() == 16


def test_parallel_extraction_gives_the_same_dossier(monkeypatch):
    """The same dossier fields come back whether the fields are read by one thread or by four (merged in extraction order)."""
    results = {}
    for workers in ("1", "4"):
        monkeypatch.setenv("VS_PESHKAR_WORKERS", workers)
        agent, _, _ = build_agent(PeshkarAgent, toolbox=FakeToolbox(build_world()))
        try:
            dossier = agent.build_dossier(make_state())
        except Exception as exc:  # a stub-limited fake world: both settings must fail the same way
            results[workers] = type(exc).__name__
            continue
        results[workers] = dossier.fields.model_dump(mode="json")
    assert results["1"] == results["4"]
    assert isinstance(results["1"], dict), results["1"]
