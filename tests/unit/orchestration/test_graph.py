"""orchestration/graph: LangGraph wiring, gate routing (plan §3.1, §3.3, §16).

Node functions and `route_after_gate` are plain functions over CaseGraphState; `build_graph` needs langgraph and is
skipped without it. ASSUMPTION: graph node names are the node-function names without the `_node` suffix.
"""

from __future__ import annotations

import inspect

import pytest

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration import graph
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import GateId, Stage

NODE_FUNCTIONS = [
    "intake_node",
    "dossier_node",
    "gate1_node",
    "plan_node",
    "draft_node",
    "spar_node",
    "hearing_prep_node",
    "gate2_node",
    "export_node",
    "change_detection_node",
    "redraft_node",
]


@pytest.mark.parametrize("name", NODE_FUNCTIONS)
def test_every_plan_node_exists_with_state_signature(name):
    """Each node of the case graph (plan §3.1 diagram, §10) is a function CaseGraphState -> CaseGraphState."""
    fn = getattr(graph, name)
    assert list(inspect.signature(fn).parameters) == ["state"]


def test_node_set_is_complete():
    """No node function exists beyond the planned eleven (a new node needs a new test)."""
    found = {n for n, f in vars(graph).items() if inspect.isfunction(f) and n.endswith("_node")}
    assert found == set(NODE_FUNCTIONS)


def test_route_and_build_signatures():
    """route_after_gate(state) -> str and build_graph(config)."""
    assert list(inspect.signature(graph.route_after_gate).parameters) == ["state"]
    assert list(inspect.signature(graph.build_graph).parameters) == ["config"]


# ---------------------------------------------------------------------------------------------------------------------
# route_after_gate
# ---------------------------------------------------------------------------------------------------------------------
def _names() -> set[str]:
    return {n.removesuffix("_node") for n in NODE_FUNCTIONS}


def test_route_after_gate_1_approval_goes_to_planning(dossier):
    """After Gate 1 is approved (stage BRIEF, nothing pending) the next node is Sutradhar's planning."""
    state = CaseGraphState(case_id="case-0007", stage=Stage.BRIEF, dossier=dossier, pending_gate=None)
    assert graph.route_after_gate(state) == "plan"  # ASSUMPTION: stage BRIEF means Gate 1 passed


def test_route_after_gate_2_approval_goes_to_export(dossier):
    """After Gate 2 is approved (stage FILE, nothing pending) the next node is export."""
    state = CaseGraphState(case_id="case-0007", stage=Stage.FILE, dossier=dossier, pending_gate=None)
    assert graph.route_after_gate(state) == "export"  # ASSUMPTION: stage FILE means Gate 2 passed


@pytest.mark.parametrize("stage", list(Stage))
def test_route_never_exports_while_gate_2_is_pending(stage):
    """With Gate 2 still pending the router never returns 'export', whatever the stage (plan §16)."""
    state = CaseGraphState(case_id="case-0007", stage=stage, pending_gate=GateId.GATE_2_EXPORT)
    assert graph.route_after_gate(state) != "export"


@pytest.mark.parametrize("stage", list(Stage))
def test_route_never_plans_or_exports_while_gate_1_is_pending(stage):
    """With Gate 1 still pending the router neither plans nor exports."""
    state = CaseGraphState(case_id="case-0007", stage=stage, pending_gate=GateId.GATE_1_DOSSIER)
    assert graph.route_after_gate(state) not in {"plan", "draft", "spar", "export"}


@pytest.mark.parametrize("pending", [None, GateId.GATE_1_DOSSIER, GateId.GATE_2_EXPORT])
def test_route_returns_a_known_node_or_end(pending):
    """The router returns the name of an existing node (or LangGraph's END marker '__end__')."""
    out = graph.route_after_gate(CaseGraphState(case_id="c", stage=Stage.DOSSIER, pending_gate=pending))
    assert out in _names() | {"__end__", "END"}


# ---------------------------------------------------------------------------------------------------------------------
# build_graph (needs langgraph)
# ---------------------------------------------------------------------------------------------------------------------
def _edges(compiled):
    return [(e.source, e.target) for e in compiled.get_graph().edges]


def test_build_graph_compiles_with_all_nodes():
    """build_graph returns a compiled graph with every planned node."""
    pytest.importorskip("langgraph")
    compiled = graph.build_graph(AppConfig())
    assert _names() <= set(compiled.get_graph().nodes)
    assert hasattr(compiled, "invoke")


def test_build_graph_export_is_reachable_only_from_gate_2():
    """The only way into 'export' is from 'gate2' (the export guard in graph form, plan §16)."""
    pytest.importorskip("langgraph")
    compiled = graph.build_graph(AppConfig())
    sources = {s for s, t in _edges(compiled) if t == "export"}
    assert sources == {"gate2"}


def test_build_graph_planning_is_reachable_only_from_gate_1():
    """Drafting starts only after Gate 1: 'plan' has no incoming edge except from 'gate1'."""
    pytest.importorskip("langgraph")
    compiled = graph.build_graph(AppConfig())
    sources = {s for s, t in _edges(compiled) if t == "plan"}
    assert sources <= {"gate1", "change_detection"}  # change detection may re-plan after a re-approved change set
    assert "gate1" in sources
