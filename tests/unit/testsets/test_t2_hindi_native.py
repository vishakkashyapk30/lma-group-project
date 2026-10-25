"""Native Hindi High Court fallback for HLDC: the interim builder (`pipelines/hindi_native.py`) and the opt-in T2 source (origin `native_hc`)."""

from __future__ import annotations

import json
import re

import pytest

from tests.unit.testsets._helpers import read_rows, write_t1_dir
from vakeel_sahayak.pipelines import hindi_native
from vakeel_sahayak.testsets.blind import blind_hash
from vakeel_sahayak.testsets.t2_messy_bundles import build_t2, build_t2_with

HI = "यह जमानत प्रार्थना पत्र धारा 439 दण्ड प्रक्रिया संहिता के अन्तर्गत प्रस्तुत किया गया है। "
EN = "This is an application for bail under section 439 of the Code of Criminal Procedure. "


def make_shards(root, spec):
    """spec: {court: [[(case_id, [chunk texts])...] per shard]} written as small parquet files."""
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    for court, shards in spec.items():
        (root / court).mkdir(parents=True)
        for n, cases in enumerate(shards):
            rows = []
            for cid, chunks in cases:
                for i, t in enumerate(chunks):
                    rows.append(
                        {
                            "case_id": cid,
                            "chunk_index": i,
                            "text_original": t,
                            "court": f"{court.title()} High Court",
                            "title": f"A vs B {cid}",
                            "decision_date": "2023-05-04 00:00:00",
                            "year": 2023,
                        }
                    )
            pq.write_table(pa.Table.from_pylist(rows), root / court / f"rg-{n:05d}.parquet")


def test_devanagari_share_counts_letters_only():
    assert hindi_native.devanagari_share("१२३ ... !!") == 0.0
    assert hindi_native.devanagari_share("abcd") == 0.0
    assert hindi_native.devanagari_share("कखab") == 0.5


def test_build_filters_and_reports(tmp_path):
    raw = tmp_path / "judgments"
    hindi = HI * 20
    make_shards(
        raw,
        {
            "allahabad": [
                [
                    ("ok1", [hindi, hindi]),
                    ("english", [EN * 30]),
                    ("short", [HI * 2]),
                    ("leak", [hindi]),
                    ("mixed", [hindi, EN * 60]),
                ],
                [("ok2", [hindi + " ", hindi + "x"])],
            ],
            "bombay": [[("ok3", [hindi * 2])]],
        },
    )
    # one dev order of splits.json, one T1 case, one sealed blind id by hash, and a duplicate text
    splits = tmp_path / "splits.json"
    splits.write_text(json.dumps({"leak": "dev", "ok1": "train"}))
    t1 = tmp_path / "t1"
    t1.mkdir()
    (t1 / "cases.jsonl").write_text(json.dumps({"case_id": "t1-000", "doc_id": "ok2"}) + "\n")
    (t1 / "dev.jsonl").write_text("")
    (t1 / "manifest_blind.json").write_text(json.dumps({"hashes": [blind_hash("ok3")]}))
    report = hindi_native.build(str(raw), str(tmp_path / "out.jsonl"), str(splits), str(t1))
    rows = read_rows(tmp_path / "out.jsonl")
    assert [r["case_id"] for r in rows] == ["ok1"]
    assert (
        report["kept"] == 1
        and report["dropped_leakage"] == 3
        and report["dropped_short"] == 1
        and report["dropped_low_share"] == 1
    )
    r = rows[0]
    assert (
        r["court"] == "Allahabad High Court"
        and r["year"] == 2023
        and r["decision_date"] == "2023-05-04"
        and r["devanagari_share"] >= 0.5
    )
    assert r["text"] == hindi + "\n" + hindi and r["source_shard"].endswith("rg-00000.parquet")
    assert report["per_court"] == {"Allahabad High Court": 1} and report["per_court_year"]["Allahabad High Court"] == {
        "2023": 1
    }


