"""The First Schedule lookup Peshkar uses for a charged section's bail class and maximum punishment.

The values asserted here are the printed First Schedule entries (CrPC 1973 Part I; BNSS 2023), read by script into
`configs/first_schedule_*.jsonl`; the first four are among the 43 IPC sections whose bail flag the 26 Oct statute store
has the wrong way round (`docs/handoff/first-schedule.md`).
"""

import json

import pytest

from vakeel_sahayak.config import resolve_config_dir
from vakeel_sahayak.pipelines.first_schedule import _table, classify, classify_other_law, part2_rows


@pytest.mark.parametrize(
    ("section", "bailable", "punishment"),
    [
        ("364", False, "life"),  # kidnapping in order to murder: the old store says bailable
        ("365", False, "7 years"),
        ("452", False, "7 years"),
        ("457", False, "14 years"),
        ("302", False, "death"),
        ("143", True, "6 months"),
        ("332", False, "3 years"),
        ("353", False, "2 years"),
    ],
)
def test_ipc_sections_read_as_printed(section, bailable, punishment):
    assert classify("IPC", section) == (bailable, punishment)


def test_a_bns_sub_section_is_read_from_its_sub_row():
    assert classify("BNS", "318(4)") == (False, "7 years")
    assert classify("BNS", "318(2)") == (True, "3 years")
    assert classify("BNS", "318")[0] is None  # sub-sections differ, so the section as a whole has no single bail class


def test_unknown_codes_sections_and_a_missing_table_give_nothing(tmp_path):
    assert classify("NDPS", "22") == (None, None)
    assert classify("IPC", "99999") == (None, None)
    assert classify("IPC", "not a section") == (None, None)
    assert classify("IPC", "302", config_dir=str(tmp_path)) == (None, None)


def test_every_row_names_its_official_source():
    for code in ("IPC", "BNS"):
        rows = _table(code, str(resolve_config_dir()))
        assert len(rows) > 250
        assert all(r["source"] for r in rows.values())
    meta = json.loads((resolve_config_dir() / "first_schedule_crpc_ipc.meta.json").read_text())
    assert meta["source_sha256"]


# ---- Part II (offences against other laws): `configs/first_schedule_part2.jsonl`, CrPC 1973 and BNSS 2023


@pytest.mark.parametrize(
    ("punishment", "want"),
    [
        ("20 years", False),  # more than 7 years
        ("10 years", False),
        ("7 years", False),  # 3 years and upwards but not more than 7
        ("3 years", False),
        ("2 years", True),  # less than 3 years
        ("1 year", True),
        ("6 months", True),
        ("fine", True),  # fine only
        ("death", False),
        ("life", False),
        ("life imprisonment", False),
        ("imprisonment for life", False),
        (None, None),
        ("", None),
        ("same as for the offence abetted", None),
    ],
)
def test_classify_other_law_reads_the_part2_bands(punishment, want):
    assert classify_other_law(punishment) is want


def test_classify_other_law_without_the_table_gives_nothing(tmp_path):
    assert classify_other_law("20 years", config_dir=str(tmp_path)) is None


def test_part2_rows_of_the_crpc_and_the_bnss_agree():
    """The code reads the BNSS rows; the CrPC 1973 prints the same bands and classes (it writes 'Ditto' where the BNSS spells them out)."""
    keys = ("band", "death", "life", "fine_only", "min_years", "min_inclusive", "max_years", "max_inclusive", "cognisable", "bailable", "triable_by")
    config = str(resolve_config_dir())
    crpc, bnss = part2_rows(config, "CrPC 1973"), part2_rows(config, "BNSS 2023")
    assert len(crpc) == len(bnss) == 3
    assert [[r[k] for k in keys] for r in crpc] == [[r[k] for k in keys] for r in bnss]
    assert [r["band"] for r in bnss] == ["death_life_or_more_than_7", "3_to_7", "less_than_3_or_fine"]
    assert [r["bailable"] for r in bnss] == [False, False, True]
    assert [r["cognisable"] for r in bnss] == [True, True, False]
    assert [r["triable_by"] for r in bnss] == ["Court of Session", "Magistrate of the first class", "Any Magistrate"]
    assert all(r["source"]["sha256"] for r in crpc + bnss)
