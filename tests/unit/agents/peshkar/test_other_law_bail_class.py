"""Part II of the First Schedule as Peshkar's last fallback for the bail class of a charged section (`PeshkarAgent._map_section`).

Part II classes an offence against a law other than the IPC / BNS by its maximum punishment (`configs/first_schedule_part2.jsonl`,
read by script from the official CrPC and BNSS PDFs). It is used only when the statute store and Part I give no bail class, only for
another law, and only when a maximum punishment is known; a class already found is never replaced.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.tools.base import ToolError


def _agent(statutes: dict[tuple[str, str], tuple[bool | None, str | None]]) -> PeshkarAgent:
    """A Peshkar whose only tool answers `get_statute` from `statutes` ((code, section) -> (bailable, max_punishment))."""
    agent = object.__new__(PeshkarAgent)

    def tool(name, **kw):
        assert name == "get_statute"
        hit = statutes.get((kw["code"], kw["section"]))
        if hit is None:
            return ToolError(tool=name, kind="not_found", message="no such section", retryable=False)
        return SimpleNamespace(bailable=hit[0], max_punishment=hit[1])

    agent._tool = tool  # type: ignore[method-assign]
    return agent


def _map(agent: PeshkarAgent, code: str, section: str) -> dict:
    return agent._map_section({"as_written": f"{code} {section}", "code": code, "section": section}, None, {})


@pytest.mark.parametrize(
    ("section", "punishment", "want"),
    [("22", "20 years", False), ("21", "10 years", False), ("27", "1 year", True), ("26", "3 years", False), ("31A", "death", False)],
)
def test_a_special_act_section_without_a_bail_flag_gets_the_part2_class(section, punishment, want):
    value = _map(_agent({("NDPS", section): (None, punishment)}), "NDPS", section)
    assert value["bailable"] is want and value["max_punishment"] == punishment


def test_a_class_already_found_is_kept():
    agent = _agent({("NDPS", "19"): (False, "20 years"), ("NDPS", "27"): (False, "1 year")})
    assert _map(agent, "NDPS", "19")["bailable"] is False
    assert _map(agent, "NDPS", "27")["bailable"] is False  # the store says non-bailable; Part II (bailable) does not override it


def test_no_maximum_punishment_gives_no_class():
    assert "bailable" not in _map(_agent({("NDPS", "2"): (None, None)}), "NDPS", "2")
    assert "bailable" not in _map(_agent({}), "NDPS", "22")
    assert "bailable" not in _map(_agent({("NDPS", "29"): (None, "same as the offence")}), "NDPS", "29")


@pytest.mark.parametrize("code", ["IPC", "BNS"])
def test_ipc_and_bns_sections_are_not_touched_by_part2(code):
    """Part II covers offences against other laws only: an IPC/BNS section the schedule does not class stays unclassed."""
    value = _map(_agent({(code, "9999"): (None, "2 years")}), code, "9999")
    assert "bailable" not in value and value["max_punishment"] == "2 years"
