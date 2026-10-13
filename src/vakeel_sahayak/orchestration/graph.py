"""LangGraph graph wiring: nodes, edges, interrupts (plan §3.3)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.state import CaseGraphState


def intake_node(state: CaseGraphState) -> CaseGraphState:
    """Munshi ingests files and fills the case shelf (plan §4).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def dossier_node(state: CaseGraphState) -> CaseGraphState:
    """Peshkar builds dossier, List of Dates, RightsReport (plan §7).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def gate1_node(state: CaseGraphState) -> CaseGraphState:
    """Interrupt: counsel approves the dossier (plan §3.1, §13.5).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def plan_node(state: CaseGraphState) -> CaseGraphState:
    """Sutradhar picks factors and plans retrieval per factor, in parallel (plan §6.2).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def draft_node(state: CaseGraphState) -> CaseGraphState:
    """Vakeel drafts, checks, repairs grounds (plan §8.1).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def spar_node(state: CaseGraphState) -> CaseGraphState:
    """Abhiyojak sparring, two rounds (plan §9).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def hearing_prep_node(state: CaseGraphState) -> CaseGraphState:
    """Vakeel builds the hearing-prep card (plan §8.3).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def gate2_node(state: CaseGraphState) -> CaseGraphState:
    """Interrupt: counsel approves the final draft (plan §3.1).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def export_node(state: CaseGraphState) -> CaseGraphState:
    """Gated export of DOCX/PDF (plan §8.2).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def change_detection_node(state: CaseGraphState) -> CaseGraphState:
    """Peshkar diffs case state after a new document or clock tick (plan §7.4).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def redraft_node(state: CaseGraphState) -> CaseGraphState:
    """Incremental redrafting of stale claims only (plan §10).

    Args:
        state: current graph state

    Returns:
        Updated state.
    """
    raise NotImplementedError


def route_after_gate(state: CaseGraphState) -> str:
    """Conditional edge: choose the next node after a gate decision.

    Args:
        state: see behaviour

    Returns:
        Node name.
    """
    raise NotImplementedError


def build_graph(config: AppConfig) -> Any:
    """Assemble the LangGraph StateGraph with SqliteSaver and interrupt-based gates (plan §3.3).

    Args:
        config: application config

    Returns:
        A compiled graph.
    """
    raise NotImplementedError
