"""Helpers shared by the tools tests: load every tool function and SPEC straight from ALL_TOOL_MODULES."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES

# The 39 tool names of plan §4.3-§8, in plan order.
PLAN_TOOL_NAMES: list[str] = [
    "inspect_page", "read_text_layer", "parse_layout", "clean_image", "ocr_page", "vision_read_page", "detect_script",
    "translate", "transcribe", "split_bundle", "classify_document", "pseudonymise", "file_item", "search_pages",
    "ask_user", "extract_dossier", "map_section", "date_calc", "span_check", "rights_check", "diff_case_state",
    "get_timeline", "get_fact", "search_case_docs", "get_statute", "search_statutes", "transfer_check",
    "search_reasoning", "get_paragraph", "citations", "good_law_check", "similar_orders", "search_arguments",
    "search_objections", "check_claim", "render_citation", "assemble_application", "request_approval", "export",
]  # fmt: skip

# Abhiyojak is context-isolated (plan §9).
ABHIYOJAK_TOOLS = {"get_fact", "search_case_docs", "get_statute", "search_statutes", "search_reasoning", "search_objections"}


def load_tool(module_path: str, name: str) -> tuple[Callable[..., Any], ToolSpec]:
    """Import `module_path` and return (function, <NAME>_SPEC)."""
    mod = importlib.import_module(module_path)
    return getattr(mod, name), getattr(mod, f"{name.upper()}_SPEC")


def all_specs() -> dict[str, ToolSpec]:
    """name -> ToolSpec read directly from the modules (independent of discover_tools)."""
    return {name: load_tool(m, name)[1] for m, name in ALL_TOOL_MODULES}


def all_functions() -> dict[str, Callable[..., Any]]:
    return {name: load_tool(m, name)[0] for m, name in ALL_TOOL_MODULES}


def agents_of(spec: ToolSpec) -> set[AgentName]:
    return set(spec.agents)
