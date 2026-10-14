"""`map_section` and the concordance bridge (plan §2 bail table, §5.1 law.concordance, §5.4).

Examples from the plan: IPC 420 <-> BNS 318(4) (case-0007); CrPC 436/436A/437/438/439 -> BNSS 478/479/480/482/483 and the
rest of the ten-row bail table (configs/bail_sections.yaml). The offence date decides the era (BNS era = offence on or after
2024-07-01). Unclear mappings are AMBIGUOUS, never guessed.

Store-level tests build a ConcordanceStore from rows. # ASSUMPTION: `ConcordanceStore.build(source_dir, out_dir)` reads
`source_dir/concordance_edges.jsonl` with one `ConcordanceEdge` JSON object per line, and `open(path)` takes `out_dir`.
Tool-level tests use the in-memory fake store through `install_stores()`.
"""

import pytest
import yaml

from tests.unit.tools_law_case._helpers import assert_tool_error, write_jsonl
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType, StoreName
from vakeel_sahayak.stores.law_concordance import ConcordanceStore
from vakeel_sahayak.tools.law.concordance import MAP_SECTION_SPEC, TRANSFER_CHECK_SPEC, map_section
from vakeel_sahayak.tools.types import MapSectionResult

BNS_ERA_OFFENCE = "2024-08-10"  # case-0007 offence date


def bail_rows(configs_dir):
    cfg = yaml.safe_load((configs_dir / "bail_sections.yaml").read_text(encoding="utf-8"))
    return cfg["rows"]


