"""Streaming subset of Open India Law (`oil_fetch`): candidate selection per row group, resumability, checksum check. No network (local source)."""

from __future__ import annotations

import json

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

from tests.unit.pipelines.test_oil_ingest import BAIL_BODY, chunks_of  # noqa: E402
from vakeel_sahayak.pipelines import oil_fetch as of  # noqa: E402


def write_court_file(folder, stem, rows, row_group_size):
    path = folder / f"in_{stem}_judgments.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=row_group_size)
    return path


@pytest.fixture()
def source(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    rows = (
        chunks_of("A1", BAIL_BODY, title="BAIL APPLN./1/2024 of A Vs State")
        + chunks_of("A2", "A suit about a lease. " * 30, title="CS/2/2024 of B Vs C")
        + chunks_of("A3", BAIL_BODY, title="BAIL APPLN./3/2010 of D Vs State", date="2010-05-05 00:00:00")  # before 2019
        + chunks_of("A4", "The petitioner seeks bail under Section 439 Cr.P.C. in a murder case. " * 3, title="CRM-M/4/2023 of E Vs State", date="2023-03-03 00:00:00")
    )
    write_court_file(src, "delhi", rows, row_group_size=7)
    return src


def test_row_group_selection_keeps_only_window_and_bail_candidates(source, tmp_path):
    out = tmp_path / "raw"
    result = of.process_file("delhi", out, str(source))
    assert result["row_groups_done"] == result["row_groups_total"]
    kept = set()
    for shard in (out / "judgments" / "delhi").glob("rg-*.parquet"):
        kept |= {r["case_id"] for r in pq.read_table(shard).to_pylist()}
    assert kept == {"A1", "A4"}, "a non-bail suit and a pre-2019 order must not be kept"
    assert result["cases_kept"] >= 2


def test_text_column_is_not_copied_only_the_chunk_body(source, tmp_path):
    out = tmp_path / "raw"
    of.process_file("delhi", out, str(source))
    shard = next((out / "judgments" / "delhi").glob("rg-*.parquet"))
    names = pq.read_table(shard).schema.names
    assert "text_original" in names
    assert "text" not in names


def test_second_run_skips_finished_row_groups(source, tmp_path):
    out = tmp_path / "raw"
    of.process_file("delhi", out, str(source))
    shards = sorted((out / "judgments" / "delhi").glob("rg-*.parquet"))
    mtimes = [p.stat().st_mtime_ns for p in shards]
    again = of.process_file("delhi", out, str(source))
    assert [p.stat().st_mtime_ns for p in sorted((out / "judgments" / "delhi").glob("rg-*.parquet"))] == mtimes
    assert again["row_groups_done"] == again["row_groups_total"]


def test_limit_groups_makes_a_pilot_and_the_rest_resumes(source, tmp_path):
    out = tmp_path / "raw"
    pilot = of.process_file("delhi", out, str(source), limit_groups=1)
    assert pilot["row_groups_done"] == 1
    full = of.process_file("delhi", out, str(source))
    assert full["row_groups_done"] == full["row_groups_total"] > 1
    state = json.loads((out / "state" / "delhi.json").read_text())
    assert len(state["groups"]) == full["row_groups_total"]


def test_supreme_court_candidates_need_several_bail_mentions(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    long_bail = "The question is whether bail should be granted under Section 439 Cr.P.C. " * 6
    rows = chunks_of("S1", long_bail, title="X v. State", court="Supreme Court of India", date="1999-01-01 00:00:00") + chunks_of(
        "S2", "A tax appeal. Bail is mentioned once under Section 439 Cr.P.C.", title="Y v. Z", court="Supreme Court of India", date="2001-01-01 00:00:00"
    )
    write_court_file(src, "supreme-court", rows, row_group_size=100)
    out = tmp_path / "raw"
    of.process_file("supreme-court", out, str(src))
    kept = {r["case_id"] for shard in (out / "judgments" / "supreme-court").glob("rg-*.parquet") for r in pq.read_table(shard).to_pylist()}
    assert kept == {"S1"}


def test_sc_metadata_has_one_row_per_case(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    rows = chunks_of("S1", BAIL_BODY, title="X v. State", court="Supreme Court of India", date="1999-01-01 00:00:00", citation="(1999) 1 SCC 1")
    write_court_file(src, "supreme-court", rows, row_group_size=3)
    out = tmp_path / "raw"
    out.mkdir()
    info = of.fetch_sc_metadata(out, str(src), workers=2)
    lines = [json.loads(x) for x in (out / "sc_metadata.jsonl").read_text(encoding="utf-8").splitlines()]
    assert info["rows"] == len(lines) == 1
    assert lines[0]["citations"] == ["(1999) 1 SCC 1"]
    assert lines[0]["date"] == "1999-01-01"


def test_sc_metadata_adds_the_neutral_citation_from_the_case_id(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    rows = chunks_of("2011_INSC_772", BAIL_BODY, title="A versus B", court="Supreme Court of India", date="2011-10-20 00:00:00")
    write_court_file(src, "supreme-court", rows, row_group_size=50)
    out = tmp_path / "raw"
    out.mkdir()
    of.fetch_sc_metadata(out, str(src), workers=1)
    row = json.loads((out / "sc_metadata.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert "2011 INSC 772" in row["citations"]
