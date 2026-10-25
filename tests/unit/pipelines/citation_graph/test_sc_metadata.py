"""Supreme Court metadata in the citation index (VI-05): SCR and INSC keys, case names against SC titles, the metadata builder,
and the corpus builder reading `oil_metadata.jsonl` (small synthetic fixtures, no data/ files)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation
from vakeel_sahayak.pipelines.citation_graph.measure import measure
from vakeel_sahayak.pipelines.citation_graph.oil_metadata import build_oil_metadata
from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex, clean_case_name
from vakeel_sahayak.pipelines.store_builders import corpus
from vakeel_sahayak.pipelines.store_builders.fast_index import FastCitationIndex

SC = [
    {"doc_id": "2011_INSC_772", "title": "SANJAY CHANDRA versus CENTRAL BUREAU OF INVESTIGATION", "date": "2011-11-23",
     "court": "Supreme Court of India", "citations": ["[2011] 15 S.C.R. 211", "2011 INSC 772"], "case_number": ""},
    {"doc_id": "2006_INSC_9", "title": "STATE OF BIHAR versus RAJ KUMAR", "date": "2006-03-02",
     "court": "Supreme Court of India", "citations": ["[2006] SUPP. 8 S.C.R. 1021", "2006 INSC 9"], "case_number": ""},
    {"doc_id": "1979_INSC_59", "title": "UNION OF INDIA & ANR. versus K. G. KHOSLA & CO. (P) LTD.", "date": "1979-03-06",
     "court": "Supreme Court of India", "citations": ["[1979] 3 S.C.R. 453", "1979 INSC 59"], "case_number": ""},
]
HC = [
    {"doc_id": "DLHC-1", "title": "BAIL APPLN./2599/2024 of RAJ KUMAR Vs THE STATE OF BIHAR", "date": "2024-02-01", "court": "Patna High Court", "citations": []},
]


@pytest.mark.parametrize(
    ("raw", "key"),
    [("[1979] 3 S.C.R. 453", "1979 3 scr 453"), ("(1979) 3 SCR 453", "1979 3 scr 453"), ("[2006] SUPP. 8 S.C.R. 1021", "2006 supp 8 scr 1021")],
)
def test_scr_citations_are_extracted_and_keyed(raw, key):
    assert extract_citations(f"as held in {raw} by this Court") == [raw]
    parsed = parse_citation(raw)
    assert parsed is not None and parsed.kind == "scr" and parsed.key == key


def test_scr_does_not_swallow_scc():
    assert parse_citation("(2014) 8 SCC 273").kind == "scc"  # type: ignore[union-attr]


@pytest.mark.parametrize("index_cls", [CitationIndex, FastCitationIndex])
def test_supreme_court_judgments_resolve_by_neutral_scr_and_name(index_cls):
    index = index_cls([*SC, *HC])
    assert index.resolve("2011 INSC 772") == "2011_INSC_772"
    assert index.resolve("[2011] 15 S.C.R. 211") == "2011_INSC_772"
    assert index.resolve("(2011) 15 SCR 211") == "2011_INSC_772"
    assert index.resolve("[2006] SUPP. 8 S.C.R. 1021") == "2006_INSC_9"
    assert index.resolve("[2006] 8 S.C.R. 1021") is None  # without SUPP. it is another volume
    assert index.resolve("Sanjay Chandra v. Central Bureau of Investigation (2011)") == "2011_INSC_772"
    assert index.resolve("Union of India v. K. G. Khosla and Co.") == "1979_INSC_59"


def test_a_citation_the_metadata_cannot_know_stays_unresolved():
    """sc_metadata.jsonl has no SCC or AIR numbers, so those resolve by name only; a bare number never resolves."""
    index = CitationIndex(SC)
    assert index.resolve("(2011) 14 SCC 1") is None
    assert index.resolve("AIR 2011 SC 3") is None


def test_docket_prefix_of_high_court_titles_is_dropped():
    assert clean_case_name("BAIL/3506/2025 of MUKTESHWAR PRASAD Vs CENTRAL BUREAU OF INVESTIGATION ACB LKO.") == "MUKTESHWAR PRASAD Vs CENTRAL BUREAU OF INVESTIGATION ACB LKO."
    assert clean_case_name("CRM (A)/1049/2025 of MAHESH YADAV Vs STATE OF WEST BENGAL") == "MAHESH YADAV Vs STATE OF WEST BENGAL"
    assert clean_case_name("BAIL APPLICATION 2299 of 2025") == "BAIL APPLICATION 2299 of 2025"
    index = FastCitationIndex([{"doc_id": "x", "title": "BAIL/1/2024 of ASHOK KUMAR Vs STATE OF GOA", "date": "2024-01-01", "court": "Bombay High Court"}])
    assert index.resolve("Ashok Kumar v. State of Goa") == "x"


def test_the_same_judgment_listed_twice_is_not_its_own_rival():
    both = FastCitationIndex([SC[0], {**SC[0], "title": "Sanjay Chandra v. Central Bureau of Investigation"}])
    assert both.resolve("Sanjay Chandra v. Central Bureau of Investigation") == "2011_INSC_772"
    assert both.docs["2011_INSC_772"]["date"] == "2011-11-23"


def test_build_oil_metadata_merges_orders_and_supreme_court_records(tmp_path):
    sc = tmp_path / "sc.jsonl"
    orders = tmp_path / "orders.jsonl"
    sc.write_text("\n".join(json.dumps(r) for r in SC) + "\n", encoding="utf-8")
    rows = [
        {**HC[0], "text": "x", "bench_size": "2"},
        {"doc_id": "2011_INSC_772", "title": "Sanjay Chandra v. CBI", "date": "2011-11-23", "court": "Supreme Court of India", "citations": [], "bench_size": 2, "text": "x"},
    ]
    orders.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out = tmp_path / "oil_metadata.jsonl"
    info = build_oil_metadata(str(sc), str(orders), str(out))
    assert info["records"] == 4 and info["in_both"] == 1 and info["sc_only_not_in_corpus"] == 2
    recs = {r["doc_id"]: r for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
    assert recs["DLHC-1"]["case_name"] == "RAJ KUMAR Vs THE STATE OF BIHAR" and recs["DLHC-1"]["court_level"] == "HC" and recs["DLHC-1"]["bench_size"] == 2
    sc_rec = recs["2011_INSC_772"]
    assert (sc_rec["source"], sc_rec["in_corpus"], sc_rec["bench_size"], sc_rec["neutral_citation"]) == ("both", True, 2, "2011 INSC 772")
    assert "[2011] 15 S.C.R. 211" in sc_rec["citations"]
    assert recs["1979_INSC_59"]["in_corpus"] is False and recs["1979_INSC_59"]["court_level"] == "SC"
    index = FastCitationIndex(list(recs.values()))
    assert index.resolve("[1979] 3 S.C.R. 453") == "1979_INSC_59"


def test_measure_reports_rate_per_format(tmp_path):
    sample = tmp_path / "s.jsonl"
    rows = [
        {"citing_doc_id": "a", "raw": "2011 INSC 772", "kind": "neutral", "stratum": ["uniform", "format"]},
        {"citing_doc_id": "a", "raw": "2012 INSC 5", "kind": "neutral", "stratum": ["format"]},
        {"citing_doc_id": "b", "raw": "[1979] 3 S.C.R. 453", "kind": "scr", "stratum": ["uniform"]},
    ]
    sample.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    result = measure(FastCitationIndex(SC), str(sample))
    assert result["uniform"] == {"n": 2, "resolved": 2, "rate": 1.0}
    assert result["per_format_sample"]["neutral"] == {"n": 2, "resolved": 1, "rate": 0.5}


def _interim(root: Path, with_metadata: bool) -> str:
    root.mkdir(parents=True, exist_ok=True)
    reasoning = (
        "The principles were laid down in [1979] 3 S.C.R. 453 and followed in Sanjay Chandra v. Central Bureau of Investigation. "
        "The petitioner relies on 2011 INSC 772 which this Court relied on and followed in the present facts and circumstances."
    )
    parts = {"facts": "The applicant was arrested on 01.01.2024 in connection with FIR No. 1 of 2024.", "defense_submissions": "Counsel for the applicant submits that he is innocent.",
             "prosecution_submissions": "The learned APP opposes the application for bail.", "reasoning": reasoning, "operative_order": "The application is allowed."}
    orders = [{"doc_id": "HC-1", "text": " ".join(parts.values()), "date": "2024-05-01", "court": "Delhi High Court", "parts": parts, "outcome": "granted"},
              {"doc_id": "HC-TEST", "text": " ".join(parts.values()), "date": "2024-06-01", "court": "Delhi High Court", "parts": parts, "outcome": "granted"}]
    (root / "orders.jsonl").write_text("\n".join(json.dumps(o) for o in orders) + "\n", encoding="utf-8")
    if with_metadata:
        meta = [{**r, "in_corpus": False, "court_level": "SC", "year": int(r["date"][:4])} for r in SC]
        meta.append({"doc_id": "HC-TEST", "title": "Test Order v. State", "court": "Delhi High Court", "date": "2024-06-01", "in_corpus": True})
        meta.append({"doc_id": "HC-LEAK", "title": "Leaky Case v. State of Delhi", "court": "Delhi High Court", "date": "2024-01-01", "in_corpus": False})
        (root / "oil_metadata.jsonl").write_text("\n".join(json.dumps(r) for r in meta) + "\n", encoding="utf-8")
    return str(root)


def test_corpus_resolves_supreme_court_citations_only_with_the_metadata_file(tmp_path):
    corpus.clear_cache()
    without = corpus.process_corpus(_interim(tmp_path / "a", False), {"HC-TEST"})
    assert without.graph.n_edges == 0
    assert "external_metadata_records" not in without.report
    corpus.clear_cache()
    withmeta = corpus.process_corpus(_interim(tmp_path / "b", True), {"HC-TEST", "HC-LEAK"})
    cited = {e.cited_doc_id for e in withmeta.graph.cites("HC-1")}
    assert cited == {"1979_INSC_59", "2011_INSC_772"}
    assert withmeta.report["external_metadata_records"] == 3  # the order record and the excluded id are not added
    node = withmeta.graph.nodes["2011_INSC_772"]
    assert (node.court_level, node.date) == ("SC", "2011-11-23")
    by_format = withmeta.report["citations_by_format"]
    assert by_format["scr"] == {"extracted": 1, "resolved": 1}
    assert by_format["neutral"]["resolved"] == 1
    corpus.clear_cache()
