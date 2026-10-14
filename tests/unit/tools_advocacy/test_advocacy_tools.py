"""`search_arguments` and `search_objections` (plan §5.1 advocacy shelf, §9, §2 leakage).

advocacy.arguments holds DEFENSE-submission paragraphs for coverage and phrasing; advocacy.objections holds PROSECUTION-submission paragraphs.
Their content is never cited as authority (skeleton.md; authorities come from reasoning paragraphs only). Fixture (case-0007 decided
2025-02-03): defense paragraph DLHC-2022-1187#9 (parity, granted), prosecution paragraph DLHC-2023-0911#6 (parity, rejected).
"""

from __future__ import annotations

import pytest

from tests.unit.tools_case._helpers import assert_tool_error, install_recording_stores, stores_touched
from vakeel_sahayak.schemas.enums import AgentName, Factor, OrderPart, StoreName
from vakeel_sahayak.tools.advocacy.arguments import SEARCH_ARGUMENTS_SPEC, search_arguments
from vakeel_sahayak.tools.advocacy.objections import SEARCH_OBJECTIONS_SPEC, search_objections

BEFORE = "2025-02-03"
FORBIDDEN = {"TESTORD-2024-0001", "SAMEFIR-2024-0002", "DLHC-2025-0099"}

TOOLS = {
    "arguments": (search_arguments, OrderPart.DEFENSE, StoreName.ADVOCACY_ARGUMENTS, "co-accused granted bail parity"),
    "objections": (search_objections, OrderPart.PROSECUTION, StoreName.ADVOCACY_OBJECTIONS, "the State submits unlike the co-accused"),
}
BOTH = pytest.mark.parametrize("which", sorted(TOOLS))


@BOTH
def test_each_tool_returns_only_its_own_side_of_the_bench(world, install_stores, which):
    """Arguments are the defense's submissions, objections the prosecution's: neither ever returns reasoning or the other side's text."""
    fn, part, _, query = TOOLS[which]
    install_stores()
    hits = fn(query, before=BEFORE, k=20)
    assert hits and all(h.part == part for h in hits)


@BOTH
def test_each_tool_reads_only_its_own_store(world, monkeypatch, which):
    """Store routing: search_arguments -> advocacy.arguments only, search_objections -> advocacy.objections only; neither touches the
    reasoning store (so argument text can never be mistaken for an authority)."""
    fn, _, store, query = TOOLS[which]
    opened = install_recording_stores(monkeypatch, world)
    fn(query, before=BEFORE)
    assert {n for n, _ in opened} == {store}
    assert stores_touched(world) == {store}


@BOTH
def test_before_date_applies_and_a_missing_one_is_refused(world, install_stores, which):
    """Plan §2: later and test-split orders never surface, and a call without `before` is refused."""
    fn, _, _, query = TOOLS[which]
    install_stores()
    assert not FORBIDDEN & {h.doc_id for h in fn(query, before=BEFORE, k=50)}
    assert fn(query, before="2022-01-01", k=50) == []
    assert_tool_error(lambda: fn(query))


@BOTH
@pytest.mark.parametrize("bad", [{"before": "05/02/2025"}, {"k": 0}, {"k": -2}, {"factor": "grant_probability"}])
def test_bad_arguments_are_refused(world, install_stores, which, bad):
    fn, _, _, query = TOOLS[which]
    install_stores()
    args = {"before": BEFORE, **bad}
    assert_tool_error(lambda: fn(query, **args))


@BOTH
def test_empty_query_is_refused(world, install_stores, which):
    fn = TOOLS[which][0]
    install_stores()
    assert_tool_error(lambda: fn(" ", before=BEFORE))


@BOTH
def test_factor_and_section_family_filters(world, install_stores, which):
    fn, _, _, query = TOOLS[which]
    install_stores()
    hits = fn(query, factor=Factor.PARITY_WITH_CO_ACCUSED, section_family=["IPC 420"], before=BEFORE, k=20)
    assert hits and all(Factor.PARITY_WITH_CO_ACCUSED in h.factors and "IPC 420" in h.section_family for h in hits)
    assert fn(query, factor=Factor.FLIGHT_RISK, before=BEFORE, k=20) == []


def test_the_known_paragraphs_come_back(world, install_stores):
    install_stores()
    assert [(h.doc_id, h.para) for h in search_arguments("co-accused granted bail", before=BEFORE)] == [("DLHC-2022-1187", 9)]
    assert [(h.doc_id, h.para) for h in search_objections("the State submits", before=BEFORE)] == [("DLHC-2023-0911", 6)]


@BOTH
def test_k_limits_results(world, install_stores, which):
    fn, _, _, query = TOOLS[which]
    install_stores()
    assert len(fn(query, before=BEFORE, k=1)) <= 1


# ---------------------------------------------------------------- who may call them (plan §3.2, §9)
def test_abhiyojak_may_call_objections_but_not_arguments():
    """Abhiyojak sees objections and refusal reasoning only; the argument bank is Vakeel's phrasing aid, and Abhiyojak must not see Vakeel's
    material (context isolation, plan §9)."""
    assert AgentName.ABHIYOJAK in SEARCH_OBJECTIONS_SPEC.agents
    assert AgentName.ABHIYOJAK not in SEARCH_ARGUMENTS_SPEC.agents


def test_argument_bank_is_documented_as_never_authority():
    assert "never cited as authority" in SEARCH_ARGUMENTS_SPEC.description
    assert SEARCH_ARGUMENTS_SPEC.stores == [StoreName.ADVOCACY_ARGUMENTS] and SEARCH_OBJECTIONS_SPEC.stores == [StoreName.ADVOCACY_OBJECTIONS]
