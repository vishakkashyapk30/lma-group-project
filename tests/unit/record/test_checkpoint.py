"""record/checkpoint: SQLite checkpointer wiring for resume and gate interrupts (plan §3.3, §17).

Needs langgraph (and its SQLite saver); skipped when absent. Interrupted work (an Ada session cut at 6 h) must resume
from the latest graph state of a case. ASSUMPTION: the LangGraph thread id is the case id.
"""

from __future__ import annotations

import inspect
import os

import pytest

from vakeel_sahayak.record import checkpoint


def test_checkpoint_signatures():
    """open_checkpointer(path=None) and resume_state(case_id, checkpointer) (plan §3.3)."""
    assert list(inspect.signature(checkpoint.open_checkpointer).parameters) == ["path"]
    assert inspect.signature(checkpoint.open_checkpointer).parameters["path"].default is None
    assert list(inspect.signature(checkpoint.resume_state).parameters) == ["case_id", "checkpointer"]


def _langgraph():
    pytest.importorskip("langgraph")
    pytest.importorskip("langgraph.checkpoint.sqlite")
    from langgraph.checkpoint.base import empty_checkpoint

    return empty_checkpoint


def _put(saver, case_id: str, values: dict, step: int = 0):
    empty_checkpoint = _langgraph()
    cp = empty_checkpoint()
    cp["channel_values"] = values
    config = {"configurable": {"thread_id": case_id, "checkpoint_ns": ""}}
    meta = {"source": "loop", "step": step, "writes": {}, "parents": {}}
    return saver.put(config, cp, meta, {})


def test_open_checkpointer_creates_sqlite_file(tmp_path):
    """open_checkpointer(path) returns a saver backed by that SQLite file."""
    _langgraph()
    path = str(tmp_path / "graph.sqlite")
    saver = checkpoint.open_checkpointer(path)
    assert saver is not None
    assert hasattr(saver, "put") and hasattr(saver, "get_tuple")
    _put(saver, "case-0007", {"stage": "DOSSIER"})
    assert os.path.exists(path)


def test_resume_state_returns_latest_state_for_case(tmp_path):
    """resume_state(case) returns the newest saved state of that case only."""
    _langgraph()
    saver = checkpoint.open_checkpointer(str(tmp_path / "graph.sqlite"))
    _put(saver, "case-0007", {"stage": "INTAKE", "case_id": "case-0007"}, step=0)
    _put(saver, "case-0007", {"stage": "DOSSIER", "case_id": "case-0007"}, step=1)
    _put(saver, "case-0008", {"stage": "BRIEF", "case_id": "case-0008"}, step=0)
    state = checkpoint.resume_state("case-0007", saver)
    assert state["stage"] == "DOSSIER"
    assert state["case_id"] == "case-0007"


def test_resume_state_survives_reopening_the_file(tmp_path):
    """A new checkpointer on the same file (a new Ada session) resumes the saved state."""
    _langgraph()
    path = str(tmp_path / "graph.sqlite")
    _put(checkpoint.open_checkpointer(path), "case-0007", {"stage": "SPAR", "pending_gate": "GATE_2_EXPORT"})
    state = checkpoint.resume_state("case-0007", checkpoint.open_checkpointer(path))
    assert state["stage"] == "SPAR"
    assert state["pending_gate"] == "GATE_2_EXPORT"


def test_resume_state_for_unknown_case_is_empty(tmp_path):
    """ASSUMPTION: a case with no checkpoint resumes as an empty state dict."""
    _langgraph()
    saver = checkpoint.open_checkpointer(str(tmp_path / "graph.sqlite"))
    assert checkpoint.resume_state("case-9999", saver) == {}
