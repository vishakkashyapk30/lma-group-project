"""LangGraph graph wiring: nodes, edges, interrupts (plan §3.3).

The case graph runs the agents in order with the two approval gates as interrupts:

    START -> intake (Munshi) -> dossier (Peshkar) -> gate1 (interrupt)
          -> plan (Sutradhar) -> draft (Vakeel) -> spar (Abhiyojak) -> hearing_prep (Vakeel) -> gate2 (interrupt)
          -> export -> END

and the change-set path (a new document mid-case):

    START -> change_detection (Peshkar diff) -> redraft (truth maintenance) -> gate1 (re-approval) -> ...

Each node is a plain function `CaseGraphState -> CaseGraphState`: it builds an `AgentContext` from the state, drives one
agent step, and returns the evolved state. `route_after_gate` is the conditional edge after a gate: it never lets the run
reach planning before Gate 1 or export before Gate 2 (plan §16). The gate nodes use `gates.await_gate`, which pauses the
run through `langgraph.types.interrupt` and reads counsel's decision from the event log, never from the resume value.

The LangGraph-free twin is `fallback_state_machine.PlainStateMachine`, which shares these node bodies and `await_gate`
with `interrupt=False`.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.gates import await_gate
from vakeel_sahayak.orchestration.state import CaseGraphState, open_graph_checkpointer
from vakeel_sahayak.schemas.enums import AgentName, GateId, Stage

# ---------------------------------------------------------------------------------------------------------------------
# node helpers
# ---------------------------------------------------------------------------------------------------------------------


def _context(state: CaseGraphState) -> Any:
    """An `AgentContext` for this case, bound to the state's event log, switches and leakage date (plan §3.3)."""
    from vakeel_sahayak.agents.base import AgentContext

    return AgentContext.for_case(state.case_id, switches=state.switches, log=state.event_log(), before=state.before)


def _with_error(state: CaseGraphState, where: str, exc: Exception) -> CaseGraphState:
    """A copy of the state with one more recorded stage error (never document text: a type and a short message)."""
    return state.model_copy(update={"errors": [*state.errors, f"{where}: {type(exc).__name__}: {str(exc)[:200]}"]})


def _drive(state: CaseGraphState, name: AgentName) -> CaseGraphState:
    """Run one agent's `run(state)` for this case; a failed stage is recorded and the case carries on (plan §11)."""
    from vakeel_sahayak.agents.registry import create_agent

    try:
        agent = create_agent(name, _context(state))
        try:
            out = agent.run(state)
        finally:
            agent.close()
        return out if isinstance(out, CaseGraphState) else state
    except Exception as exc:  # noqa: BLE001 - one failed stage is recorded, the run still yields a state
        return _with_error(state, name.value, exc)


# ---------------------------------------------------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------------------------------------------------


def intake_node(state: CaseGraphState) -> CaseGraphState:
    """Munshi ingests files and fills the case shelf (plan §4); a text-only case (no files) skips Munshi.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    if not state.files:
        return state
    return _drive(state, AgentName.MUNSHI)


def dossier_node(state: CaseGraphState) -> CaseGraphState:
    """Peshkar builds dossier, List of Dates, RightsReport (plan §7) and the stage advances to DOSSIER.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    state = _drive(state, AgentName.PESHKAR)
    return state.model_copy(update={"stage": Stage.DOSSIER})


def gate1_node(state: CaseGraphState) -> CaseGraphState:
    """Interrupt: counsel approves the dossier (plan §3.1, §13.5). On approval the stage advances to BRIEF.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    state = await_gate(state, GateId.GATE_1_DOSSIER)
    if state.gate_state(GateId.GATE_1_DOSSIER) == "approved":
        state = state.model_copy(update={"stage": Stage.BRIEF})
    return state


def plan_node(state: CaseGraphState) -> CaseGraphState:
    """Sutradhar picks factors and plans retrieval per factor, in parallel (plan §6.2); fills the evidence packs.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    return _drive(state, AgentName.SUTRADHAR)


def draft_node(state: CaseGraphState) -> CaseGraphState:
    """Vakeel drafts, checks, repairs grounds (plan §8.1).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    return _drive(state, AgentName.VAKEEL)


def spar_node(state: CaseGraphState) -> CaseGraphState:
    """Abhiyojak sparring, two rounds (plan §9); the stage advances to SPAR.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    state = _drive(state, AgentName.ABHIYOJAK)
    return state.model_copy(update={"stage": Stage.SPAR})


def hearing_prep_node(state: CaseGraphState) -> CaseGraphState:
    """Vakeel builds the hearing-prep card (plan §8.3); the stage advances to HEARING_PREP.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    from vakeel_sahayak.agents.registry import create_agent

    try:
        vakeel = create_agent(AgentName.VAKEEL, _context(state))
        try:
            card = vakeel.build_hearing_card(state)
        finally:
            vakeel.close()
        return state.model_copy(update={"hearing_card": card, "stage": Stage.HEARING_PREP})
    except Exception as exc:  # noqa: BLE001 - a failed card is recorded; the stage still advances
        return _with_error(state, "hearing_prep", exc).model_copy(update={"stage": Stage.HEARING_PREP})


def gate2_node(state: CaseGraphState) -> CaseGraphState:
    """Interrupt: counsel approves the final draft (plan §3.1). On approval the stage advances to FILE.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    state = await_gate(state, GateId.GATE_2_EXPORT)
    if state.gate_state(GateId.GATE_2_EXPORT) == "approved":
        state = state.model_copy(update={"stage": Stage.FILE})
    return state


