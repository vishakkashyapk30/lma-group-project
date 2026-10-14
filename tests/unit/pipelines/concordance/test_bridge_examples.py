"""The recodification bridge end to end on the pipeline output (plan §5.4): build edges, load them into the concordance
store and read the transfer flags the brief needs.

Examples: IPC 420 <-> BNS 318(4) (REWORDED, so a precedent under IPC 420 is `CHANGED` and must be qualified) and
IPC 406 <-> BNS 316(2) (SAME, so `SAME_TEXT`). Layout assumption of the store build: `concordance_edges.jsonl` in the source
directory (tests/unit/tools_law_case/test_map_section.py).
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines.concordance._helpers import read_edges, write_statutes, write_verify_dir
from vakeel_sahayak.pipelines.concordance.crpc_bnss_table import load_bail_sections_table
from vakeel_sahayak.pipelines.concordance.ipc2bns import build_ipc_bns_edges
from vakeel_sahayak.schemas.enums import TransferFlag
from vakeel_sahayak.stores.law_concordance import ConcordanceStore


@pytest.fixture()
def store(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    build_ipc_bns_edges(str(write_verify_dir(tmp_path / "v")), str(write_statutes(tmp_path / "s.json")), str(src / "concordance_edges.jsonl"))
    edges = read_edges(src / "concordance_edges.jsonl") + load_bail_sections_table()
    (src / "concordance_edges.jsonl").write_text("\n".join(e.model_dump_json() for e in edges) + "\n", encoding="utf-8")
    s = ConcordanceStore()
    s.build(str(src), str(out))
    s.open(str(out))
    return s


def test_ipc_420_to_bns_318_4_is_found_in_both_directions(store):
    """IPC 420 <-> BNS 318(4), the case-0007 mapping, resolves unambiguously from the built graph."""
    fwd = store.map_section("IPC", "420", "2024-08-10")
    back = store.map_section("BNS", "318(4)", "2024-08-10")
    assert fwd.equivalent == "BNS 318(4)" and not fwd.ambiguous
    assert back.equivalent == "IPC 420" and not back.ambiguous


def test_precedent_under_ipc_420_is_changed_for_a_bns_case(store):
    """Wording differs, so the transfer flag is CHANGED with a text diff and a qualification the brief must state."""
    res = store.transfer_flag("IPC 420", "BNS 318(4)")
    assert res.flag == TransferFlag.CHANGED
    assert res.text_diff
    assert res.qualification


def test_precedent_under_ipc_406_carries_over_unchanged(store):
    """IPC 406 -> BNS 316(2) is SAME_TEXT: the precedent applies as it stands."""
    assert store.transfer_flag("IPC 406", "BNS 316(2)").flag == TransferFlag.SAME_TEXT


def test_provision_without_ipc_counterpart_is_new(store):
    """BNS 111 has no IPC equivalent: NEW."""
    assert store.transfer_flag("", "BNS 111").flag == TransferFlag.NEW


def test_bail_table_rows_map_both_ways_in_the_built_store(store):
    """CrPC 436/436A/437/438/439 map to BNSS 478/479/480/482/483 and back (plan §2)."""
    for crpc, bnss in [("436", "478"), ("436A", "479"), ("437", "480"), ("438", "482"), ("439", "483")]:
        assert store.map_section("CrPC", crpc, "2024-08-10").equivalent == f"BNSS {bnss}"
        assert store.map_section("BNSS", bnss, "2024-08-10").equivalent == f"CrPC {crpc}"
