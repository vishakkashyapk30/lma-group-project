"""Open India Law ingest (plan §2 source 1): reassembly, the bail test, the sensitive-matter filter, orders.jsonl and statutes.jsonl.

The fixtures are tiny Parquet files with the real schema of the release `v2026.08.1` (judgment chunks: `case_id`, `chunk_index`,
`total_chunks`, `text_original`, `char_start`, `char_end`, `title`, `decision_date`...; legislation: `act_id`, `chunk_id`, `title`,
`section_number`, `text` behind an "Act: ... | Section N: Title" header). No network is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq  # noqa: E402

from tests.unit.pipelines._helpers import read_json  # noqa: E402
from vakeel_sahayak.pipelines import oil_ingest as oi  # noqa: E402

BAIL_BODY = (
    "IN THE HIGH COURT OF DELHI\n\nBAIL APPLN. 1234/2024\n\nThe petitioner seeks regular bail under Section 483 BNSS in FIR No. 55/2024 "
    "dated 12.08.2024 registered at P.S. Rohini under Section 318(4) BNS.\n\n"
    "Learned counsel for the petitioner submits that the petitioner is innocent and has been in custody for four months.\n\n"
    "Learned APP for the State opposes the bail application and submits that the allegations are serious.\n\n"
    "Having heard the learned counsel and perused the record, this Court is of the view that the petitioner is entitled to bail.\n\n"
    "The bail application is allowed. The petitioner shall be released on bail on furnishing a personal bond."
)


def chunks_of(case_id: str, text: str, *, title: str, court: str = "High Court of Delhi", date: str = "2024-09-02 00:00:00",
              size: int = 200, overlap: int = 30, drop: int | None = None, **extra: Any) -> list[dict[str, Any]]:
    """Cut `text` into overlapping chunks the way the release does (`char_start` of a chunk lies before the previous `char_end`)."""
    pieces, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        pieces.append((start, end))
        if end == len(text):
            break
        start = end - overlap
    rows = []
    for i, (a, b) in enumerate(pieces):
        rows.append(
            {
                "case_id": case_id, "chunk_id": f"{case_id}_{i}", "chunk_index": i, "total_chunks": len(pieces),
                "text_original": text[a:b], "char_start": a, "char_end": b, "section_type": "body", "court": court,
                "court_code": "7_26", "bench": "delhi_hc", "bench_strength": 1, "judges": ["A. B. Judge"], "title": title,
                "petitioner": "A", "respondent": "State", "disposition": "ALLOWED", "case_number": "1234 of 2024",
                "citation": "", "decision_date": date, "date_of_registration": "01-01-2024", "year": 2024,
                "source_url": f"https://example.org/{case_id}.pdf", **extra,
            }
        )
    if drop is not None:
        rows = [r for r in rows if r["chunk_index"] != drop]
    return rows


def write_shard(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


@pytest.fixture()
def raw_dir(tmp_path):
    raw = tmp_path / "raw"
    rows = (
        chunks_of("DLHC01", BAIL_BODY, title="BAIL APPLN./1234/2024 of A Vs State")
        + chunks_of("DLHC02", BAIL_BODY.replace("BAIL APPLN. 1234/2024", "W.P.(CRL) 9/2024"), title="W.P.(CRL)/9/2024 of B Vs State")
        + chunks_of("DLHC03", "Civil suit about a lease. " * 40, title="CS/5/2024 of C Vs D")
        + chunks_of("DLHC04", BAIL_BODY + "\n\nThe accused is charged under Section 376 IPC.", title="BAIL APPLN./7/2024 of E Vs State")
        + chunks_of("DLHC05", BAIL_BODY, title="BAIL APPLN./8/2024 of F Vs State", drop=1)
        + chunks_of("DLHC06", BAIL_BODY, title="BAIL APPLN./9/2024 of G Vs State", date="not a date")
    )
    write_shard(raw / "judgments" / "delhi" / "rg-00000.parquet", rows)
    return raw


# ---- reassembly and cleaning ---------------------------------------------------------------------------------------
def test_reassemble_removes_the_overlap_between_chunks():
    rows = chunks_of("X", BAIL_BODY, title="BAIL APPLN./1/2024 of A Vs B")
    assert len(rows) > 3
    text, complete = oi.reassemble(list(reversed(rows)))
    assert complete
    assert text == BAIL_BODY


def test_reassemble_flags_a_missing_chunk():
    rows = chunks_of("X", BAIL_BODY, title="BAIL APPLN./1/2024 of A Vs B", drop=2)
    assert oi.reassemble(rows)[1] is False


def test_clean_text_strips_markdown_markers_and_rules():
    raw = "[TITLE] # THE HIGH COURT\n\n[SECTION] ## DATED : 7th OCTOBER\n\n-----------------------\n\n\n\nBody text."
    assert oi.clean_text(raw) == "THE HIGH COURT\n\nDATED : 7th OCTOBER\n\nBody text."


# ---- the bail test ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("title", "text", "basis"),
    [
        ("BAIL APPLN./8/2016 of A Vs State", "anything", "case_type"),
        ("Crl.M.C./5/2020 of A Vs State", "Petition under 439 Cr.P.C. for regular bail.", "keyword"),
        ("CRM-M/5/2020 of A Vs State", "The petitioner prays for anticipatory bail.", "bail_section"),
        ("CS/5/2024 of A Vs B", "A suit about a lease. The bail bond of the contractor is mentioned.", "no"),
    ],
)
def test_is_bail_order_basis(title, text, basis):
    selected, got = oi.is_bail_order(title, text, oi.DEFAULT_KEYWORDS)
    assert got == basis
    assert selected is (basis != "no")


def test_case_type_is_the_title_prefix():
    assert oi.case_type_of("BAIL APPLN./8/2016 of Jacob Rai Vs State Of Sikkim") == "BAIL APPLN."


def test_sc_judgment_needs_several_bail_mentions():
    assert oi.is_bail_judgment("bail " * 5 + "under Section 439 Cr.P.C.")
    assert not oi.is_bail_judgment("bail once, Section 439 Cr.P.C.")


# ---- sensitive matters -------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Bail under Section 376 IPC is sought.", "sexual_offence"),
        ("Offence under the POCSO Act, bail sought.", "pocso"),
        ("The applicant is a Juvenile in conflict with law before the JJB; bail sought.", "juvenile"),
        ("The prosecutrix alleged that the applicant, bail sought, ...", "sexual_offence_keyword"),
        ("Bail under Section 420 IPC and 406 IPC is sought.", None),
    ],
)
def test_declined_reason(text, reason):
    assert oi.declined_reason("BAIL APPLN./1/2024 of A Vs State", text) == reason


# ---- FIR and offence date ----------------------------------------------------------------------------------------
def test_offence_date_prefers_the_incident_date():
    text = "The incident took place on 05.08.2024. FIR No. 12/2024 dated 06.08.2024 under Section 103 BNS."
    assert oi.extract_offence_date(text) == ("2024-08-05", "incident")


def test_fir_date_before_the_bns_date_is_an_ipc_era_offence():
    iso, source = oi.extract_offence_date("FIR No. 77/2023 dated 10.03.2023 under Section 420 IPC.")
    assert (iso, source) == ("2023-03-10", "fir_date")


def test_fir_date_after_the_bns_date_with_ipc_sections_gives_no_offence_date():
    text = "FIR No. 80/2024 dated 10.07.2024 was registered under Section 420 IPC."
    assert oi.extract_offence_date(text) == (None, None)


# ---- orders.jsonl ----------------------------------------------------------------------------------------------------
def test_select_bail_orders_keeps_only_complete_nonsensitive_bail_orders(raw_dir, tmp_path):
    out = tmp_path / "interim"
    n = oi.select_bail_orders(str(raw_dir), str(out))
    rows = [json.loads(line) for line in (out / "orders.jsonl").read_text(encoding="utf-8").splitlines()]
    assert n == len(rows) == 2
    assert {r["doc_id"] for r in rows} == {"DLHC01", "DLHC02"}
    counts = read_json(out / "ingest_report.json")["orders"]["counts"]
    assert counts["dropped_not_bail"] == 1
    assert counts["declined_sexual_offence"] == 1
    assert counts["dropped_incomplete"] == 1
    assert counts["dropped_no_date"] == 1


def test_order_record_has_the_fields_the_corpus_reader_expects(raw_dir, tmp_path):
    from vakeel_sahayak.pipelines.store_builders.corpus import load_orders

    out = tmp_path / "interim"
    oi.select_bail_orders(str(raw_dir), str(out))
    orders, skipped = load_orders(str(out))
    assert skipped == {}
    first = next(o for o in orders if o.doc_id == "DLHC01")
    assert first.date == "2024-09-02"
    assert first.court == "Delhi High Court"
    assert first.text.startswith("IN THE HIGH COURT OF DELHI")
    assert first.bench_size == 1
    assert first.offence_date == "2024-08-12"
    rec = next(json.loads(line) for line in (out / "orders.jsonl").read_text(encoding="utf-8").splitlines() if '"DLHC01"' in line)
    assert rec["fir_key"]
    assert rec["source"]["dataset"] == "vaquill/open-india-law"
    assert rec["source"]["licence"] == "CC BY 4.0"
    assert rec["selection_basis"] == "case_type"


def test_ingest_is_resumable_and_deterministic(raw_dir, tmp_path):
    out = tmp_path / "interim"
    oi.select_bail_orders(str(raw_dir), str(out))
    first = (out / "orders.jsonl").read_bytes()
    cache = next((out / ".oil_shards").glob("*.jsonl.gz"))
    mtime = cache.stat().st_mtime_ns
    oi.select_bail_orders(str(raw_dir), str(out))
    assert (out / "orders.jsonl").read_bytes() == first
    assert cache.stat().st_mtime_ns == mtime, "the cached shard was recomputed"


def test_court_names_are_canonical_whatever_the_release_spells():
    assert oi.canonical_court("punjab-and-haryana") == "Punjab and Haryana High Court"
    assert oi.canonical_court("delhi") == "Delhi High Court"
    assert oi.canonical_court("supreme-court") == "Supreme Court of India"


def _row(doc_id, court, date, clean=False, bns=False, mentions=0):
    return {"doc_id": doc_id, "court": court, "date": date, "clean_split": clean, "bns_era": bns, "bail_mentions": mentions}


def test_sampling_keeps_the_evaluation_pool_and_caps_the_rest():
    """Per court and year only `cap` ordinary orders stay, but every clean dev/test-window order and every BNS-era order is kept."""
    windows = {"dev": {"from": "2024-01-01", "to": "2024-04-01"}, "test": {"from": "2024-06-01", "to": "2025-12-31"}}
    rows = [_row(f"a{i}", "Delhi High Court", "2022-05-05") for i in range(50)]
    rows += [_row(f"c{i}", "Delhi High Court", "2024-08-01", clean=True) for i in range(5)]
    rows += [_row(f"u{i}", "Delhi High Court", "2024-08-01", clean=False) for i in range(50)]
    rows += [_row("bns", "Delhi High Court", "2024-09-01", clean=True, bns=True)]
    kept, counts = oi.choose_kept(rows, 10, 2, 1980, windows)
    assert sum(1 for i in range(50) if f"a{i}" in kept) == 10
    assert all(f"c{i}" in kept for i in range(5))
    assert "bns" in kept
    assert sum(1 for i in range(50) if f"u{i}" in kept) == 4  # 2024: cap 10 minus 6 must-keep orders
    assert counts["hc_kept_must_keep"] == 6


def test_sampling_takes_the_supreme_court_judgments_with_most_bail_mentions():
    windows = {"dev": {}, "test": {}}
    rows = [_row(f"s{i}", "Supreme Court of India", "2015-01-01", mentions=i) for i in range(10)]
    rows.append(_row("old", "Supreme Court of India", "1975-01-01", mentions=99))
    kept, _ = oi.choose_kept(rows, 10, 3, 1980, windows)
    assert kept == {"s9", "s8", "s7"}


def test_feasibility_report_from_a_tiny_corpus(raw_dir, tmp_path):
    out = tmp_path / "interim"
    oi.select_bail_orders(str(raw_dir), str(out))
    report = oi.check_feasibility(str(out), citation_sample=10)
    assert report["population"]["high_court_bail_orders"] == 2
    assert report["bns_era"]["orders"] == 2
    assert (out / "feasibility_report.json").is_file()
    assert "Week-0 data feasibility" in (out / "feasibility_report.md").read_text(encoding="utf-8")
    assert report["targets"]["dev_plus_test_cleanly_split_ge_250"]["met"] is False
    assert report["fir_numbers"]["orders_with_fir_key"] == 2


# ---- statutes ----------------------------------------------------------------------------------------------------
def leg_row(act_id: str, title: str, section: str, chunk: str, body: str, chapter: str = "Chapter I: X", sec_title: str = "Cheating") -> dict[str, Any]:
    head = f"Act: {title} (2023) | India | Central | In Force\n{chapter} | Section {section}: {sec_title}\n\n"
    return {"act_id": act_id, "chunk_id": chunk, "title": title, "section_number": section, "text": head + body}


@pytest.fixture()
def legislation_dir(tmp_path):
    bns, ipc = "The Bharatiya Nyaya Sanhita, 2023", "The Indian Penal Code, 45 of 1860 (Rep., Act 45 of 2023)"
    rows = [
        leg_row("B", bns, "318", "B_s318_p1", "( _a_ ) Illustration."),
        leg_row("B", bns, "318", "B_s318_p0", "**318. Cheating.—** Whoever cheats shall be punished with imprisonment of either description for a term which may extend to three years, or with fine."),
        leg_row("B", bns, "103", "B_s103", "**103. Murder.—** Whoever commits murder shall be punished with death or imprisonment for life.", sec_title="Punishment for murder"),
        leg_row("I", ipc, "420", "I_s420", "**420.** Whoever cheats shall be punished with imprisonment for a term which may extend to seven years."),
        leg_row("N", "The Narcotic Drugs and Psychotropic Substances Act, 1985", "37", "N_s37", "Offences to be cognizable and non-bailable."),
        leg_row("N", "The Narcotic Drugs and Psychotropic Substances Act, 1985", "20", "N_s20", "Not a bail bar."),
        leg_row("U", "The Unlawful Activities (Prevention) Act, 1967", "43D", "U_s43D", "( _5_ ) no person accused shall be released on bail."),
        leg_row("P", "The Prevention of Money-Laundering Act, 2002", "45", "P_s45", "Twin conditions for bail."),
        leg_row("O", "The Sale of Goods Act, 1930", "1", "O_s1", "Unrelated."),
    ]
    path = tmp_path / "raw" / "legislation" / "in_central_legislation.parquet"
    path.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows), path)
    return tmp_path / "raw"


def test_statutes_cover_the_named_acts_and_nothing_else(legislation_dir, tmp_path):
    out = tmp_path / "interim"
    n = oi.extract_statute_texts(str(legislation_dir), str(out))
    rows = [json.loads(line) for line in (out / "statutes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert n == len(rows) == 6
    assert {(r["code"], r["section"]) for r in rows} == {
        ("BNS", "318"), ("BNS", "103"), ("IPC", "420"), ("NDPS", "37"), ("UAPA", "43D"), ("PMLA", "45"),
    }


def test_statute_chunks_are_joined_in_part_order_without_the_header(legislation_dir, tmp_path):
    out = tmp_path / "interim"
    oi.extract_statute_texts(str(legislation_dir), str(out))
    by_key = {(r["code"], r["section"]): r for r in map(json.loads, (out / "statutes.jsonl").read_text(encoding="utf-8").splitlines())}
    text = by_key[("BNS", "318")]["text"]
    assert text.index("Whoever cheats") < text.index("Illustration")
    assert "Act:" not in text
    assert text.startswith("Cheating")
    assert by_key[("BNS", "318")]["max_punishment"] == "3 years"
    assert by_key[("BNS", "103")]["max_punishment"] == "death"
    assert by_key[("NDPS", "37")]["max_punishment"] is None


def test_statute_report_names_the_acts_missing_from_the_release(legislation_dir, tmp_path):
    out = tmp_path / "interim"
    oi.extract_statute_texts(str(legislation_dir), str(out))
    report = read_json(out / "ingest_report.json")["statutes"]
    assert "CrPC" in report["absent_from_release"]
    assert "BNSS" in report["absent_from_release"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("shall be punished with imprisonment for a term which may extend to seven years", "7 years"),
        ("imprisonment which may extend to six months, or with fine", "6 months"),
        ("punished with imprisonment for life, or with imprisonment which may extend to ten years", "life"),
        ("shall be punished with death", "death"),
        ("a definition with no penalty", None),
    ],
)
def test_max_punishment(text, expected):
    assert oi.max_punishment(text) == expected
