"""PairokarAgent (plan §3.2, §11): class facts, next-step decisions, GPU-budgeted stage 2, no bulk export."""

from __future__ import annotations

import inspect

import pytest

from tests.fakes.data import build_world
from tests.fakes.toolbox import FakeToolbox
from tests.unit.agents._helpers import build_agent, models_yaml, tool_specs, tools_yaml
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.pairokar.agent import PairokarAgent
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.triage import TriageCard

DEFAULT_BAIL = "Default-bail window opens in 3 days (BNSS s.187(3))"  # reason text from plan §11


# ---- class facts -----------------------------------------------------------------------------------------------------
def test_class_facts():
    """Pairokar is a concrete BaseAgent named PAIROKAR on the shared 14B model."""
    assert issubclass(PairokarAgent, BaseAgent) and not inspect.isabstract(PairokarAgent)
    assert PairokarAgent.NAME == AgentName.PAIROKAR
    assert PairokarAgent.ROLE_MODEL == "agents_14b"
    assert "pairokar" in models_yaml()["llm"]["agents_14b"]["used_by"]


@pytest.mark.parametrize("method", ["run", "stage1", "decide_next_steps", "stage2"])
def test_method_exists(method):
    """The plan §11 stages exist as methods."""
    assert callable(getattr(PairokarAgent, method))


def test_pairokar_has_no_export_tool_and_no_gated_tool():
    """Plan §11 'no bulk export': configs/tools.yaml gives Pairokar no export (and no other gated tool)."""
    tools = tools_yaml()["pairokar"]
    assert "export" not in tools
    specs = tool_specs()
    assert not [t for t in tools if specs[t].gated]


# ---- decide_next_steps -----------------------------------------------------------------------------------------------
def card(case_id: str, rank: int, reasons=None, flags=None, missing=None) -> TriageCard:
    return TriageCard(case_id=case_id, urgency_rank=rank, reasons=reasons or [], flags=flags or [], missing_docs=missing or [])


def next_step(c: TriageCard) -> str:
    agent, _, _ = build_agent(PairokarAgent)
    out = agent.decide_next_steps([c])
    assert len(out) == 1 and out[0].case_id == c.case_id
    assert out[0].next_step
    return out[0].next_step.lower()


def test_open_default_bail_window_is_flagged_to_counsel():
    """An open default-bail window means 'flag counsel' (plan §11 example next step)."""
    # ASSUMPTION on wording: the text contains 'flag' and 'counsel'.
    text = next_step(card("case-0142", 1, reasons=[DEFAULT_BAIL]))
    assert "flag" in text and "counsel" in text


def test_missing_custody_certificate_with_nothing_urgent_requests_documents_first():
    """Nothing urgent but a custody certificate is missing: ask for documents before a full run."""
    text = next_step(card("case-0201", 7, reasons=["Custody 167 days"], missing=["custody certificate"]))
    assert "request" in text and "document" in text
    assert "queued" not in text


def test_ordinary_case_gets_a_full_brief_queued():
    """No deadline and nothing missing: queue the full brief."""
    text = next_step(card("case-0301", 9, reasons=["Custody 167 days"]))
    assert "full brief" in text and "queue" in text


def test_urgent_deadline_outranks_missing_documents():
    """A deadline case with a missing document is still flagged to counsel, not parked behind a document request."""
    text = next_step(card("case-0142", 1, reasons=[DEFAULT_BAIL], missing=["custody certificate"]))
    assert "flag" in text and "counsel" in text


def test_decide_next_steps_keeps_every_card_in_order():
    """One output card per input card, same ids in the same order; reasons and missing docs are not lost."""
    cards = [
        card("case-0142", 1, reasons=[DEFAULT_BAIL]),
        card("case-0201", 7, missing=["custody certificate"]),
        card("case-0301", 9, reasons=["Custody 167 days"]),
    ]
    agent, _, _ = build_agent(PairokarAgent)
    out = agent.decide_next_steps(cards)
    assert [c.case_id for c in out] == ["case-0142", "case-0201", "case-0301"]
    assert out[1].missing_docs == ["custody certificate"] and out[0].reasons == [DEFAULT_BAIL]


