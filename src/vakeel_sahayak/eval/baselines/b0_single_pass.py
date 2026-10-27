"""Baseline B0. Single pass: raw facts and the 12-factor checklist to a brief in one call. No retrieval, no agents, no tool call. (plan §15.3)

Isolates: no retrieval, no agents. The model is an argument: `run_case` uses the context's client (else the shared 14B role), `run_case_with_model`
a named role. B0L is B0 with the prompted large model (`teacher` role), B0S is B0 with the untuned small model (`munshi_4b`); both work with any
backend (`VS_LLM_BACKEND`, the offline stand-in included).

B0L on a hosted backend (`b0l_model_id`): `VS_LLM_BACKEND=sarvam` uses `sarvam-105b` (or the id in env `VS_B0L_MODEL`); `VS_LLM_BACKEND=openai` is
UNAVAILABLE (a refusal, never a silent copy of B0 on the same model) unless `VS_B0L_MODEL` names another OpenAI model id. The model id is recorded in the
run manifest (`b0l_model`) and in each case record (`variant_signals.b0l`), with `same_model_as_b0` when it equals the model B0 runs on (a Sarvam run whose
base model is already sarvam-105b: then B0L is the same model and the row must not be read as a larger-model result).
"""

from __future__ import annotations

import os
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
        model_id = b0l_model_id()  # raises NotImplementedError when no larger hosted model is available
        from vakeel_sahayak.models.factory import get_llm_model

        client = get_llm_model("agents_14b", model_id)
        b0_model = getattr(ctx.llm, "model_id", None) or getattr(_default_client(), "model_id", None)
        record = dict(getattr(ctx, "eval_record", None) or {})
        record["variant_signals"] = {**(record.get("variant_signals") or {}), "b0l": {"model_id": model_id, "b0_model_id": b0_model, "same_model_as_b0": model_id == b0_model}}
        ctx.eval_record = record
        saved = ctx.llm
        ctx.llm = client
        try:
            return draft(case, ctx, task=TASK)
        finally:
            ctx.llm = saved
    return draft(case, ctx, task=TASK, role=role)


B0L_SARVAM_MODEL = "sarvam-105b"


def b0l_model_id() -> str | None:
    """The model of B0L on a hosted backend, None off a hosted backend (the offline and local paths are unchanged).

    Raises:
        NotImplementedError: `VS_LLM_BACKEND=openai` with `VS_B0L_MODEL` unset (no model larger than the one B0 runs on is configured): a clear refusal.
    """
    if not hosted_backend():
        return None
    explicit = (os.environ.get("VS_B0L_MODEL") or "").strip()
    if explicit:
        return explicit
    if os.environ.get("VS_LLM_BACKEND", "").lower() == "sarvam":
        return B0L_SARVAM_MODEL
    raise NotImplementedError("B0L is unavailable on VS_LLM_BACKEND=openai: no model larger than B0's gpt-6-luna is configured (running it would duplicate B0). "
                              "Set VS_B0L_MODEL to another OpenAI model id with a price in configs/models.yaml, or run B0L on VS_LLM_BACKEND=sarvam.")


def _default_client() -> Any:
    try:
        from vakeel_sahayak.models.factory import get_llm

        return get_llm("agents_14b")
    except Exception:  # noqa: BLE001 - only used to record the id B0 runs on
        return None


def offline_draft(req: OfflineRequest) -> dict[str, Any]:
    """Offline stand-in for the drafting call: one favourable ground per checklist factor whose words occur in the facts (rules, no model)."""
    from vakeel_sahayak.eval.baselines.offline_rules import grounds_from_facts

    case = req.case
    return {"statutory_position": {}, "grounds": grounds_from_facts(str(case.get("facts") or ""), req.corpus.get("evidence") or []), "open_issues": []}


register_offline_handler(TASK, offline_draft)
