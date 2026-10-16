"""IPC2BNS-Verify loader on the REAL file layout (repository MS-406/IPC2BNS-Verify, MIT; plan §2 source 2).

`data/eval_ground_truth/concordance_v1.csv` has the header `ipc_section,bns_section,status`, but its second column holds a Python-literal
dict with the IPC and BNS section, heading and bare-act description; 'Repealed in BNS' marks sections with no counterpart. The rows below
are shortened copies of real rows (IPC 406 -> BNS 316(2), IPC 420 -> BNS 318(4), IPC 456 -> BNS 331(2, 4), IPC 7 repealed).
No network is used.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from vakeel_sahayak.pipelines.concordance.ipc2bns import _sections, build_ipc_bns_edges, load_ipc_bns_edges
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType as T

IPC_HDR = " Indian Penal Code, 1860 \n"
BNS_HDR = "The Bharatiya Nyaya Sanhita, 2023\n"
ROWS = [
    ("406", "Punishment for criminal breach of trust", "406. Punishment for criminal breach of trust \nWhoever commits criminal breach of trust shall be punished with\nimprisonment of either description for a term which may extend to three years,\nor with fine, or with both.",
     "316(2)", "Criminal breach of trust", "Of criminal breach of trust\n316. Criminal breach of trust.\n(2) Whoever commits criminal breach of trust shall be punished with imprisonment of either description for a term which may extend to five years, or with fine, or with both.\n"),
    ("13", "Definition of Government of India", "13. Definition of Government of India\nThe words shall mean the Government.",
     "2(27)", "Government", "2. Definitions.\n(27) The words shall mean the Government."),
    ("456", "Punishment for lurking housetrespass by night", "456. Punishment for lurking housetrespass by night\nWhoever commits lurking housetrespass by night shall be punished.",
     "331(2, 4)", "Punishment for housetrespass or housebreaking", '"The Bharatiya Nyaya Sanhita, 2023\n331. Punishment for housetrespass or housebreaking.\n(2) After sunset, punished with three years.\n\n(4) In order to commit an offence, punished with five years.'),
    ("66", "Punishment for A", "66. Punishment for A\nPunished A.", "8(4), (5)", "Fine", "8. Fine.\n(4) Fine A.\n(5) Fine B."),
    ("30", "Valuable security", "30. Valuable security\nThe words valuable security denote a document.",
     "2(31)", "Valuable security", "2. Definitions.\n(31) The words valuable security denote a document."),
    ("34", "Acts done by several persons", "34. Acts done by several persons\nWhen a criminal act is done by several persons, each is liable.",
     "3(5)", "Acts by several", "3. General explanations.\n(5) When a criminal act is done by several persons, each is liable."),
    ("35", "When such an act is criminal", "35. When such an act is criminal\nWhere an act is criminal by reason of knowledge.",
     "3(5)", "Acts by several", "3. General explanations.\n(5) When a criminal act is done by several persons, each is liable."),
    ("7", "Sense of expression once explained", "7. Sense of expression once explained\nEvery expression keeps its sense.", "Repealed in BNS", "", ""),
]


def write_verify_root(root: Path, with_noise: bool = True) -> Path:
    gt = root / "data" / "eval_ground_truth"
    gt.mkdir(parents=True)
    with (gt / "concordance_v1.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ipc_section", "bns_section", "status"])
        for ipc, ipc_head, ipc_text, bns, bns_head, bns_text in ROWS:
            cell = {"IPC Section": ipc, "IPC Heading": ipc_head, "IPC Descriptions": IPC_HDR + ipc_text,
                    "BNS Section": bns, "BNS Heading": bns_head, "BNS description": (BNS_HDR + bns_text) if bns_text else ""}
            writer.writerow([f"Provide the official title of IPC Section {ipc}.", repr(cell), "exact"])
    phase2 = root / "data" / "phase2_cleaned"
    phase2.mkdir(parents=True)
    (phase2 / "bns_sections.jsonl").write_text(
        json.dumps({"section_number": "111", "relationship_type": "new_in_bns"}) + "\n"
        + json.dumps({"section_number": "316", "relationship_type": "renumbered", "mapped_from_ipc": "406"}) + "\n",
        encoding="utf-8",
    )
    if with_noise:  # benchmark files that must be ignored
        bench = root / "phase7" / "benchmark"
        bench.mkdir(parents=True)
        (bench / "master_benchmark.jsonl").write_text(json.dumps({"question_id": "P7_0001", "ipc": "999", "bns": "888"}) + "\n", encoding="utf-8")
        (root / "README.md").write_text("# IPC2BNS-Verify\n", encoding="utf-8")
    return root


@pytest.fixture()
def edges(tmp_path):
    return {(e.old_ref, e.new_ref): e for e in load_ipc_bns_edges(str(write_verify_root(tmp_path / "verify")))}


def test_clause_level_references_are_split_into_one_edge_each(edges):
    """'331(2, 4)' and '8(4), (5)' name two clauses each; both are SPLIT edges from the same IPC section."""
    assert {k for k in edges if k[0] == "IPC 456"} == {("IPC 456", "BNS 331(2)"), ("IPC 456", "BNS 331(4)")}
    assert {k for k in edges if k[0] == "IPC 66"} == {("IPC 66", "BNS 8(4)"), ("IPC 66", "BNS 8(5)")}
    assert {edges[k].type for k in edges if k[0] in ("IPC 456", "IPC 66")} == {T.SPLIT}


def test_headers_numbers_and_headings_are_stripped_before_typing(edges):
    """IPC 13 -> BNS 2(27) has the same body behind different act titles, numbers and headings: SAME, no diff."""
    e = edges[("IPC 13", "BNS 2(27)")]
    assert e.type == T.SAME
    assert not e.text_diff


def test_reworded_edge_carries_a_diff_of_the_two_bodies(edges):
    """IPC 406 -> BNS 316(2): the penalty went from three to five years, so REWORDED with a diff naming both."""
    e = edges[("IPC 406", "BNS 316(2)")]
    assert e.type == T.REWORDED
    assert "three years" in e.text_diff
    assert "five years" in e.text_diff
    assert "Indian Penal Code" not in e.text_diff


def test_repealed_in_bns_gives_no_edge(edges):
    """IPC 7 is 'Repealed in BNS': no BNS counterpart, so no edge (the edge types have no 'repealed')."""
    assert not [k for k in edges if k[0] == "IPC 7"]


def test_two_ipc_sections_onto_one_bns_clause_are_merged(edges):
    """IPC 34 and IPC 35 both map to BNS 3(5)."""
    assert edges[("IPC 34", "BNS 3(5)")].type == T.MERGED
    assert edges[("IPC 35", "BNS 3(5)")].type == T.MERGED


def test_new_in_bns_sections_come_from_the_phase2_labels(edges):
    """BNS 111 is labelled new_in_bns: a NEW edge with an empty old_ref; 'renumbered' labels do not create edges."""
    assert edges[("", "BNS 111")].type == T.NEW
    assert [k for k in edges if k[1] == "BNS 316"] == []


def test_benchmark_and_readme_files_are_ignored(tmp_path):
    """With concordance_v1.csv present, the benchmark JSONL (ipc 999 -> bns 888) must not produce an edge."""
    loaded = load_ipc_bns_edges(str(write_verify_root(tmp_path / "v")))
    assert not [e for e in loaded if "999" in e.old_ref or "888" in e.new_ref]


def test_build_writes_edges_jsonl_and_checks_against_a_jsonl_statutes_file(tmp_path):
    """`statutes.jsonl` (JSON lines, as the Open India Law ingest writes it) is accepted; sections with Verify text need no lookup."""
    root = write_verify_root(tmp_path / "v")
    statutes = tmp_path / "statutes.jsonl"
    statutes.write_text(
        "".join(json.dumps({"code": c, "section": s, "text": "t"}) + "\n" for c, s in [("IPC", "406"), ("BNS", "316"), ("BNS", "111"), ("BNS", "2")]),
        encoding="utf-8",
    )
    out = tmp_path / "concordance_edges.jsonl"
    n = build_ipc_bns_edges(str(root), str(statutes), str(out))
    lines = out.read_text(encoding="utf-8").splitlines()
    assert n == len(lines) == len({(json.loads(x)["old_ref"], json.loads(x)["new_ref"]) for x in lines})
    assert {json.loads(x)["type"] for x in lines} >= {"SAME", "REWORDED", "SPLIT", "MERGED", "NEW"}


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("318(4)", ["318(4)"]),
        ("8(4), (5)", ["8(4)", "8(5)"]),
        ("331(2, 4)", ["331(2)", "331(4)"]),
        ("351(2) & (3)", ["351(2)", "351(3)"]),
        ("180 Explanation", ["180"]),
        ("326(a)", ["326(a)"]),
        ("Repealed in BNS", []),
        ("Repealed In BNS", []),
        ("189(3)(5)", ["189(3)(5)"]),
    ],
)
def test_section_cells_of_the_real_file(cell, expected):
    assert _sections(cell) == expected


def test_non_strict_build_drops_edges_whose_section_has_no_text_anywhere(tmp_path):
    """IPC 13 has an empty body in the source and is absent from the statutes file: strict raises, non-strict drops its edge and keeps the rest."""
    root = write_verify_root(tmp_path / "v")
    csv_path = root / "data" / "eval_ground_truth" / "concordance_v1.csv"
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    import ast

    for row in rows[1:]:
        cell = ast.literal_eval(row[1])
        if cell["IPC Section"] == "13":
            cell["IPC Descriptions"] = IPC_HDR + "13. Definition of Government of India\n"
            row[1] = repr(cell)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    statutes = tmp_path / "statutes.jsonl"
    statutes.write_text(json.dumps({"code": "BNS", "section": "2", "text": "t"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="IPC 13"):
        build_ipc_bns_edges(str(root), str(statutes), str(tmp_path / "a.jsonl"))
    n = build_ipc_bns_edges(str(root), str(statutes), str(tmp_path / "b.jsonl"), strict=False)
    refs = {json.loads(x)["old_ref"] for x in (tmp_path / "b.jsonl").read_text(encoding="utf-8").splitlines()}
    assert "IPC 13" not in refs
    assert n > 0
