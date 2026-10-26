"""Shared plumbing of the model-using baselines (B0..B3): one checklist, one drafting call, the same output contract.

All baselines use the same 12-factor checklist and the same clean facts text (plan §15.3), draft with ONE structured call whose
schema is titled `BailBrief`, and return a `BailBrief` (fixed draft label). Run metadata (model names via `describe_run_models()`, tokens,
store calls, seed) is added by the driver (`eval.runners.driver.run_metadata`). Tool calls go to the context's toolbox (fixtures) or the
tool registry, are counted as store calls on the context's budget, and never carry anything but the case's `before` date as a filter.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground, OpenIssue, StatutoryPosition
from vakeel_sahayak.schemas.enums import Factor

SYSTEM = ("You help legal-aid counsel prepare a bail application for an Indian High Court. You never predict outcomes or give grant rates. "
          "Write a draft brief: one ground for each checklist factor that the facts support, with the stance, the argument and, only when evidence "
          "is supplied, the authorities (doc_id and para) taken from it.")
INSTRUCTIONS = ("Read the facts and the checklist. Return a BailBrief JSON object with `statutory_position`, `grounds` (id, factor, stance "
                "favourable|adverse|not_applicable, argument) and `open_issues`. Use factor values exactly as in the checklist.")


class DraftBrief(BaseModel):
    """What the model writes (no case id or label: the baseline sets them). Titled `BailBrief` so every baseline's call has one schema name."""

    model_config = ConfigDict(title="BailBrief")

    statutory_position: StatutoryPosition = Field(default_factory=StatutoryPosition)
    grounds: list[Ground] = Field(default_factory=list)
    open_issues: list[OpenIssue] = Field(default_factory=list)


def hosted_backend() -> bool:
    """True when `VS_LLM_BACKEND` names a hosted API and models are not forced offline (then a baseline must send pseudonymised facts, as Full does)."""
    import os

    return os.environ.get("VS_LLM_BACKEND", "offline").lower() in ("openai", "sarvam") and os.environ.get("VS_MODELS", "offline").lower() != "offline"


def facts_of(case: dict[str, Any]) -> str:
    """The case's facts text (`facts`, or `facts_text` of a T1 row)."""
    return str(case.get("facts") or case.get("facts_text") or "")


def checklist() -> list[dict[str, str]]:
    """The 12-factor checklist, the same for every system: value and plain label."""
    return [{"factor": f.value, "label": f.value.replace("_", " ")} for f in Factor]


def call_tool(ctx: AgentContext, name: str, **kwargs: Any) -> Any:
    """Call a tool from the context's toolbox or the registry, charge one store call; a failed call returns []."""
    from vakeel_sahayak.tools.registry import get_tool

    try:
        out = (ctx.tools.get(name) or get_tool(name))(**kwargs)
    except Exception:  # noqa: BLE001 - an unbuilt store gives the baseline no evidence, not a crash
        return []
    try:
        ctx.budgets.charge(None, store_calls=1)
    except Exception:  # noqa: BLE001 - minimal budgets
        pass
    return [] if getattr(out, "kind", None) and getattr(out, "message", None) else out


def evidence_rows(items: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Retrieved items as JSON-able rows for the prompt (paragraph text kept)."""
    rows = []
    for item in list(items or [])[:limit]:
        rows.append(item.model_dump(mode="json") if isinstance(item, BaseModel) else dict(item) if isinstance(item, dict) else {"text": str(item)})
    return rows


def resolve_llm(ctx: AgentContext, role: str | None = None) -> Any:
    """The model of a baseline: the role's client when `role` is given, else the context's client, else the shared 14B role."""
    from vakeel_sahayak.models.factory import get_llm

    if role:
        return get_llm(role)
    return ctx.llm if ctx.llm is not None else get_llm("agents_14b")


def draft(case: dict[str, Any], ctx: AgentContext, *, task: str, evidence: list[dict[str, Any]] | None = None, role: str | None = None,
          extra: dict[str, Any] | None = None, max_tokens: int = 2048) -> BailBrief:
    """One structured drafting call (facts, checklist, optional evidence) returning the brief with the case id and the fixed draft label.

    A model that fails to produce valid JSON after the repairs gives an empty brief (the run goes on; the miss is scored).
    """
    from vakeel_sahayak.models.json_schema import schema_of
    from vakeel_sahayak.models.prompting import render_prompt
    from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, structured_call

    facts, evidence = facts_of(case), evidence or []
    if hosted_backend():  # the same input rule as Full: pseudonymised facts, PII masked in public rows, so the boundary lets the call through
        from vakeel_sahayak.agents.outbound import mask_public
        from vakeel_sahayak.eval.runners.driver import file_facts

        facts, evidence = file_facts(ctx, case, shelve=False), mask_public(evidence)
    data: dict[str, Any] = {"case": {"case_id": case["case_id"], "facts": facts, "checklist": checklist()},
                            "corpus": {"evidence": evidence}, **(extra or {})}
    prompt = render_prompt(task, INSTRUCTIONS, data, system=SYSTEM, schema=schema_of(DraftBrief))
    try:
        res = structured_call(resolve_llm(ctx, role), prompt, DraftBrief, max_tokens=max_tokens, temperature=0.0, retries=2)
    except StructuredOutputError:
        return BailBrief(case_id=case["case_id"])
    try:
        ctx.budgets.charge(None, tokens=int(res.prompt_tokens) + int(res.completion_tokens))
    except Exception:  # noqa: BLE001 - minimal budgets
        pass
    value = res.value if isinstance(res.value, DraftBrief) else DraftBrief.model_validate(res.value)
    grounds = [g if g.id else g.model_copy(update={"id": f"G{i}"}) for i, g in enumerate(value.grounds, start=1)]
    return BailBrief(case_id=case["case_id"], statutory_position=value.statutory_position, grounds=grounds, open_issues=value.open_issues)
