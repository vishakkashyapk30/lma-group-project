"""Baseline B0. Single pass: raw facts and the 12-factor checklist to a brief in one call. No retrieval, no agents, no tool call. (plan §15.3)

Isolates: no retrieval, no agents. The model is an argument: `run_case` uses the context's client (else the shared 14B role), `run_case_with_model`
a named role. B0L is B0 with the prompted large model (`teacher` role), B0S is B0 with the untuned small model (`munshi_4b`); both work with any
backend (`VS_LLM_BACKEND`, the offline stand-in included).
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.baselines.common import draft, hosted_backend
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.schemas.bail_brief import BailBrief

TASK = "baseline.b0_single_pass"


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B0.

    Args:
        case: `case_id`, `facts` (or `facts_text`), `before`
        ctx: context; its LLM client is used when set

    Returns:
        BailBrief.
    """
    return draft(case, ctx, task=TASK)


def run_case_with_model(case: dict[str, Any], ctx: AgentContext, role: str | None) -> BailBrief:
    """B0 on the model of a configs/models.yaml role (B0L: 'teacher', B0S: 'munshi_4b'); None is plain B0.

    Args:
        case: see `run_case`
        ctx: see `run_case`
        role: model role

    Returns:
        BailBrief.
    """
    if role == "teacher" and hosted_backend():
        role = None  # stand-in ('b0l-hosted'): the hosted API model fills the large-model slot (the `teacher` role has no hosted client); label the row as a stand-in
    return draft(case, ctx, task=TASK, role=role)


def offline_draft(req: OfflineRequest) -> dict[str, Any]:
    """Offline stand-in for the drafting call: one favourable ground per checklist factor whose words occur in the facts (rules, no model)."""
    from vakeel_sahayak.eval.baselines.offline_rules import grounds_from_facts

    case = req.case
    return {"statutory_position": {}, "grounds": grounds_from_facts(str(case.get("facts") or ""), req.corpus.get("evidence") or []), "open_issues": []}


register_offline_handler(TASK, offline_draft)
