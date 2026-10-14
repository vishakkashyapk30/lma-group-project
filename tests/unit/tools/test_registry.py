"""Tool registry (plan §3.3, §4.3, §5.1, §6-§9; docs/architecture/skeleton.md 'Tools').

Static part (passes on the skeleton): ALL_TOOL_MODULES names exactly the 39 plan tools, every module exposes the function
and a matching <NAME>_SPEC, signatures follow the plan, store tools declare the right StoreName (plan §5.1 'Tools'
column), shared-store readers expose `before` (plan §2 leakage rule), only `export` is gated (plan §8.1, §16).
Behaviour part (fails until implemented): discover_tools, get_tool, tools_for_agent.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.tools._helpers import ABHIYOJAK_TOOLS, PLAN_TOOL_NAMES, all_functions, all_specs, load_tool
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES, discover_tools, get_tool, tools_for_agent

# Parameter names, in order. The ones the plan writes out explicitly (map_section, date_calc, span_check, check_claim,
# file_item, ocr_page(lang), search_pages(query), export(format), ...) are marked "plan"; the rest follow the skeleton.
SIGNATURES: dict[str, list[str]] = {
    "inspect_page": ["file_path", "page"],
    "read_text_layer": ["file_path", "page"],
    "parse_layout": ["file_path", "page"],
    "clean_image": ["image", "ops"],
    "ocr_page": ["file_path", "page", "lang"],  # plan: ocr_page(lang)
    "vision_read_page": ["file_path", "page"],
    "detect_script": ["text", "image"],
    "translate": ["text", "src", "tgt"],  # plan: translate(hi->en)
    "transcribe": ["audio_path", "lang_hint"],  # plan: transcribe(audio)
    "split_bundle": ["file_path"],
    "classify_document": ["file_path", "pages"],
    "pseudonymise": ["text", "case_id"],
    "file_item": ["store", "item", "source"],  # plan: file_item(store, item, source)
    "search_pages": ["case_id", "query", "k"],  # plan: search_pages(query)
    "ask_user": ["questions", "case_id"],
    "extract_dossier": ["case_id", "fields"],
    "map_section": ["code", "section", "offence_date"],  # plan §7.1
    "date_calc": ["start", "end", "rule"],  # plan §7.1
    "span_check": ["value", "quote"],  # plan §7.1
    "rights_check": ["case_id", "as_of"],
    "diff_case_state": ["case_id", "since_hash"],
    "get_timeline": ["case_id", "start", "end"],
    "get_fact": ["case_id", "field"],
    "search_case_docs": ["case_id", "query", "doc_types", "k"],
    "get_statute": ["code", "section"],
    "search_statutes": ["query", "code", "k"],
    "transfer_check": ["old_ref", "new_ref"],
    "search_reasoning": ["query", "factor", "section_family", "before", "outcome", "court", "k"],
    "get_paragraph": ["doc_id", "para"],
    "citations": ["doc_ids", "want"],
    "good_law_check": ["doc_id", "as_of"],
    "similar_orders": ["facts_text", "signature", "before", "k"],
    "search_arguments": ["query", "factor", "section_family", "before", "k"],
    "search_objections": ["query", "factor", "section_family", "before", "k"],
    "check_claim": ["claim", "refs"],  # plan §8.1
    "render_citation": ["doc_id", "para"],
    "assemble_application": ["case_id"],
    "request_approval": ["case_id", "gate"],
    "export": ["case_id", "format"],  # plan: export(format)
}

# Plan §5.1 'Tools' column: which store each store-reading tool reads.
STORE_OF_TOOL: dict[str, set[StoreName]] = {
    "get_statute": {StoreName.LAW_STATUTES},
    "search_statutes": {StoreName.LAW_STATUTES},
    "map_section": {StoreName.LAW_CONCORDANCE},
    "transfer_check": {StoreName.LAW_CONCORDANCE},
    "search_reasoning": {StoreName.CASELAW_REASONING},
    "get_paragraph": {StoreName.CASELAW_REASONING},
    "citations": {StoreName.CASELAW_CITATIONS},
    "good_law_check": {StoreName.CASELAW_CITATIONS},
    "similar_orders": {StoreName.CASELAW_SIMILAR},
    "search_arguments": {StoreName.ADVOCACY_ARGUMENTS},
    "search_objections": {StoreName.ADVOCACY_OBJECTIONS},
    "search_case_docs": {StoreName.CASE_DOCS},
    "get_timeline": {StoreName.CASE_TIMELINE},
    "date_calc": {StoreName.CASE_TIMELINE},
    "get_fact": {StoreName.CASE_FACTS},
}

SHARED_STORE_READERS = ["search_reasoning", "search_arguments", "search_objections", "similar_orders"]


# ---------------------------------------------------------------- static: registry contents
def test_registry_lists_exactly_39_tools():
    """Plan §4.3-§8 name 39 tools and ALL_TOOL_MODULES has exactly one entry for each."""
    assert len(ALL_TOOL_MODULES) == 39
    assert len(PLAN_TOOL_NAMES) == 39 and len(set(PLAN_TOOL_NAMES)) == 39


def test_registry_names_equal_plan_names():
    """The set of registered tool names equals the plan-named set (no extras, none missing, no duplicates)."""
    names = [n for _, n in ALL_TOOL_MODULES]
    assert len(names) == len(set(names))
    assert set(names) == set(PLAN_TOOL_NAMES)


@pytest.mark.parametrize(("module_path", "name"), ALL_TOOL_MODULES, ids=[n for _, n in ALL_TOOL_MODULES])
def test_module_exposes_function_and_matching_spec(module_path, name):
    """Each (module, name) imports, defines the function `name` and a <NAME>_SPEC ToolSpec whose .name is `name`."""
    fn, spec = load_tool(module_path, name)
    assert callable(fn) and fn.__name__ == name
    assert isinstance(spec, ToolSpec)
    assert spec.name == name
    assert spec.description.strip()
    assert spec.plan_ref.startswith("§"), "plan_ref cites the plan section"
    assert spec.agents, "a tool nobody may call is dead"


@pytest.mark.parametrize("name", PLAN_TOOL_NAMES)
def test_signature_matches_plan(name):
    """Parameter names and order of each tool match the plan / skeleton table."""
    fn = all_functions()[name]
    assert list(inspect.signature(fn).parameters) == SIGNATURES[name]


def test_signature_table_covers_every_tool():
    """The signature table has one row per plan tool."""
    assert set(SIGNATURES) == set(PLAN_TOOL_NAMES)


@pytest.mark.parametrize("name", ["map_section", "date_calc", "check_claim", "file_item", "span_check"])
def test_plan_spelled_out_signatures_have_no_defaults_on_required_args(name):
    """Plan-spelled-out arguments are required positional parameters (schema-constrained calls need them all)."""
    params = inspect.signature(all_functions()[name]).parameters
    required = [p for p in params.values() if p.default is inspect.Parameter.empty]
    expected_required = {
        "map_section": ["code", "section", "offence_date"],
        "date_calc": ["start", "end"],  # ASSUMPTION: `rule` defaults to the inclusive day-1 rule of Appendix C
        "check_claim": ["claim"],  # ASSUMPTION: `refs` optional (a claim can be checked against the whole pack)
        "file_item": ["store", "item", "source"],
        "span_check": ["value", "quote"],
    }[name]
    assert [p.name for p in required] == expected_required


def test_date_calc_default_rule_is_inclusive_day_1():
    """Rights Radar counts the first-remand date as day 1 (plan App. C), so that is the default rule."""
    default = inspect.signature(all_functions()["date_calc"]).parameters["rule"].default
    assert default == "inclusive_day_1"


# ---------------------------------------------------------------- static: gating and reachability
def test_only_export_is_gated():
    """Plan §8.1/§16: `export` is the only gated tool."""
    gated = {n for n, s in all_specs().items() if s.gated}
    assert gated == {"export"}


def test_export_only_for_vakeel():
    """Export is reachable only by Vakeel (after Gate 2): SPEC.agents == [VAKEEL]."""
    assert all_specs()["export"].agents == [AgentName.VAKEEL]


def test_request_approval_reachable_by_vakeel_and_peshkar():
    """Gate requests come from Vakeel (Gate 2) and Peshkar (Gate 1) (plan §3.3, §8.1)."""
    assert set(all_specs()["request_approval"].agents) == {AgentName.VAKEEL, AgentName.PESHKAR}


@pytest.mark.parametrize("name", ["assemble_application", "check_claim", "render_citation", "get_paragraph"])
def test_drafting_tools_are_vakeel_only(name):
    """Drafting and checking tools belong to Vakeel alone (plan §8.1)."""
    assert all_specs()[name].agents == [AgentName.VAKEEL]


def test_no_tool_other_than_abhiyojak_set_lists_abhiyojak():
    """Abhiyojak appears in SPEC.agents of exactly its context-isolated tool set (plan §9)."""
    with_abhiyojak = {n for n, s in all_specs().items() if AgentName.ABHIYOJAK in s.agents}
    assert with_abhiyojak == ABHIYOJAK_TOOLS


def test_abhiyojak_cannot_reach_drafting_or_gated_tools():
    """Abhiyojak never reaches export, approval or drafting tools, so it cannot agree with Vakeel's notes."""
    forbidden = {"export", "request_approval", "assemble_application", "check_claim", "render_citation", "get_paragraph"}
    assert not forbidden & {n for n, s in all_specs().items() if AgentName.ABHIYOJAK in s.agents}


