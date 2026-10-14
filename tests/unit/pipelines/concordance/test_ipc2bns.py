"""IPC <-> BNS edge construction from IPC2BNS-Verify (plan §2 source 2, §5.1 `law.concordance`, §5.4).

Edge types are same / split / merged / reworded / new, each with a text diff. Worked examples: IPC 420 <-> BNS 318(4)
(case-0007; the wording differs, so REWORDED) and IPC 406 <-> BNS 316(2) (carried over unchanged, so SAME). The synthetic
sections IPC 999 (split into BNS 888(1) and 888(2)), IPC 777 + 778 (merged into BNS 666) and BNS 111 (new) stand in for the
real split / merged / new provisions. The layout of the input directory is an ASSUMPTION documented in `_helpers.py`.
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines.concordance._helpers import PAIRS, T, edge_map, read_edges, write_statutes, write_verify_dir
from vakeel_sahayak.pipelines.concordance.ipc2bns import build_ipc_bns_edges


@pytest.fixture()
def built(tmp_path):
    verify = write_verify_dir(tmp_path / "verify")
    statutes = write_statutes(tmp_path / "statutes.json")
    out = tmp_path / "edges.jsonl"
    n = build_ipc_bns_edges(str(verify), str(statutes), str(out))
    return n, read_edges(out)


def test_returns_the_number_of_edges_written(built):
    """The return value is the edge count and equals the lines written: 1 + 1 + 2 (split) + 2 (merged) + 1 (new) = 7."""
    n, edges = built
    assert n == len(edges) == 7


def test_unchanged_text_is_a_same_edge_with_an_empty_diff(built):
    """IPC 406 -> BNS 316(2) has identical text, so the edge is SAME and the text diff is empty."""
    e = edge_map(built[1])[("IPC 406", "BNS 316(2)")]
    assert e.type == T.SAME
    assert not e.text_diff


def test_ipc_420_to_bns_318_4_is_reworded_with_a_text_diff(built):
    """The worked example of case-0007: IPC 420 -> BNS 318(4) is REWORDED and carries a diff naming both wordings."""
    e = edge_map(built[1])[("IPC 420", "BNS 318(4)")]
    assert e.type == T.REWORDED
    assert e.text_diff
    assert "dishonestly inducing delivery" in e.text_diff and "thereby" in e.text_diff


def test_one_ipc_section_to_two_bns_sections_is_split(built):
    """IPC 999 -> BNS 888(1) and BNS 888(2): two SPLIT edges from the same old_ref."""
    edges = [e for e in built[1] if e.old_ref == "IPC 999"]
    assert {e.new_ref for e in edges} == {"BNS 888(1)", "BNS 888(2)"}
    assert {e.type for e in edges} == {T.SPLIT}


def test_two_ipc_sections_into_one_bns_section_is_merged(built):
    """IPC 777 and IPC 778 -> BNS 666: two MERGED edges into the same new_ref."""
    edges = [e for e in built[1] if e.new_ref == "BNS 666"]
    assert {e.old_ref for e in edges} == {"IPC 777", "IPC 778"}
    assert {e.type for e in edges} == {T.MERGED}


def test_bns_section_without_ipc_counterpart_is_new(built):
    """A BNS provision with no IPC equivalent is a NEW edge; ASSUMPTION: its old_ref is empty."""
    new = [e for e in built[1] if e.type == T.NEW]
    assert [e.new_ref for e in new] == ["BNS 111"]
    assert new[0].old_ref == ""


def test_all_five_edge_types_occur_and_nothing_else(built):
    """The five types of plan §5.1 are all produced from the synthetic source, and no other type appears."""
    assert {e.type for e in built[1]} == {T.SAME, T.SPLIT, T.MERGED, T.REWORDED, T.NEW}


def test_refs_are_normalised_as_code_and_section(built):
    """Every non-empty ref reads 'IPC <n>' or 'BNS <n>', the form used by section_family and map_section."""
    for e in built[1]:
        assert e.old_ref == "" or e.old_ref.startswith("IPC ")
        assert e.new_ref.startswith("BNS ")


def test_building_twice_gives_identical_output(tmp_path):
    """The build is deterministic: same inputs, byte-identical output file."""
    verify = write_verify_dir(tmp_path / "v")
    statutes = write_statutes(tmp_path / "s.json")
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    build_ipc_bns_edges(str(verify), str(statutes), str(a))
    build_ipc_bns_edges(str(verify), str(statutes), str(b))
    assert a.read_bytes() == b.read_bytes()


def test_unknown_section_in_the_source_is_reported_not_guessed(tmp_path):
    """A pair naming a section that is absent from the statutes file cannot be typed: the build fails loudly.

    ASSUMPTION: the failure is a ValueError or KeyError (the plan only says the tools never guess)."""
    verify = write_verify_dir(tmp_path / "v", [{"ipc": ["12345"], "bns": ["316(2)"]}])
    statutes = write_statutes(tmp_path / "s.json")
    with pytest.raises((ValueError, KeyError, LookupError)):
        build_ipc_bns_edges(str(verify), str(statutes), str(tmp_path / "out.jsonl"))


def test_source_pairs_are_the_documented_five():
    """Self-check of the synthetic source: five pairs covering the five edge types."""
    assert len(PAIRS) == 5
