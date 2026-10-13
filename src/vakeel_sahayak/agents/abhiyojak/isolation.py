"""Context isolation: what Abhiyojak may see (plan §9)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.orchestration.state import CaseGraphState

VISIBLE_STORES: list[str] = ["advocacy.objections", "caselaw.reasoning", "law.statutes"]


def build_context(state: CaseGraphState) -> dict[str, Any]:
    """Only drafted grounds with cited material and the dossier; never Vakeel's plan or notes.

    Args:
        state: see behaviour

    Returns:
        Prompt context.
    """
    raise NotImplementedError
