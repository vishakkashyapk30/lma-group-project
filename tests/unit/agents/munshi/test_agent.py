"""MunshiAgent (plan §3.2, §4.3, §4.6): class facts (pass today), gap check, question limit, filing, report."""

from __future__ import annotations

import inspect

import pytest

from tests.fakes.data import build_world
from tests.fakes.toolbox import FakePage, FakeToolbox, leaked_names
from tests.fixtures import pdfgen
from tests.unit.agents._helpers import build_agent, make_state, models_yaml
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, EventKind, StoreName
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, IngestionReport


# ---- class facts -----------------------------------------------------------------------------------------------------
def test_class_facts():
    """Munshi is a concrete BaseAgent named MUNSHI on the laptop 4B model."""
    assert issubclass(MunshiAgent, BaseAgent) and not inspect.isabstract(MunshiAgent)
    assert MunshiAgent.NAME == AgentName.MUNSHI
    assert MunshiAgent.ROLE_MODEL == "munshi_4b"
    assert models_yaml()["llm"]["munshi_4b"]["where"] == "laptop"
    assert models_yaml()["llm"]["munshi_4b"]["used_by"] == ["munshi"]


@pytest.mark.parametrize("method", ["run", "survey", "categorise", "file_items", "check_gaps", "check_conflicts", "report"])
def test_method_exists(method):
    """The plan §4.3 loop steps exist as methods."""
    assert callable(getattr(MunshiAgent, method))


# ---- scenarios -------------------------------------------------------------------------------------------------------
def bundle_pages(with_names: bool = False) -> list[FakePage]:
    """A 5-page constructed bundle: remand order (pp.1-2), bail order (pp.3-4), order sheet (p.5). No custody certificate."""
    remand = pdfgen.REMAND_PAGE + ("\nThe accused Ramesh Kumar Yadav was produced by Anil Pratap Singh." if with_names else "")
    return [
        FakePage(text=remand, doc_type=DocumentType.REMAND_ORDER),
        FakePage(text=remand, doc_type=DocumentType.REMAND_ORDER),
        FakePage(text=pdfgen.BAIL_ORDER_PAGE, doc_type=DocumentType.BAIL_ORDER),
        FakePage(text=pdfgen.BAIL_ORDER_PAGE, doc_type=DocumentType.BAIL_ORDER),
        FakePage(text=pdfgen.ORDER_SHEET_PAGE, doc_type=DocumentType.ORDER_SHEET),
    ]


def state_for(documents: list[DocumentEntry] | None = None):
    report = IngestionReport(case_id="case-0007", file="bundle_1.pdf", documents=documents or [])
    return make_state().model_copy(update={"ingestion": report})


def thin_state():
    """Nothing filed: FIR, remand, bail orders, charge sheet and custody certificate are all missing."""
    return state_for([])


def test_gap_check_is_skipped_under_the_p5_switch():
    """switches.munshi_no_gap_check removes step 4: no gaps, no search_pages, no ask_user, no tool call at all."""
    toolbox = FakeToolbox(build_world(), pages=bundle_pages())
    agent, ctx, _ = build_agent(MunshiAgent, toolbox=toolbox, switches=Switches(munshi_no_gap_check=True))
    assert agent.check_gaps(thin_state()) == []
    assert toolbox.count("search_pages") == 0 and toolbox.count("ask_user") == 0
    assert toolbox.questions == []
    assert not [e for e in ctx.log.events if e.kind == EventKind.TOOL_CALL]


def test_gap_check_runs_by_default_and_finds_the_missing_custody_certificate():
    """Control for the switch: by default the same state yields gaps, including the custody certificate, and acts on them."""
    toolbox = FakeToolbox(build_world(), pages=bundle_pages())
    agent, _, _ = build_agent(MunshiAgent, toolbox=toolbox)
    gaps = agent.check_gaps(thin_state())
    assert any("custody certificate" in g.item.lower() for g in gaps)
    assert toolbox.count("search_pages") + toolbox.count("ask_user") >= 1
    assert all(g.action for g in gaps)


def test_never_more_than_three_questions_per_round():
    """With five or more gaps Munshi still asks counsel at most 3 questions in the round (plan §4.3 ask_user limit)."""
    # ASSUMPTION: one check_gaps call is one round; the 3-question limit covers every ask_user call in it.
    toolbox = FakeToolbox(build_world(), pages=[], answers=["", "", ""])
    agent, _, _ = build_agent(MunshiAgent, toolbox=toolbox)
    gaps = agent.check_gaps(thin_state())
    assert len(gaps) >= 4
    assert sum(len(q) for q in toolbox.questions) <= 3
    assert all(len(q) <= 3 for q in toolbox.questions)


def test_survey_categorise_file_report_are_consistent():
    """The report mirrors what was filed: documents, page ranges and counts match the filing calls."""
    toolbox = FakeToolbox(build_world(), pages=bundle_pages())
    agent, ctx, _ = build_agent(MunshiAgent, toolbox=toolbox)
    state = state_for([])
    routes = agent.survey(state)
    docs = agent.categorise(state)
    counts = agent.file_items(state)
    report = agent.report(state)
    assert isinstance(report, IngestionReport) and report.case_id == "case-0007"
    assert len(routes) == 5
    assert [d.doc_id for d in report.documents] == [d.doc_id for d in docs]
    assert [d.pages for d in report.documents] == [[1, 2], [3, 4], [5, 5]]
    assert report.filed == counts

    def filed_into(store: StoreName) -> int:
        return sum(1 for c in toolbox.calls if c.name == "file_item" and StoreName(c.kwargs["store"]) == store)

    assert report.filed.timeline_events == filed_into(StoreName.CASE_TIMELINE)
    assert report.filed.chunks == filed_into(StoreName.CASE_DOCS)
    assert report.filed.timeline_events >= 1 and report.filed.chunks >= 1


def test_filing_pseudonymises_before_anything_is_written_or_logged(planted_names):
    """Planted names in the page text never reach a file_item payload or the event log (plan §4.3 step 3, §16)."""
    toolbox = FakeToolbox(build_world(), pages=bundle_pages(with_names=True))
    agent, ctx, _ = build_agent(MunshiAgent, toolbox=toolbox)
    state = state_for([])
    agent.survey(state)
    agent.categorise(state)
    agent.file_items(state)
    payloads = [str(c.kwargs) for c in toolbox.calls if c.name == "file_item"]
    assert payloads
    assert leaked_names(payloads, planted_names) == []
    assert leaked_names([ctx.log.as_text()], planted_names) == []