def test_build_deduplicates_identical_text(tmp_path):
    raw = tmp_path / "judgments"
    hindi = HI * 20
    make_shards(raw, {"allahabad": [[("a", [hindi]), ("b", [hindi])]]})
    report = hindi_native.build(str(raw), str(tmp_path / "o.jsonl"))
    assert report["kept"] == 1 and report["dropped_duplicate"] == 1


def native_file(tmp_path, n=6):
    rows = [
        {
            "case_id": f"UP{i:04d}",
            "court": "Allahabad High Court",
            "year": 2022 + i % 2,
            "decision_date": f"2022-01-0{i % 9 + 1}",
            "title": "t",
            "text": (HI * 30) + str(i),
        }
        for i in range(n)
    ]
    f = tmp_path / "hindi_native.jsonl"
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return f


def test_native_bundles_are_opt_in_and_tagged(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=4)
    native = native_file(tmp_path)
    out = tmp_path / "t2n"
    m = build_t2_with(str(t1), None, None, str(out), n_cases=0, native_path=str(native))
    truth = read_rows(out / "truth.jsonl")
    assert m.size == len(truth) == 6 and m.details["hindi_native"]["documents"] == 6
    for t in truth:
        assert (
            t["origin"] == "native_hc"
            and t["bundle_id"].startswith("hnat-")
            and t["kind"] == "K5"
            and t["text_layer"] == "exact"
        )
        assert t["documents"] == [{"doc_id": "d1", "type": "COURT_JUDGMENT_HI", "pages": [1, len(t["pages"])]}]
        assert re.search("[ऀ-ॿ]", t["pages"][0]["text"]) and t["source"]["court"] == "Allahabad High Court"
        assert (out / t["pdf"]).is_file()
    # seeded and repeatable
    out2 = tmp_path / "t2n2"
    build_t2_with(str(t1), None, None, str(out2), n_cases=0, native_path=str(native))
    assert (out / "truth.jsonl").read_bytes() == (out2 / "truth.jsonl").read_bytes()


def test_default_t2_output_is_unchanged_without_native(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=4)
    a, b = tmp_path / "a", tmp_path / "b"
    build_t2(str(t1), None, None, str(a))
    build_t2_with(str(t1), None, None, str(b), native_path=None)
    ra = read_rows(a / "truth.jsonl")
    assert (a / "truth.jsonl").read_bytes() == (b / "truth.jsonl").read_bytes()
    assert (
        not any("origin" in r for r in ra)
        and "hindi_native" not in json.loads((a / "manifest.json").read_text())["details"]
    )


def test_native_added_to_the_full_set_keeps_the_other_rows(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=4)
    native = native_file(tmp_path, n=3)
    a, b = tmp_path / "a", tmp_path / "b"
    build_t2_with(str(t1), None, None, str(a), n_cases=3)
    build_t2_with(str(t1), None, None, str(b), n_cases=3, native_path=str(native))
    ra, rb = read_rows(a / "truth.jsonl"), read_rows(b / "truth.jsonl")
    assert len(rb) == len(ra) + 3 and [r["bundle_id"] for r in rb if not r["bundle_id"].startswith("hnat-")] == [
        r["bundle_id"] for r in ra
    ]


def test_supreme_court_rows_are_not_kept(tmp_path):
    raw = tmp_path / "judgments"
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    (raw / "supreme-court").mkdir(parents=True)
    row = {
        "case_id": "sc1",
        "chunk_index": 0,
        "text_original": HI * 20,
        "court": "Supreme Court of India",
        "title": "t",
        "decision_date": "2013-01-01",
        "year": 2013,
    }
    pq.write_table(pa.Table.from_pylist([row]), raw / "supreme-court" / "rg-00000.parquet")
    report = hindi_native.build(str(raw), str(tmp_path / "o.jsonl"))
    assert report["kept"] == 0 and report["dropped_not_high_court"] == 1
