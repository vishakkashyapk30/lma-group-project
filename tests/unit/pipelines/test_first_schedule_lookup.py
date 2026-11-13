"""The First Schedule lookup Peshkar uses for a charged section's bail class and maximum punishment.

The values asserted here are the printed First Schedule entries (CrPC 1973 Part I; BNSS 2023), read by script into
`configs/first_schedule_*.jsonl`; the first four are among the 43 IPC sections whose bail flag the 26 Oct statute store
has the wrong way round (`docs/handoff/first-schedule.md`).
"""

import json

import pytest

from vakeel_sahayak.config import resolve_config_dir
from vakeel_sahayak.pipelines.first_schedule import _table, classify


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
