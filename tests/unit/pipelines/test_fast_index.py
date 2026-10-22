"""FastCitationIndex gives the same resolution as CitationIndex for case names that share words with the indexed title."""

from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex
from vakeel_sahayak.pipelines.store_builders.fast_index import FastCitationIndex

RECORDS = [
    {"doc_id": "a", "title": "Sanjay Chandra v. Central Bureau of Investigation", "court": "Supreme Court of India", "date": "2011-11-23"},
    {"doc_id": "b", "title": "Arnesh Kumar v. State of Bihar", "court": "Supreme Court of India", "date": "2014-07-02"},
]


def test_same_result_as_slow_index_and_memoised():
    slow, fast = CitationIndex(RECORDS), FastCitationIndex(RECORDS)
    for cite in ["Sanjay Chandra v. Central Bureau of Investigation", "Arnesh Kumar v. State of Bihar (2014)", "Nobody v. Nothing"]:
        assert fast.resolve(cite) == slow.resolve(cite)
    assert fast.resolve("Sanjay Chandra v. CBI") == slow.resolve("Sanjay Chandra v. CBI")
    assert fast._memo