# ---- stage 2 ---------------------------------------------------------------------------------------------------------
def queued_cards(n: int) -> list[TriageCard]:
    """n ordinary cases ranked 1..n (shuffled on purpose by the caller), each ready for a full brief."""
    return [
        TriageCard(case_id=f"case-{100 + i}", urgency_rank=i, reasons=["Custody 167 days"], next_step="full brief queued")
        for i in range(1, n + 1)
    ]


def run_stage2(cards, budget_hours, toolbox=None):
    agent, ctx, toolbox = build_agent(PairokarAgent, toolbox=toolbox or FakeToolbox(build_world(), gate2_approved=True))
    done = agent.stage2(cards, budget_hours)
    return done, ctx, toolbox


def test_stage2_runs_in_urgency_order():
    """Completed case ids are the most urgent ones, in urgency_rank order, whatever the input order."""
    cards = list(reversed(queued_cards(6)))
    done, _, _ = run_stage2(cards, 100.0)
    ranked = [c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)]
    assert done == ranked[: len(done)] and len(done) >= 1


def test_stage2_with_no_budget_does_nothing():
    """A zero GPU budget completes no case."""
    done, _, _ = run_stage2(queued_cards(4), 0.0)
    assert done == []


def test_stage2_respects_the_gpu_budget():
    """More budget never completes fewer cases; a small budget completes fewer than all; a huge one completes all."""
    # ASSUMPTION: per-case cost is a fixed positive number of GPU-hours, so n(budget) is non-decreasing, 0 at 0, and
    # n <= budget / cost; we check the shape without knowing the cost.
    cards = queued_cards(8)
    counts = [len(run_stage2(cards, b)[0]) for b in (0.0, 0.5, 1.0, 2.0, 4.0, 1000.0)]
    assert counts == sorted(counts)
    assert counts[0] == 0
    assert counts[-1] == 8
    assert counts[1] < 8


def test_stage2_cases_are_unique_and_come_from_the_cards():
    """No case is run twice and none is invented."""
    cards = queued_cards(5)
    done, _, _ = run_stage2(cards, 1000.0)
    assert len(done) == len(set(done)) and set(done) <= {c.case_id for c in cards}


def test_stage2_skips_cases_waiting_for_documents():
    """A card whose next step is 'request documents first' is not given a full run."""
    cards = queued_cards(3)
    cards[0] = cards[0].model_copy(update={"next_step": "request documents first (custody certificate)", "missing_docs": ["custody certificate"]})
    done, _, _ = run_stage2(cards, 1000.0)
    assert cards[0].case_id not in done and len(done) == 2


def test_stage2_writes_each_output_as_it_finishes_in_completion_order():
    """Each completed case leaves its own record in the event log, in the order the cases finished (sessions resume)."""
    # ASSUMPTION: a finished case is recorded as one event by PAIROKAR whose JSON contains the case id.
    done, ctx, _ = run_stage2(queued_cards(4), 1000.0)
    assert done
    positions = []
    for case_id in done:
        idx = [i for i, e in enumerate(ctx.log.events) if case_id in e.model_dump_json() and str(getattr(e.actor, "value", e.actor)) == "PAIROKAR"]
        assert idx, f"no completion record for {case_id}"
        positions.append(idx[0])
    assert positions == sorted(positions)


def test_stage2_never_exports_even_when_gate_2_is_open():
    """No bulk export (plan §11, §16): the export tool is never called, whatever the gate says."""
    done, ctx, toolbox = run_stage2(queued_cards(5), 1000.0)
    assert done
    assert toolbox.exports == []
    assert toolbox.count("export") == 0
    assert not [e for e in ctx.log.events if e.kind == EventKind.TOOL_CALL and e.tool == "export"]
