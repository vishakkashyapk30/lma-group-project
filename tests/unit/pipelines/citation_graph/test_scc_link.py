"""Name-linked SCC citations ('Case Name, (2011) 15 SCC 211' resolved through the case name and the SCC year); synthetic fixtures only."""

from __future__ import annotations

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation, scc_name_before
from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex
from vakeel_sahayak.pipelines.store_builders.fast_index import FastCitationIndex

SC = [
    {"doc_id": "2011_INSC_772", "title": "SANJAY CHANDRA versus CENTRAL BUREAU OF INVESTIGATION", "date": "2011-11-23", "court": "Supreme Court of India", "citations": []},
    {"doc_id": "2014_INSC_1", "title": "ARNESH KUMAR versus STATE OF BIHAR", "date": "2014-07-02", "court": "Supreme Court of India", "citations": []},
]
HC = [{"doc_id": "PHHC-1", "title": "ARNESH KUMAR Vs STATE OF BIHAR", "date": "2014-07-02", "court": "Patna High Court", "citations": []}]
TEXT = "Reliance was placed on Sanjay Chandra v. Central Bureau of Investigation, (2012) 1 SCC 40 and Arnesh Kumar v. State of Bihar (2014) 8 SCC 273."


def test_default_extraction_is_unchanged():
    assert extract_citations(TEXT) == extract_citations(TEXT, link_scc=False)
    assert "(2012) 1 SCC 40" in extract_citations(TEXT)


def test_linked_extraction_prefixes_the_name_and_keeps_the_scc_key():
    got = extract_citations(TEXT, link_scc=True)
    assert "Sanjay Chandra v. Central Bureau of Investigation, (2012) 1 SCC 40" in got
    assert "(2012) 1 SCC 40" not in got
    p = parse_citation("Sanjay Chandra v. Central Bureau of Investigation, (2012) 1 SCC 40")
    assert p is not None and p.kind == "scc" and p.key == "2012 1 scc 40"


def test_name_before_scc_must_touch_the_citation():
    assert scc_name_before("see Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273", len("see Arnesh Kumar v. State of Bihar, ")) == "Arnesh Kumar v. State of Bihar"
    far = "Arnesh Kumar v. State of Bihar was cited, and the Court also noted (2014) 8 SCC 273"
    assert scc_name_before(far, far.index("(2014)")) is None


def test_scc_resolves_through_the_name_only_when_enabled():
    for cls in (CitationIndex, FastCitationIndex):
        idx = cls([*SC, *HC])
        raw = "Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273"
        assert idx.resolve(raw) is None  # default: no link
        idx.link_scc = True
        assert idx.resolve(raw) == "2014_INSC_1"  # Supreme Court judgment, not the High Court order of the same name
        assert idx.resolve("(2014) 8 SCC 273") is None  # a bare SCC number has no name to go through


def test_year_gate_blocks_a_wrong_year():
    idx = CitationIndex(SC)
    idx.link_scc = True
    assert idx.resolve("Arnesh Kumar v. State of Bihar, (1999) 8 SCC 273") is None
    assert idx.resolve("Arnesh Kumar v. State of Bihar, (2015) 8 SCC 273") == "2014_INSC_1"  # reported a year after the decision


def test_exact_scc_key_still_wins():
    rec = {**SC[1], "citations": ["(2014) 8 SCC 273"]}
    idx = CitationIndex([SC[0], rec])
    idx.link_scc = True
    assert idx.resolve("Sanjay Chandra v. Central Bureau of Investigation, (2014) 8 SCC 273") == "2014_INSC_1"
