"""configs/tools.yaml against the tool SPECs (plan §3.2, §4.3, §6-§9; skeleton.md: 'A tool may only be listed for an agent named in its SPEC.agents').

All tests here are static and pass on the skeleton.
"""

from __future__ import annotations

import pytest

from tests.unit.tools._helpers import ABHIYOJAK_TOOLS, PLAN_TOOL_NAMES, all_specs
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES


@pytest.fixture(scope="module")
def tools_yaml(configs_dir):
    import yaml

    return yaml.safe_load((configs_dir / "tools.yaml").read_text(encoding="utf-8"))


def test_yaml_has_exactly_the_six_agents(tools_yaml):
    """One key per agent of plan §3.2, in lower case."""
    assert set(tools_yaml) == {a.value.lower() for a in AgentName}


def test_yaml_lists_have_no_duplicates(tools_yaml):
    """A tool appears once per agent list."""
    for agent, names in tools_yaml.items():
        assert len(names) == len(set(names)), agent


def test_every_listed_tool_exists(tools_yaml):
    """Every name in tools.yaml is one of the 39 registered tools."""
    registered = {n for _, n in ALL_TOOL_MODULES}
    for agent, names in tools_yaml.items():
        assert set(names) <= registered, (agent, set(names) - registered)


def test_every_tool_is_listed_for_someone(tools_yaml):
    """No registered tool is unreachable: each is listed by at least one agent."""
    listed = {n for names in tools_yaml.values() for n in names}
    assert listed == set(PLAN_TOOL_NAMES)


def test_listed_agents_are_in_spec_agents(tools_yaml):
    """An agent may list a tool only if the agent is in the tool's SPEC.agents."""
    specs = all_specs()
    bad = [(a, n) for a, names in tools_yaml.items() for n in names if AgentName(a.upper()) not in specs[n].agents]
    assert bad == []


def test_every_spec_agent_lists_the_tool(tools_yaml):
    """Each agent in SPEC.agents also lists the tool in tools.yaml (the two sources agree exactly)."""
    missing = [
        (a.value, n)
        for n, s in all_specs().items()
        for a in s.agents
        if n not in tools_yaml[a.value.lower()]
    ]
    assert missing == []


def test_only_vakeel_lists_export(tools_yaml):
    """Export is reachable only through Vakeel (plan §8.1, §16)."""
    assert [a for a, names in tools_yaml.items() if "export" in names] == ["vakeel"]


def test_request_approval_listed_for_vakeel_and_peshkar(tools_yaml):
    """request_approval is in exactly the Vakeel and Peshkar lists."""
    assert sorted(a for a, names in tools_yaml.items() if "request_approval" in names) == ["peshkar", "vakeel"]


def test_abhiyojak_list_is_exactly_the_isolated_set(tools_yaml):
    """Plan §9 context isolation: objections, refusal reasoning, statutes, dossier (+ case docs per the brief)."""
    assert set(tools_yaml["abhiyojak"]) == ABHIYOJAK_TOOLS
    assert len(tools_yaml["abhiyojak"]) == len(ABHIYOJAK_TOOLS)


def test_abhiyojak_has_no_export_approval_or_drafting_tools(tools_yaml):
    """Abhiyojak cannot export, request approval, or use drafting tools."""
    forbidden = {"export", "request_approval", "assemble_application", "check_claim", "render_citation", "get_paragraph",
                 "search_arguments", "similar_orders", "citations", "good_law_check", "transfer_check", "map_section"}  # fmt: skip
    assert not forbidden & set(tools_yaml["abhiyojak"])


def test_munshi_lists_no_store_search_tool_except_case_docs(tools_yaml):
    """Munshi searches only the client's documents among the stores (search_pages is an intake search over pages)."""
    shared_and_case_readers = {
        "get_statute", "search_statutes", "map_section", "transfer_check", "search_reasoning", "get_paragraph",
        "citations", "good_law_check", "similar_orders", "search_arguments", "search_objections", "get_timeline",
        "get_fact", "date_calc",
    }  # fmt: skip
    assert not shared_and_case_readers & set(tools_yaml["munshi"])
    assert "search_case_docs" in tools_yaml["munshi"]


def test_munshi_has_no_gated_or_drafting_tools(tools_yaml):
    """Munshi neither drafts nor approves nor exports."""
    assert not {"export", "request_approval", "assemble_application", "check_claim", "render_citation"} & set(tools_yaml["munshi"])


def test_munshi_has_all_intake_tools(tools_yaml):
    """Plan §4.3 lists the intake tools for Munshi."""
    intake = {
        "inspect_page", "read_text_layer", "parse_layout", "clean_image", "ocr_page", "vision_read_page", "detect_script",
        "translate", "transcribe", "split_bundle", "classify_document", "pseudonymise", "file_item", "search_pages", "ask_user",
    }  # fmt: skip
    assert intake <= set(tools_yaml["munshi"])


def test_peshkar_has_the_plan_7_1_tools(tools_yaml):
    """Plan §7.1 Peshkar tools are all listed for Peshkar."""
    assert {"extract_dossier", "map_section", "date_calc", "span_check", "rights_check", "diff_case_state", "ask_user"} <= set(
        tools_yaml["peshkar"]
    )


def test_vakeel_has_the_plan_8_1_tools(tools_yaml):
    """Plan §8.1 Vakeel tools are all listed for Vakeel."""
    plan = {"get_paragraph", "get_statute", "check_claim", "transfer_check", "good_law_check", "render_citation",
            "assemble_application", "request_approval", "export"}  # fmt: skip
    assert plan <= set(tools_yaml["vakeel"])


def test_ask_user_only_munshi_and_peshkar(tools_yaml):
    """Plan §4.3: Munshi and Peshkar share the 3-question limit; nobody else asks the user."""
    assert sorted(a for a, names in tools_yaml.items() if "ask_user" in names) == ["munshi", "peshkar"]


def test_pairokar_has_only_read_tools_and_no_gated_ones(tools_yaml):
    """Pairokar drives other agents per file and never exports or approves (plan §11: no bulk export)."""
    assert not {"export", "request_approval"} & set(tools_yaml["pairokar"])