def test_munshi_has_no_store_search_tool_except_case_docs():
    """Munshi reads only the client's case shelf (plan §4.3): of the store-search tools only search_case_docs."""
    munshi_store_readers = {
        n for n, s in all_specs().items() if AgentName.MUNSHI in s.agents and n in STORE_OF_TOOL
    }
    assert munshi_store_readers == {"search_case_docs"}


# ---------------------------------------------------------------- static: stores and leakage rule
@pytest.mark.parametrize(("name", "stores"), sorted(STORE_OF_TOOL.items()))
def test_store_tools_declare_their_store(name, stores):
    """SPEC.stores of a store tool is the store(s) in plan §5.1's Tools column."""
    assert set(all_specs()[name].stores) == stores


def test_search_objections_reads_advocacy_objections():
    """Concrete example from the brief: search_objections -> advocacy.objections only."""
    assert all_specs()["search_objections"].stores == [StoreName.ADVOCACY_OBJECTIONS]


def test_file_item_writes_only_case_shelf_stores():
    """file_item files into the client's case shelf only (plan §4.3 step 3, §4.4)."""
    assert set(all_specs()["file_item"].stores) <= {StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS}


@pytest.mark.parametrize("name", SHARED_STORE_READERS)
def test_shared_store_readers_expose_before(name):
    """Every tool reading a dated shared store takes a `before` date (plan §2 leakage rule)."""
    assert "before" in inspect.signature(all_functions()[name]).parameters


