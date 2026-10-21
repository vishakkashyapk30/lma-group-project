"""S5 (A16) graph expansion: `Switches.graph_expansion` (HippoRAG 2 style; evaluation plan 3.3). Agent level on the case-0007 world.

The toolbox below gives the fake `search_reasoning` the real `expand_graph` logic (`tools.caselaw.reasoning.expand_search`) over a
`CitationGraph` built from the world's citation edges, so the agent's use of the argument, the signals and leakage are tested end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import _helpers as h
from tests.unit.agents.sutradhar._variants_helpers import build, canonical_run, digest
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.pipelines.citation_graph.expansion import expand_documents
from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph, NodeMeta, court_level_of
from vakeel_sahayak.schemas.enums import EventKind, OrderPart, StoreName
from vakeel_sahayak.tools.caselaw.reasoning import expand_search

GOLDEN = json.loads((Path(__file__).parent / "golden_default_run.json").read_text())
S5 = Switches.for_variant("S5")


class GraphToolbox(h.ScenarioToolbox):
    """ScenarioToolbox whose `search_reasoning` understands `expand_graph`."""

    def _graph(self) -> CitationGraph:
        rows = self._store(StoreName.CASELAW_REASONING).rows
        dates = {r.doc_id: (r.court, r.date) for r in rows}
        nodes = [NodeMeta(d, c, court_level_of(c), None, dt) for d, (c, dt) in dates.items()]
        return CitationGraph(nodes, list(self._store(StoreName.CASELAW_CITATIONS).edges))

    def t_search_reasoning(self, query, factor=None, section_family=None, before=None, outcome=None, court=None, k=10, expand_graph=False):
        plain = super().t_search_reasoning(query, factor, section_family, before, outcome, court, k)
        if not expand_graph or not plain:
            return plain
        graph, store = self._graph(), self._store(StoreName.CASELAW_REASONING)

        def search_docs(docs, kk):
            ranked = store._search(query, None, None, before, None, None, OrderPart.REASONING, 300)
            return [(r, 1.0 / (1 + i)) for i, r in enumerate(ranked) if r.doc_id in set(docs)][:kk]

        return expand_search(query, plain, before, k, expand=lambda seeds, n: expand_documents(graph, seeds, before, n), search_docs=search_docs)


def graph_env(**kw):
    return build(switches=kw.pop("switches", S5), toolbox_cls=GraphToolbox, **kw)


def calls(env, tool="search_reasoning"):
    return [c for c in env.toolbox.calls if c.name == tool]


def decisions(env, tool):
    return [e.outputs for e in env.ctx.log.events if e.kind == EventKind.AGENT_MESSAGE and e.tool == tool]


# ---- switches --------------------------------------------------------------------------------------------------
def test_switch_default_and_names():
    assert Switches().graph_expansion is False and S5.graph_expansion is True
    assert S5.variant() == "S5" and Switches.for_variant("A16") == S5 and "S5" in Switches.implemented_variants()
    assert "citation" in S5.describe()


# ---- default-off equivalence -----------------------------------------------------------------------------------
@pytest.mark.parametrize("world", ["case_0007", "case_0007_second_parity"])
def test_default_run_is_byte_identical_and_never_passes_expand_graph(world):
    env = graph_env(switches=Switches(graph_expansion=False), world=h.case_0007_world(second_parity=world.endswith("parity")))
    assert {k: digest(v) for k, v in canonical_run(env).items()} == GOLDEN[world]
    assert all("expand_graph" not in c.kwargs for c in calls(env)) and env.agent.retrieval_signals == {}


# ---- behaviour -------------------------------------------------------------------------------------------------
def test_authority_searches_ask_for_expansion_and_nothing_else_does():
    env = graph_env()
    env.agent.run(env.state)
    asked = [c for c in calls(env) if c.kwargs.get("expand_graph")]
    assert asked
    assert all("expand_graph" not in c.kwargs for c in calls(env, "search_objections") + calls(env, "citations"))


def test_the_citation_graph_adds_the_supreme_court_judgment_behind_a_high_court_hit():
    env = graph_env()
    out = env.agent.run(env.state)
    sig = out.retrieval_signals
    assert sum(s["graph"]["expansion_hits"] for s in sig.values()) > 0
    assert any("SC-2014-0463" in s["graph"]["expanded_docs"] for s in sig.values())
    assert sum(s["graph"]["expansion_sc_hits"] for s in sig.values()) > 0
    for s in sig.values():
        assert {"expand_calls", "expansion_hits", "expansion_sc_hits", "expanded_docs", "expansion_hits_in_pack"} <= set(s["graph"])
        assert s["graph"]["expansion_hits_in_pack"] >= 0  # may include expanded paragraphs another factor found (the shared pool)


def test_expansion_never_reaches_a_forbidden_or_later_document():
    env = graph_env()
    out = env.agent.run(env.state)
    seen = {i["doc_id"] for p in out.evidence_packs for s in p.slots for i in s.items if i.get("para") is not None}
    assert not seen & h.FORBIDDEN_DOC_IDS
    docs = {d for s in out.retrieval_signals.values() for d in s["graph"]["expanded_docs"]}
    assert not docs & h.FORBIDDEN_DOC_IDS


def test_run_is_deterministic():
    runs = [canonical_run(graph_env()) for _ in range(2)]
    assert digest(runs[0]["packs"]) == digest(runs[1]["packs"]) and digest(runs[0]["plans"]) == digest(runs[1]["plans"])


def test_signals_are_events_and_state_fields():
    env = graph_env()
    out = env.agent.run(env.state)
    emitted = {d["factor"]: d for d in decisions(env, "retrieval_signals")}
    assert set(emitted) == set(out.retrieval_signals) and all("graph" in d for d in emitted.values())


def test_store_call_budget_is_unchanged_by_expansion():
    plain, env = build(), graph_env()
    plain.agent.run(plain.state)
    env.agent.run(env.state)
    a, b = plain.budgets.snapshot().store_calls, env.budgets.snapshot().store_calls
    assert all(v <= 8 for v in b.values()) and sum(b.values()) <= sum(a.values()) + len(b)  # one tool call is still one store call


def test_budgets_are_respected_with_a_small_case_cap():
    env = graph_env(budgets=BudgetTracker(tokens_per_case=20000))
    env.agent.run(env.state)
    snap = env.budgets.snapshot()
    assert all(v <= 8 for v in snap.store_calls.values()) and snap.tokens_spent <= snap.tokens_cap + 500


def test_a_knocked_out_citation_store_turns_expansion_off():
    env = graph_env(switches=Switches(graph_expansion=True, knockout_store="caselaw.citations"))
    env.agent.run(env.state)
    assert not any(c.kwargs.get("expand_graph") for c in calls(env))


def test_combines_with_the_other_retrieval_variants():
    env = graph_env(switches=Switches(graph_expansion=True, retrieval_policy="self_critique", stopping="rules_llm"))
    out = env.agent.run(env.state)
    sig = next(iter(out.retrieval_signals.values()))
    assert {"graph", "critique", "stopping"} <= set(sig)