@pytest.fixture()
def concordance_store(tmp_path, concordance_edges, configs_dir):
    """A ConcordanceStore built from the tiny fixture edges plus the ten-row bail table."""
    edges = [e.model_dump(mode="json") for e in concordance_edges]
    for row in bail_rows(configs_dir):
        edges.append({"old_ref": f"CrPC {row['crpc']}", "new_ref": f"BNSS {row['bnss']}", "type": "REWORDED", "text_diff": ""})
    # the fixture already has CrPC 439 / 436A rows; drop duplicates so each old_ref maps once
    seen, unique = set(), []
    for e in edges:
        key = (e["old_ref"], e["new_ref"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    write_jsonl(src / "concordance_edges.jsonl", unique)
    store = ConcordanceStore()
    store.build(str(src), str(out))
    store.open(str(out))
    return store


# ---------------------------------------------------------------- pass-today facts
def test_specs():
    """map_section is used by Peshkar, Sutradhar and Vakeel; transfer_check by Sutradhar and Vakeel; both read law.concordance."""
    assert {a.value for a in MAP_SECTION_SPEC.agents} == {"PESHKAR", "SUTRADHAR", "VAKEEL"}
    assert {a.value for a in TRANSFER_CHECK_SPEC.agents} == {"SUTRADHAR", "VAKEEL"}
    assert [s for s in MAP_SECTION_SPEC.stores] == [StoreName.LAW_CONCORDANCE]


def test_bail_table_has_the_ten_rows_and_the_five_named_pairs(configs_dir):
    """Plan §2: ten-row table including CrPC 436/436A/437/438/439 -> BNSS 478/479/480/482/483."""
    rows = bail_rows(configs_dir)
    assert len(rows) == 10
    pairs = {(r["crpc"], r["bnss"]) for r in rows}
    assert {("436", "478"), ("436A", "479"), ("437", "480"), ("438", "482"), ("439", "483")} <= pairs


# ---------------------------------------------------------------- store-level semantics (fail until implemented)
@pytest.mark.parametrize(
    ("code", "section", "equivalent", "edge"),
    [
        ("IPC", "420", "BNS 318(4)", ConcordanceEdgeType.REWORDED),
        ("BNS", "318(4)", "IPC 420", ConcordanceEdgeType.REWORDED),
        ("IPC", "406", "BNS 316(2)", ConcordanceEdgeType.SAME),
        ("CrPC", "439", "BNSS 483", ConcordanceEdgeType.SAME),
        ("BNSS", "483", "CrPC 439", ConcordanceEdgeType.SAME),
    ],
)
def test_store_maps_both_directions(concordance_store, code, section, equivalent, edge):
    """IPC 420 <-> BNS 318(4) and CrPC 439 <-> BNSS 483, with the edge type; not ambiguous."""
    res = concordance_store.map_section(code, section, BNS_ERA_OFFENCE)
    assert isinstance(res, MapSectionResult)
    assert res.equivalent == equivalent
    assert res.edge_type == edge
    assert res.ambiguous is False


def test_store_maps_the_whole_bail_table(concordance_store, configs_dir):
    """Every row of the ten-row bail table maps CrPC -> BNSS and back."""
    for row in bail_rows(configs_dir):
        fwd = concordance_store.map_section("CrPC", row["crpc"], BNS_ERA_OFFENCE)
        assert fwd.equivalent == f"BNSS {row['bnss']}", row
        back = concordance_store.map_section("BNSS", row["bnss"], BNS_ERA_OFFENCE)
        assert back.equivalent == f"CrPC {row['crpc']}", row


def test_split_section_is_ambiguous_with_candidates(concordance_store):
    """A split provision (synthetic IPC 999 -> BNS 888(1)/(2)) is AMBIGUOUS and lists the candidates, no guess."""
    res = concordance_store.map_section("IPC", "999", BNS_ERA_OFFENCE)
    assert res.ambiguous is True
    assert res.equivalent is None
    assert set(res.candidates) == {"BNS 888(1)", "BNS 888(2)"}
    assert res.edge_type == ConcordanceEdgeType.SPLIT


def test_merged_sections_map_forward_but_ambiguous_backward(concordance_store):
    """Two IPC sections merged into BNS 666: forward is clear (ASSUMPTION), backward is ambiguous."""
    fwd = concordance_store.map_section("IPC", "777", BNS_ERA_OFFENCE)
    assert fwd.equivalent == "BNS 666" and fwd.edge_type == ConcordanceEdgeType.MERGED and not fwd.ambiguous
    back = concordance_store.map_section("BNS", "666", BNS_ERA_OFFENCE)
    assert back.ambiguous is True and set(back.candidates) == {"IPC 777", "IPC 778"}


def test_unknown_section_is_never_guessed(concordance_store):
    """A section not in the graph returns no equivalent and is flagged ambiguous."""
    res = concordance_store.map_section("IPC", "12345", BNS_ERA_OFFENCE)
    assert res.equivalent is None and res.ambiguous is True


@pytest.mark.parametrize("offence_date", ["2024-06-30", "2024-07-01", "2024-08-10"])
def test_equivalent_is_the_same_across_the_era_boundary(concordance_store, offence_date):
    """The concordance equivalent of IPC 420 does not depend on the date (the date decides which law governs, not the map)."""
    assert concordance_store.map_section("IPC", "420", offence_date).equivalent == "BNS 318(4)"


def test_family_expansion(concordance_store):
    """section_family for IPC 420 contains the BNS equivalent (plan §5.2)."""
    fam = concordance_store.family("IPC 420")
    assert "IPC 420" in fam and "BNS 318(4)" in fam


# ---------------------------------------------------------------- tool-level (via the fake store)
def test_tool_passes_through_the_store(install_stores):
    """map_section tool returns the concordance store's answer: IPC 420 -> BNS 318(4) for the case-0007 offence date."""
    install_stores()
    res = map_section("IPC", "420", BNS_ERA_OFFENCE)
    assert res.equivalent == "BNS 318(4)"


@pytest.mark.parametrize(
    "args",
    [("XYZ", "420", BNS_ERA_OFFENCE), ("IPC", "", BNS_ERA_OFFENCE), ("IPC", "420", "10-08-2024"), ("IPC", "420", "")],
)
def test_tool_validates_arguments(install_stores, args):
    """Unknown code, empty section or a malformed offence date is an error even though calls are schema-constrained."""
    install_stores()
    assert_tool_error(lambda: map_section(*args))