def test_only_shared_dated_stores_need_before():
    """Case-shelf tools have no `before` (it is the case's own record); shared dated readers all have it."""
    for name, spec in all_specs().items():
        has_before = "before" in inspect.signature(all_functions()[name]).parameters
        reads_dated_shared = bool(
            set(spec.stores)
            & {
                StoreName.CASELAW_REASONING,
                StoreName.CASELAW_SIMILAR,
                StoreName.ADVOCACY_ARGUMENTS,
                StoreName.ADVOCACY_OBJECTIONS,
            }
        ) and name != "get_paragraph"  # get_paragraph fetches by id; the id came from a `before`-filtered search
        assert has_before == reads_dated_shared, name


# ---------------------------------------------------------------- behaviour: fails until implemented
def test_discover_tools_returns_39_specs():
    """discover_tools() collects all 39 specs keyed by tool name."""
    found = discover_tools()
    assert len(found) == 39
    assert set(found) == set(PLAN_TOOL_NAMES)
    assert all(isinstance(s, ToolSpec) and s.name == k for k, s in found.items())


def test_discover_tools_equals_module_specs():
    """The discovered specs equal the <NAME>_SPEC constants in the modules."""
    assert discover_tools() == all_specs()


def test_discover_tools_is_repeatable():
    """No import-time side effects: two calls give equal results."""
    assert discover_tools() == discover_tools()


