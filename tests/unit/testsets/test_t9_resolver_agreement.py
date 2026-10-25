"""T9 (new tests): the generated strings are well-formed for the citation resolver, and `metadata_used.jsonl` is an index it can read."""

from __future__ import annotations

from tests.unit.testsets._helpers import read_rows
from tests.unit.testsets.test_t9_citation_formats import write_metadata
from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex
from vakeel_sahayak.testsets.t9_citation_formats import build_t9


def test_citation_format_strings_resolve_to_their_document_and_distractors_do_not(tmp_path):
    path, _ = write_metadata(tmp_path)
    build_t9(str(path), str(tmp_path / "t9"))
    index = CitationIndex.from_jsonl(tmp_path / "t9" / "metadata_used.jsonl")
    wrong = [r for r in read_rows(tmp_path / "t9" / "strings.jsonl") if r["format"] != "case_name" and index.resolve(r["string"]) != r["doc_id"]]
    assert not wrong, wrong[:5]


def test_the_metadata_used_file_records_which_references_were_constructed(tmp_path):
    """Real metadata may lack SCC/AIR/SCC OnLine/Cri LJ numbers; whatever the builder adds is named, never silent."""
    import json

    src = tmp_path / "sparse.jsonl"
    src.write_text("\n".join(json.dumps({"doc_id": f"D{i}", "title": f"A{i} versus B{i}", "date": "2001-02-03", "court": "Supreme Court of India",
                                         "citations": [f"2001 INSC {i + 1}", f"[2001] 1 S.C.R. {i}"]}) for i in range(60)) + "\n", encoding="utf-8")
    m = build_t9(str(src), str(tmp_path / "t9"))
    used = read_rows(tmp_path / "t9" / "metadata_used.jsonl")
    assert all(d["synthetic_fields"] == ["scc", "air", "scc_online", "cri_lj"] and d["neutral_citation"] for d in used)
    assert m.details["constructed_references"]["scc"] == 60 and m.details["real_references"]["neutral"] == 60
