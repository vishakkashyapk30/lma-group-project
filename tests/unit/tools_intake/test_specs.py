"""Registration facts of the Munshi intake tools (plan §4.3 tool list, §3.3 'tools return typed results').

Static checks: every plan §4.3 tool has a function, a `<NAME>_SPEC`, is allowed for Munshi in configs/tools.yaml, and has the
signature the plan and toolbox fakes rely on. These pass without any implementation.
"""

from __future__ import annotations

import importlib
import inspect

import pytest

from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES

# tool -> (module, parameter names with defaults as a list of names)
INTAKE_TOOLS = {
    "inspect_page": ("vakeel_sahayak.tools.intake.pages", ["file_path", "page"]),
    "read_text_layer": ("vakeel_sahayak.tools.intake.pages", ["file_path", "page"]),
    "parse_layout": ("vakeel_sahayak.tools.intake.pages", ["file_path", "page"]),
    "clean_image": ("vakeel_sahayak.tools.intake.pages", ["image", "ops"]),
    "ocr_page": ("vakeel_sahayak.tools.intake.ocr", ["file_path", "page", "lang"]),
    "vision_read_page": ("vakeel_sahayak.tools.intake.ocr", ["file_path", "page"]),
    "detect_script": ("vakeel_sahayak.tools.intake.ocr", ["text", "image"]),
    "translate": ("vakeel_sahayak.tools.intake.language", ["text", "src", "tgt"]),
    "transcribe": ("vakeel_sahayak.tools.intake.language", ["audio_path", "lang_hint"]),
    "split_bundle": ("vakeel_sahayak.tools.intake.documents", ["file_path"]),
    "classify_document": ("vakeel_sahayak.tools.intake.documents", ["file_path", "pages"]),
    "file_item": ("vakeel_sahayak.tools.intake.documents", ["store", "item", "source"]),
    "search_pages": ("vakeel_sahayak.tools.intake.documents", ["case_id", "query", "k"]),
    "pseudonymise": ("vakeel_sahayak.tools.intake.privacy_tool", ["text", "case_id"]),
    "ask_user": ("vakeel_sahayak.tools.interaction", ["questions", "case_id"]),
}


def test_plan_lists_fifteen_munshi_tools():
    """Plan §4.3 names fifteen tools for Munshi (inspect_page ... ask_user)."""
    assert len(INTAKE_TOOLS) == 15


@pytest.mark.parametrize("name", sorted(INTAKE_TOOLS))
def test_tool_has_function_and_matching_spec(name):
    """Each tool is one function plus a `<NAME>_SPEC` ToolSpec in the same module (skeleton convention)."""
    module, params = INTAKE_TOOLS[name]
    mod = importlib.import_module(module)
    fn = getattr(mod, name)
    spec = getattr(mod, f"{name.upper()}_SPEC")
    assert isinstance(spec, ToolSpec) and spec.name == name
    assert list(inspect.signature(fn).parameters) == params
    assert AgentName.MUNSHI in spec.agents
    assert spec.plan_ref.startswith("§"), "spec cites its plan section"


@pytest.mark.parametrize("name", sorted(INTAKE_TOOLS))
def test_tool_is_registered_and_allowed_for_munshi(name, load_yaml):
    """Each tool is in ALL_TOOL_MODULES and allowed for Munshi in configs/tools.yaml."""
    module, _ = INTAKE_TOOLS[name]
    assert (module, name) in ALL_TOOL_MODULES
    assert name in load_yaml("tools.yaml")["munshi"]


def test_ask_user_is_shared_between_munshi_and_peshkar(load_yaml):
    """Plan §4.3: Munshi and Peshkar share the question limit, so both may call ask_user (and no one else)."""
    spec = importlib.import_module("vakeel_sahayak.tools.interaction").ASK_USER_SPEC
    assert set(spec.agents) == {AgentName.MUNSHI, AgentName.PESHKAR}
    assert "ask_user" in load_yaml("tools.yaml")["peshkar"]


def test_file_item_writes_only_to_the_case_shelf():
    """file_item may touch only case.docs, case.timeline and case.facts (plan §4.4)."""
    spec = importlib.import_module("vakeel_sahayak.tools.intake.documents").FILE_ITEM_SPEC
    assert set(spec.stores) == {StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS}


def test_no_other_intake_tool_touches_a_store():
    """Only file_item declares stores among the intake tools; reading and OCR tools are store-free."""
    for name, (module, _) in INTAKE_TOOLS.items():
        spec = getattr(importlib.import_module(module), f"{name.upper()}_SPEC")
        assert (spec.stores == []) == (name != "file_item"), name


def test_ocr_lang_default_is_english():
    """ocr_page defaults to lang='eng' (Tesseract-style codes: 'eng' or 'hin')."""
    from vakeel_sahayak.tools.intake.ocr import ocr_page

    assert inspect.signature(ocr_page).parameters["lang"].default == "eng"
