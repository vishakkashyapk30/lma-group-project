"""Tool registry: discovery from <NAME>_SPEC constants; no import-time side effects (plan §3.3)."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from functools import cache, lru_cache
from typing import Any, get_type_hints

from pydantic import ConfigDict, ValidationError, create_model

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec


class ToolPermissionError(PermissionError):
    """An agent called a tool that configs/tools.yaml (and the tool's SPEC.agents) does not allow it."""


class ToolArgumentError(ValueError):
    """Tool arguments failed validation against the tool's signature."""

    def __init__(self, tool: str, message: str) -> None:
        """Remember which tool rejected the arguments."""
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.message = message


ALL_TOOL_MODULES: list[tuple[str, str]] = [
    ("vakeel_sahayak.tools.intake.pages", "inspect_page"),
    ("vakeel_sahayak.tools.intake.pages", "read_text_layer"),
    ("vakeel_sahayak.tools.intake.pages", "parse_layout"),
    ("vakeel_sahayak.tools.intake.pages", "clean_image"),
    ("vakeel_sahayak.tools.intake.ocr", "ocr_page"),
    ("vakeel_sahayak.tools.intake.ocr", "vision_read_page"),
    ("vakeel_sahayak.tools.intake.ocr", "detect_script"),
    ("vakeel_sahayak.tools.intake.language", "translate"),
    ("vakeel_sahayak.tools.intake.language", "transcribe"),
    ("vakeel_sahayak.tools.intake.documents", "split_bundle"),
    ("vakeel_sahayak.tools.intake.documents", "classify_document"),
    ("vakeel_sahayak.tools.intake.documents", "file_item"),
    ("vakeel_sahayak.tools.intake.documents", "search_pages"),
    ("vakeel_sahayak.tools.intake.privacy_tool", "pseudonymise"),
    ("vakeel_sahayak.tools.interaction", "ask_user"),
    ("vakeel_sahayak.tools.dossier", "extract_dossier"),
    ("vakeel_sahayak.tools.dossier", "span_check"),
    ("vakeel_sahayak.tools.dossier", "rights_check"),
    ("vakeel_sahayak.tools.dossier", "diff_case_state"),
    ("vakeel_sahayak.tools.case.dates", "date_calc"),
    ("vakeel_sahayak.tools.case.timeline", "get_timeline"),
    ("vakeel_sahayak.tools.case.facts", "get_fact"),
    ("vakeel_sahayak.tools.case.docs", "search_case_docs"),
    ("vakeel_sahayak.tools.law.statutes", "get_statute"),
    ("vakeel_sahayak.tools.law.statutes", "search_statutes"),
    ("vakeel_sahayak.tools.law.concordance", "map_section"),
    ("vakeel_sahayak.tools.law.concordance", "transfer_check"),
    ("vakeel_sahayak.tools.caselaw.reasoning", "search_reasoning"),
    ("vakeel_sahayak.tools.caselaw.reasoning", "get_paragraph"),
    ("vakeel_sahayak.tools.caselaw.citations", "citations"),
    ("vakeel_sahayak.tools.caselaw.citations", "good_law_check"),
    ("vakeel_sahayak.tools.caselaw.similar", "similar_orders"),
    ("vakeel_sahayak.tools.advocacy.arguments", "search_arguments"),
    ("vakeel_sahayak.tools.advocacy.objections", "search_objections"),
    ("vakeel_sahayak.tools.drafting.claims", "check_claim"),
    ("vakeel_sahayak.tools.drafting.claims", "render_citation"),
    ("vakeel_sahayak.tools.drafting.application", "assemble_application"),
    ("vakeel_sahayak.tools.drafting.approval", "request_approval"),
    ("vakeel_sahayak.tools.drafting.export_tool", "export"),
]


@lru_cache(maxsize=1)
def _discover() -> tuple[dict[str, ToolSpec], dict[str, Callable[..., Any]]]:
    """Import each registered module once and collect its function and <NAME>_SPEC."""
    specs: dict[str, ToolSpec] = {}
    funcs: dict[str, Callable[..., Any]] = {}
    for module_name, tool in ALL_TOOL_MODULES:
        module = importlib.import_module(module_name)
        spec = getattr(module, f"{tool.upper()}_SPEC", None)
        func = getattr(module, tool, None)
        if not isinstance(spec, ToolSpec) or not callable(func):
            raise RuntimeError(f"{module_name} must define {tool}() and {tool.upper()}_SPEC")
        if spec.name != tool:
            raise RuntimeError(f"{module_name}: {tool.upper()}_SPEC.name is {spec.name!r}")
        specs[tool], funcs[tool] = spec, func
    return specs, funcs


def discover_tools() -> dict[str, ToolSpec]:
    """Import every module in ALL_TOOL_MODULES and collect <NAME>_SPEC into a registry keyed by tool name. Verify that the tools named in plan §4.3-§8 are all present, once each.

    Returns:
        Mapping of tool name to spec.
    """
    names = [name for _, name in ALL_TOOL_MODULES]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise RuntimeError(f"tools registered twice: {duplicates}")
    return dict(_discover()[0])


def get_tool(name: str) -> Callable[..., Any]:
    """Return the callable for a tool name.

    Args:
        name: see behaviour

    Returns:
        The function.

    Raises:
        KeyError: for an unknown tool name.
    """
    funcs = _discover()[1]
    if name not in funcs:
        raise KeyError(f"unknown tool {name!r}")
    return funcs[name]


def _allowed_names(agent: AgentName, allowed: list[str] | None) -> list[str]:
    """Names listed for an agent in configs/tools.yaml (or the override)."""
    if allowed is not None:
        return allowed
    from vakeel_sahayak.config import load_config

    return load_config().tools.get(AgentName(agent).value.lower(), [])


def tools_for_agent(agent: AgentName, allowed: list[str] | None = None) -> list[ToolSpec]:
    """Tools an agent may call, per configs/tools.yaml intersected with SPEC.agents.

    Args:
        agent: see behaviour
        allowed: override of configs/tools.yaml

    Returns:
        Specs.
    """
    specs = discover_tools()
    agent = AgentName(agent)
    return [specs[n] for n in _allowed_names(agent, allowed) if n in specs and agent in specs[n].agents]


def check_permission(agent: AgentName, name: str, allowed: list[str] | None = None) -> ToolSpec:
    """Raise ToolPermissionError unless `agent` may call tool `name`; return the tool's spec otherwise.

    The tool must be listed for the agent in configs/tools.yaml and the agent must be named in the tool's SPEC.agents.
    """
    specs = discover_tools()
    if name not in specs:
        raise ToolPermissionError(f"unknown tool {name!r}")
    agent = AgentName(agent)
    if name not in _allowed_names(agent, allowed) or agent not in specs[name].agents:
        raise ToolPermissionError(f"{agent.value} may not call {name}")
    return specs[name]


def validate_tool_config() -> list[str]:
    """Problems in configs/tools.yaml: unknown tools, unknown agents, or an agent not named in a tool's SPEC.agents."""
    from vakeel_sahayak.config import load_config

    specs, problems = discover_tools(), []
    for agent_key, names in load_config().tools.items():
        try:
            agent = AgentName(agent_key.upper())
        except ValueError:
            problems.append(f"tools.yaml: unknown agent {agent_key!r}")
            continue
        for name in names:
            if name not in specs:
                problems.append(f"tools.yaml: {agent_key} lists unknown tool {name!r}")
            elif agent not in specs[name].agents:
                problems.append(f"tools.yaml: {agent_key} lists {name}, whose SPEC.agents excludes it")
    return problems


@cache
def _args_model(name: str):  # noqa: ANN202
    """Pydantic model built from a tool function's signature and type hints (extra arguments are errors)."""
    func = _discover()[1].get(name) or get_tool(name)  # the real function: a test that patches `get_tool` with a *args/**kwargs wrapper must not poison this cache
    try:
        hints = get_type_hints(func)
    except Exception:  # unresolvable annotation: fall back to Any rather than refuse the tool
        hints = {}
    fields: dict[str, Any] = {}
    for pname, param in inspect.signature(func).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[pname] = (hints.get(pname, Any), default)
    return create_model(f"{name}_args", __config__=ConfigDict(extra="forbid"), **fields)


def validate_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce tool arguments against the tool's signature (types, enums, required, no extras).

    Args:
        name: tool name
        args: keyword arguments

    Returns:
        The coerced arguments (enum strings become enums).

    Raises:
        ToolArgumentError: describing the first problems found.
    """
    model = _args_model(name)
    try:
        validated = model.model_validate(args)
    except ValidationError as exc:
        detail = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors()[:5])
        raise ToolArgumentError(name, detail) from exc
    return {k: getattr(validated, k) for k in type(validated).model_fields}


def call_tool(agent: AgentName, name: str, args: dict[str, Any], allowed: list[str] | None = None) -> Any:
    """Check permission, validate arguments, enforce the gate, then run a tool.

    A gated tool (`export`) additionally needs the case's Gate 2 approval event in the case's event log; the tool
    function checks it again itself, so calling it directly cannot bypass the gate (plan §16). Invalid arguments come
    back as a retryable ToolError; permission and gate failures raise.

    Args:
        agent: the calling agent
        name: tool name
        args: keyword arguments
        allowed: override of configs/tools.yaml

    Returns:
        The tool's typed result or a ToolError.
    """
    spec = check_permission(agent, name, allowed)
    try:
        clean = validate_args(name, args)
    except ToolArgumentError as exc:
        return ToolError(tool=name, kind="invalid_args", message=exc.message, retryable=True)
    if spec.gated:
        from vakeel_sahayak.record.gates import assert_export_allowed
        from vakeel_sahayak.tools.runtime import get_runtime

        case_id = clean.get("case_id")
        if not case_id:
            raise ToolArgumentError(name, "a gated tool needs a case_id")
        assert_export_allowed(get_runtime().event_log(case_id), case_id)
    return get_tool(name)(**clean)