def export_node(state: CaseGraphState) -> CaseGraphState:
    """Gated export of DOCX/PDF (plan §8.2). The `export` tool re-checks Gate 2, so export is impossible without it.

    Args:
        state: current graph state

    Returns:
        Updated state (`exported` paths and `done`).
    """
    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.schemas.enums import ExportFormat

    try:
        vakeel = create_agent(AgentName.VAKEEL, _context(state))
        try:
            res = vakeel.call_tool("export", case_id=state.case_id, format=ExportFormat.DOCX)
        finally:
            vakeel.close()
        if getattr(res, "kind", None):  # a ToolError (for example export is not built yet)
            return _with_error(state, "export", RuntimeError(f"{res.kind}: {getattr(res, 'message', '')[:120]}")).model_copy(update={"done": True})
        paths = [str(p) for p in (res if isinstance(res, list) else [res])]
        return state.model_copy(update={"exported": [*state.exported, *paths], "done": True})
    except Exception as exc:  # noqa: BLE001 - a blocked or failed export is recorded; the run ends
        return _with_error(state, "export", exc).model_copy(update={"done": True})


def change_detection_node(state: CaseGraphState) -> CaseGraphState:
    """Peshkar diffs case state after a new document or clock tick (plan §7.4); leaves a pending ChangeSet.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    from vakeel_sahayak.agents.registry import create_agent

    try:
        peshkar = create_agent(AgentName.PESHKAR, _context(state))
        try:
            change_set = peshkar.detect_changes(state)
        finally:
            peshkar.close()
        return state.model_copy(update={"pending_change_set": change_set})
    except Exception as exc:  # noqa: BLE001
        return _with_error(state, "change_detection", exc)


def redraft_node(state: CaseGraphState) -> CaseGraphState:
    """Incremental redrafting of stale claims only (plan §10): rewrite the grounds the change set touched, keep the rest.

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    from vakeel_sahayak.truth_maintenance.redraft import redraft_incrementally
    from vakeel_sahayak.truth_maintenance.staleness import touched_factors

    change_set = state.pending_change_set
    if change_set is None:
        return state
    try:
        brief = redraft_incrementally(state, change_set)
        return state.model_copy(
            update={
                "brief": brief,
                "pending_change_set": None,
                "change_sets": [*state.change_sets, change_set],
                "reopened_factors": touched_factors(change_set),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _with_error(state, "redraft", exc).model_copy(update={"pending_change_set": None})


# ---------------------------------------------------------------------------------------------------------------------
# routing and assembly
# ---------------------------------------------------------------------------------------------------------------------

NODES = {
    "intake": intake_node,
    "dossier": dossier_node,
    "gate1": gate1_node,
    "plan": plan_node,
    "draft": draft_node,
    "spar": spar_node,
    "hearing_prep": hearing_prep_node,
    "gate2": gate2_node,
    "export": export_node,
    "change_detection": change_detection_node,
    "redraft": redraft_node,
}


def route_after_gate(state: CaseGraphState) -> str:
    """Conditional edge after a gate: never plan before Gate 1, never export before Gate 2 (plan §16).

    - a gate still pending (counsel has not decided) ends the run until it is resumed;
    - Gate 1 passed (stage BRIEF, nothing pending) -> Sutradhar's planning;
    - Gate 2 passed (stage FILE, nothing pending) -> export;
    - anything else ends the run.

    Args:
        state: current graph state

    Returns:
        A node name, or LangGraph's END marker.
    """
    try:
        from langgraph.graph import END
    except ImportError:  # pragma: no cover - langgraph is a core dependency
        END = "__end__"
    if state.pending_gate is not None:  # Gate 1 or Gate 2 is still open: hold here
        return END
    if state.stage == Stage.FILE:
        return "export"
    if state.stage == Stage.BRIEF:
        return "plan"
    return END


def _entry_router(state: CaseGraphState) -> str:
    """The graph's entry branch: a pending change set re-enters at change detection, otherwise a fresh case starts at intake."""
    return "change_detection" if state.pending_change_set is not None else "intake"


def build_graph(config: AppConfig) -> Any:
    """Assemble the LangGraph StateGraph with SqliteSaver and interrupt-based gates (plan §3.3).

    Args:
        config: application config

    Returns:
        A compiled graph. Export has exactly one incoming edge (from gate2) and planning only follows Gate 1
        or the change-set path, so the export guard holds in graph form (plan §16).
    """
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(CaseGraphState)
    for name, fn in NODES.items():
        builder.add_node(name, fn)

    builder.add_conditional_edges(START, _entry_router, {"intake": "intake", "change_detection": "change_detection"})
    builder.add_edge("intake", "dossier")
    builder.add_edge("dossier", "gate1")
    builder.add_conditional_edges("gate1", route_after_gate, {"plan": "plan", END: END})
    builder.add_edge("plan", "draft")
    builder.add_edge("draft", "spar")
    builder.add_edge("spar", "hearing_prep")
    builder.add_edge("hearing_prep", "gate2")
    builder.add_conditional_edges("gate2", route_after_gate, {"export": "export", END: END})
    builder.add_edge("export", END)
    # change-set path: a new document is diffed, the stale grounds are redrafted, then Gate 1 is re-approved
    builder.add_edge("change_detection", "redraft")
    builder.add_edge("redraft", "gate1")

    checkpointer = open_graph_checkpointer(path=":memory:", config=config)
    return builder.compile(checkpointer=checkpointer)
