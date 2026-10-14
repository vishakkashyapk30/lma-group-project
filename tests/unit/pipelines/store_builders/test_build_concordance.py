"""Builder of `law.concordance` (plan §5.1, §2): IPC <-> BNS and CrPC <-> BNSS edges typed same / split / merged / reworded /
new, with a text diff, in a graph. The ten-row bail table (CrPC 436/436A/437/438/439 -> BNSS 478/479/480/482/483 and five more)
is part of the graph. Exclusion sets do not apply (sections are not orders)."""

from __future__ import annotations

import pytest

from tests.fakes.data import load_concordance
from vakeel_sahayak.pipelines.store_builders.build_concordance import build_concordance
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType, StoreName
from vakeel_sahayak.stores.law_concordance import ConcordanceStore

FIXTURE_PAIRS = {(e.old_ref, e.new_ref) for e in load_concordance()}
BAIL_PAIRS = {("CrPC 436", "BNSS 478"), ("CrPC 436A", "BNSS 479"), ("CrPC 437", "BNSS 480"), ("CrPC 438", "BNSS 482"),
              ("CrPC 439", "BNSS 483")}


@pytest.fixture()
def built(interim, tmp_path):
    out = tmp_path / "concordance"
    n = build_concordance(str(interim), str(out))
    store = ConcordanceStore()
    store.open(str(out))
    yield n, store
    store.close()


def test_store_identity():
    assert ConcordanceStore.name == StoreName.LAW_CONCORDANCE


def test_edge_count_matches_the_store(built):
    """The return value is the number of edges written. ASSUMPTION: the interim edges plus the ten-row bail table, de-duplicated by (old_ref, new_ref)."""
    n, store = built
    assert n == store.count()
    assert n >= len(FIXTURE_PAIRS)


def test_ipc_420_edge_is_reworded_with_a_diff(built):
    _, store = built
    (edge,) = [e for e in store.edges_for("IPC 420") if e.new_ref == "BNS 318(4)"]
    assert edge.type == ConcordanceEdgeType.REWORDED
    assert edge.text_diff


def test_split_edges_come_out_of_one_old_section(built):
    _, store = built
    assert {e.new_ref for e in store.edges_for("IPC 999")} == {"BNS 888(1)", "BNS 888(2)"}
    assert {e.type for e in store.edges_for("IPC 999")} == {ConcordanceEdgeType.SPLIT}


def test_merged_edges_meet_in_one_new_section(built):
    _, store = built
    assert {e.old_ref for e in store.edges_for("BNS 666")} == {"IPC 777", "IPC 778"}


@pytest.mark.parametrize(("old", "new"), sorted(BAIL_PAIRS))
def test_bail_table_edges_are_in_the_graph(built, old, new):
    """Plan §2: the bail-related CrPC/BNSS table is part of `law.concordance` (via `map_section`)."""
    _, store = built
    assert any(e.new_ref == new for e in store.edges_for(old))


def test_family_expansion_links_old_and_new_sections(built):
    """Used for `section_family` (plan §5.2): the family of IPC 420 contains BNS 318(4) and the other way round."""
    _, store = built
    assert {"IPC 420", "BNS 318(4)"} <= set(store.family("IPC 420"))
    assert {"IPC 420", "BNS 318(4)"} <= set(store.family("BNS 318(4)"))


def test_no_duplicate_edges(built):
    _, store = built
    edges = store.edges_for("CrPC 439")
    assert len({(e.old_ref, e.new_ref) for e in edges}) == len(edges)