def test_get_tool_returns_callable():
    """get_tool('date_calc') is the date_calc function itself."""
    fn = get_tool("date_calc")
    assert callable(fn)
    assert fn is all_functions()["date_calc"]


@pytest.mark.parametrize("name", PLAN_TOOL_NAMES)
def test_get_tool_resolves_every_plan_tool(name):
    """Every plan tool name resolves to its function."""
    assert get_tool(name) is all_functions()[name]


def test_get_tool_unknown_name_raises_keyerror():
    """An unknown tool name is a KeyError (ASSUMPTION: KeyError, matching dict lookup semantics)."""
    with pytest.raises(KeyError):
        get_tool("predict_grant_probability")


def test_tools_for_abhiyojak_is_exactly_the_isolated_set():
    """Plan §9: Abhiyojak gets get_fact, search_case_docs, get_statute, search_statutes, search_reasoning, search_objections."""
    assert {s.name for s in tools_for_agent(AgentName.ABHIYOJAK)} == ABHIYOJAK_TOOLS


def test_tools_for_munshi_has_no_export():
    """Munshi can never reach export."""
    names = {s.name for s in tools_for_agent(AgentName.MUNSHI)}
    assert "export" not in names and "request_approval" not in names
    assert "inspect_page" in names and "file_item" in names


def test_tools_for_vakeel_includes_gated_export_and_approval():
    """Vakeel's list includes request_approval and the gated export."""
    specs = {s.name: s for s in tools_for_agent(AgentName.VAKEEL)}
    assert "export" in specs and specs["export"].gated
    assert "request_approval" in specs


def test_tools_for_agent_override_intersects_with_spec_agents():
    """An `allowed` override cannot grant a tool the spec does not allow: export listed for Munshi yields nothing."""
    specs = tools_for_agent(AgentName.MUNSHI, allowed=["export"])
    assert specs == []


def test_tools_for_agent_override_keeps_permitted_tools():
    """With override ['export', 'inspect_page'], Munshi keeps only inspect_page."""
    assert [s.name for s in tools_for_agent(AgentName.MUNSHI, allowed=["export", "inspect_page"])] == ["inspect_page"]


def test_tools_for_agent_override_for_abhiyojak_drops_approval_and_export():
    """Abhiyojak with an override listing export/request_approval/get_fact keeps only get_fact."""
    got = tools_for_agent(AgentName.ABHIYOJAK, allowed=["export", "request_approval", "get_fact"])
    assert [s.name for s in got] == ["get_fact"]


def test_tools_for_agent_empty_override_gives_no_tools():
    """An explicit empty override means no tools (it is not 'use the default')."""
    assert tools_for_agent(AgentName.VAKEEL, allowed=[]) == []


@pytest.mark.parametrize("agent", list(AgentName))
def test_tools_for_agent_matches_yaml_intersect_spec(agent, load_yaml):
    """Default list for an agent = configs/tools.yaml entry filtered by SPEC.agents (computed independently)."""
    listed = load_yaml("tools.yaml")[agent.value.lower()]
    specs = all_specs()
    expected = {n for n in listed if agent in specs[n].agents}
    assert {s.name for s in tools_for_agent(agent)} == expected
