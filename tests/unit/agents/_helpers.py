"""Helpers shared by the agent unit tests (plan §3.2, §3.3, §6-§11).

Everything here builds *inputs* (agents wired to fakes, states, grounds, scripted LLM responders) or accepts one of
several equally valid error styles; none of it re-implements product logic.
"""

from __future__ import annotations

import importlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from tests.fakes.context import make_context
from tests.fakes.data import CaseWorld, build_world
from tests.fakes.models import ScriptedLLM
from tests.fakes.toolbox import FakeToolbox
from vakeel_sahayak.agents.base import AgentContext, BaseAgent
from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, Ground
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import (
    ClaimCheck,
    Factor,
    FactorStance,
    Stage,
)
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES

REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_ID = "case-0007"
CASE_DATE = "2025-02-03"


# --------------------------------------------------------------------------------------------------------------------
# configs and tool specs (constants only: these helpers work on the skeleton today)
# --------------------------------------------------------------------------------------------------------------------
def tools_yaml() -> dict[str, list[str]]:
    return yaml.safe_load((REPO_ROOT / "configs" / "tools.yaml").read_text(encoding="utf-8"))


def models_yaml() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "configs" / "models.yaml").read_text(encoding="utf-8"))


def tool_specs() -> dict[str, ToolSpec]:
    """name -> ToolSpec, read from the <NAME>_SPEC constants (not through the stubbed registry.discover_tools)."""
    out: dict[str, ToolSpec] = {}
    for module, name in ALL_TOOL_MODULES:
        out[name] = getattr(importlib.import_module(module), f"{name.upper()}_SPEC")
    return out


# --------------------------------------------------------------------------------------------------------------------
# building agents on fakes (no pytest fixtures, so hypothesis tests can use it too)
# --------------------------------------------------------------------------------------------------------------------
def build_agent(
    cls: type[BaseAgent],
    llm: ScriptedLLM | None = None,
    toolbox: FakeToolbox | None = None,
    world: CaseWorld | None = None,
    **ctx_kwargs: Any,
) -> tuple[BaseAgent, AgentContext, FakeToolbox]:
    """Instantiate `cls` on a fake context.

    ASSUMPTION: the allow-list that BaseAgent.call_tool enforces is `ctx.config.tools` (agent name lower-case ->
    tool names, i.e. configs/tools.yaml). `tests.fakes.context.make_context` leaves `AppConfig.tools` empty, so the
    helper fills it from configs/tools.yaml; an implementation that reads tools.yaml itself behaves the same.
    """
    toolbox = toolbox or FakeToolbox(world or build_world())
    ctx = make_context(llm=llm, toolbox=toolbox, **ctx_kwargs)
    ctx.config = AppConfig(tools=tools_yaml())
    return cls(ctx), ctx, toolbox


class SpyBudget:
    """Duck-typed BudgetTracker that records every charge (independent of the real tracker's implementation)."""

    def __init__(self, store_calls: int = 8, tokens: int = 12000, exhausted: bool = False) -> None:
        self.charges: list[dict[str, Any]] = []
        self._left = BudgetLeft(store_calls=store_calls, tokens=tokens)
        self._exhausted = exhausted

    def charge(self, factor: str | None, tokens: int = 0, store_calls: int = 0) -> None:
        self.charges.append({"factor": factor, "tokens": tokens, "store_calls": store_calls})

    def left(self, factor: str | None = None) -> BudgetLeft:
        return self._left

    def exhausted(self, factor: str | None = None) -> bool:
        return self._exhausted

    @property
    def store_calls_charged(self) -> int:
        return sum(c["store_calls"] for c in self.charges)


# --------------------------------------------------------------------------------------------------------------------
# states and drafts
# --------------------------------------------------------------------------------------------------------------------
def make_state(
    dossier: CaseDossier | None = None,
    rights: RightsReport | None = None,
    brief: BailBrief | None = None,
    stage: Stage = Stage.BRIEF,
    case_id: str = CASE_ID,
    **extra: Any,
) -> CaseGraphState:
    """A CaseGraphState; `extra` attributes (e.g. vakeel_notes) are attached with model_copy(update=...)."""
    state = CaseGraphState(case_id=case_id, stage=stage, dossier=dossier, rights=rights, brief=brief)
    if extra:
        state = state.model_copy(update=extra)
    return state


def para_dict(world_or_paragraphs: Any, doc_id: str, para: int) -> dict[str, Any]:
    """A paragraph dict (JSON-mode dump of the ParagraphRecord) built from tests/fixtures/caselaw/paragraphs.json."""
    paragraphs = world_or_paragraphs
    for p in paragraphs:
        if p.doc_id == doc_id and p.para == para:
            return p.model_dump(mode="json")
    raise KeyError(f"{doc_id}#{para} not in fixture")


def make_ground(
    gid: str,
    factor: Factor,
    argument: str,
    authorities: list[tuple[str, int]] | None = None,
    stance: FactorStance = FactorStance.FAVOURABLE,
    check: ClaimCheck = ClaimCheck.NEEDS_REVIEW,
) -> Ground:
    return Ground(
        id=gid,
        factor=factor,
        stance=stance,
        argument=argument,
        authorities=[Authority(doc_id=d, para=p) for d, p in (authorities or [])],
        check=check,
    )


# --------------------------------------------------------------------------------------------------------------------
# accepting either of two equally valid error styles (each marked ASSUMPTION at the call site)
# --------------------------------------------------------------------------------------------------------------------
def is_denied(call: Any, *args: Any, **kwargs: Any) -> bool:
    """True when `call` is refused by raising PermissionError or by returning a ToolError."""
    try:
        result = call(*args, **kwargs)
    except PermissionError:
        return True
    return isinstance(result, ToolError)


@contextmanager
def expect_gate_error():
    """Pass if the block raises PermissionError or an exception whose class name mentions 'Gate' (the project's gate
    error is not fixed by the plan). Anything else, including a missing implementation, propagates."""
    try:
        yield
    except PermissionError:
        return
    except Exception as exc:  # noqa: BLE001
        if "gate" in type(exc).__name__.lower():
            return
        raise
    raise AssertionError("expected a gate error (PermissionError or a *Gate* error), nothing was raised")


def raises_or_tool_error(call: Any, *args: Any, **kwargs: Any) -> bool:
    """True when `call` raises KeyError/ValueError/LookupError or returns a ToolError (unknown ids)."""
    try:
        result = call(*args, **kwargs)
    except (KeyError, ValueError, LookupError):
        return True
    return isinstance(result, ToolError)


def route_or_refuse(route_question: Any, question: str) -> list[str]:
    """ASSUMPTION: a refusal is `[]` or an exception named *Refusal* / a ValueError; both mean 'no tools'."""
    try:
        return list(route_question(question))
    except ValueError:
        return []
    except Exception as exc:  # noqa: BLE001
        if "refus" in type(exc).__name__.lower():
            return []
        raise


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)
