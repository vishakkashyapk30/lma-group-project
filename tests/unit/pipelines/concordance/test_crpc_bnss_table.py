"""The ten-row bail-related CrPC <-> BNSS table (plan §2, coded from the bare acts as tool configuration, not a dataset).

CrPC 436/436A/437/438/439 -> BNSS 478/479/480/482/483 are the five rows the plan names; the other five rows of
`configs/bail_sections.yaml` (default bail, notice of appearance, grounds of arrest, 24-hour production, the s.480 proviso)
are the skeleton's reading of "ten-row table" (docs/architecture/skeleton.md §3) and carry a week-0 verification TODO.
"""

from __future__ import annotations

import pytest
import yaml

from vakeel_sahayak.pipelines.concordance.crpc_bnss_table import load_bail_sections_table
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge

NAMED_PAIRS = [("436", "478"), ("436A", "479"), ("437", "480"), ("438", "482"), ("439", "483")]
OTHER_PAIRS = [("167(2)", "187(3)"), ("41A", "35(3)"), ("50", "47"), ("57", "58"), ("437(1) proviso", "480(1) proviso")]


@pytest.fixture()
def table() -> list[ConcordanceEdge]:
    return load_bail_sections_table()


@pytest.fixture()
def yaml_rows(configs_dir) -> list[dict]:
    return yaml.safe_load((configs_dir / "bail_sections.yaml").read_text(encoding="utf-8"))["rows"]


def test_table_has_ten_edges(table):
    """Plan §2: a ten-row table."""
    assert len(table) == 10
    assert all(isinstance(e, ConcordanceEdge) for e in table)


@pytest.mark.parametrize(("crpc", "bnss"), NAMED_PAIRS)
def test_named_bail_pairs_are_present(table, crpc, bnss):
    """CrPC 436/436A/437/438/439 -> BNSS 478/479/480/482/483 (plan §2)."""
    assert any(e.old_ref == f"CrPC {crpc}" and e.new_ref == f"BNSS {bnss}" for e in table)


@pytest.mark.parametrize(("crpc", "bnss"), OTHER_PAIRS)
def test_remaining_rows_cover_the_rights_radar_provisions(table, crpc, bnss):
    """The other five rows are the provisions the Rights Radar cites (Appendix C): 167(2)->187(3), 41A->35(3), 50->47, 57->58, 437 proviso."""
    assert any(e.old_ref == f"CrPC {crpc}" and e.new_ref == f"BNSS {bnss}" for e in table)


def test_table_matches_the_yaml_file_row_for_row(table, yaml_rows):
    """The loader returns exactly the configured rows, in file order, as 'CrPC <n>' -> 'BNSS <m>'."""
    assert [(e.old_ref, e.new_ref) for e in table] == [(f"CrPC {r['crpc']}", f"BNSS {r['bnss']}") for r in yaml_rows]


def test_every_edge_has_a_valid_type_and_no_edge_is_new(table):
    """Each CrPC section has a BNSS counterpart, so no row is NEW; the type is one of the five of plan §5.1."""
    assert all(isinstance(e.type, ConcordanceEdgeType) for e in table)
    assert all(e.type != ConcordanceEdgeType.NEW for e in table)


def test_old_and_new_refs_are_unique(table):
    """No CrPC section is mapped twice and no BNSS section is the target of two rows."""
    assert len({e.old_ref for e in table}) == 10
    assert len({e.new_ref for e in table}) == 10


def test_s479_is_not_a_plain_copy_of_s436a(table):
    """BNSS 479 adds the first-time-offender proviso (Appendix C), so CrPC 436A -> BNSS 479 is not SAME.

    ASSUMPTION: the table marks it REWORDED, as tests/fixtures/law/concordance.json does."""
    e = next(e for e in table if e.old_ref == "CrPC 436A")
    assert e.type == ConcordanceEdgeType.REWORDED


def test_s483_carries_over_s439(table):
    """CrPC 439 -> BNSS 483 (regular bail by the High Court) is SAME in the fixture and in plan §1.1 ('s.439 / BNSS s.483')."""
    e = next(e for e in table if e.old_ref == "CrPC 439")
    assert e.new_ref == "BNSS 483" and e.type == ConcordanceEdgeType.SAME
