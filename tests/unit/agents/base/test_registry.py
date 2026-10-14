"""Agent registry and class declarations (plan §3.2, §12; configs/models.yaml, configs/tools.yaml)."""

from __future__ import annotations

import importlib
import inspect

import pytest

from tests.unit.agents._helpers import models_yaml, tool_specs, tools_yaml
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.agents.registry import AGENT_CLASSES, get_agent_class
from vakeel_sahayak.schemas.enums import AgentName, StoreName


def load_class(dotted: str) -> type:
    module, _, cls = dotted.rpartition(".")
    return getattr(importlib.import_module(module), cls)


def test_registry_covers_exactly_the_six_agents():
    """One registry entry per AgentName, no extras."""
    assert set(AGENT_CLASSES) == {a.name for a in AgentName}
    assert len(AGENT_CLASSES) == 6


@pytest.mark.parametrize("name", sorted(AGENT_CLASSES))
def test_registry_path_resolves_to_a_base_agent_subclass(name):
    """Each dotted path imports and is a concrete BaseAgent subclass whose NAME is that agent."""
    cls = load_class(AGENT_CLASSES[name])
    assert issubclass(cls, BaseAgent) and cls is not BaseAgent
    assert not inspect.isabstract(cls)
    assert cls.NAME == AgentName[name]


@pytest.mark.parametrize("name", sorted(AGENT_CLASSES))
def test_role_model_is_a_models_yaml_key_used_by_that_agent(name):
    """ROLE_MODEL names an `llm` role in models.yaml whose used_by lists this agent."""
    cls = load_class(AGENT_CLASSES[name])
    llm = models_yaml()["llm"]
    assert cls.ROLE_MODEL in llm
    assert name.lower() in llm[cls.ROLE_MODEL]["used_by"]


@pytest.mark.parametrize(
    "name, role",
    [("MUNSHI", "munshi_4b"), ("PESHKAR", "extractor_4b"), ("SUTRADHAR", "agents_14b"), ("VAKEEL", "agents_14b"),
     ("ABHIYOJAK", "agents_14b"), ("PAIROKAR", "agents_14b")],
)
def test_role_models_match_plan_3_2(name, role):
    """Plan §3.2 table: Munshi 4B base, Peshkar fine-tuned 4B, the other four share Qwen3-14B."""
    assert load_class(AGENT_CLASSES[name]).ROLE_MODEL == role


def test_models_yaml_used_by_only_names_real_agents():
    """Every used_by entry is one of the six agents (no stale names)."""
    agents = {a.value.lower() for a in AgentName}
    for role, spec in models_yaml()["llm"].items():
        assert set(spec.get("used_by", [])) <= agents, role


def test_base_agent_is_abstract():
    """BaseAgent cannot be instantiated: run() is abstract."""
    with pytest.raises(TypeError):
        BaseAgent(None)  # type: ignore[abstract]


def test_every_agent_has_an_allow_list_naming_only_tools_that_list_it():
    """Each agent's tools.yaml entry is a subset of tools whose SPEC.agents includes the agent."""
    specs = tool_specs()
    allow = tools_yaml()
    assert set(allow) == {a.value.lower() for a in AgentName}
    for agent, tools in allow.items():
        for t in tools:
            assert AgentName(agent.upper()) in specs[t].agents, (agent, t)


def test_only_vakeel_can_export():
    """Export is Vakeel's gated tool; no other agent lists it (plan §8.1, §16)."""
    allow = tools_yaml()
    assert [a for a, tools in allow.items() if "export" in tools] == ["vakeel"]
    assert tool_specs()["export"].gated is True


def test_get_agent_class_resolves_every_name():
    """get_agent_class maps each AgentName to the registered class."""
    for name in AgentName:
        assert get_agent_class(name) is load_class(AGENT_CLASSES[name.name])


def test_stores_declared_by_tool_specs_are_real_store_names():
    """Sanity: every store named by a tool spec exists in StoreName (guards the allow-list tests above)."""
    for spec in tool_specs().values():
        assert all(isinstance(s, StoreName) for s in spec.stores)
