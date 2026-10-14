"""Regex section extraction and section-family expansion through the concordance (plan §5.2 'sections', 'section_family', §5.4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vakeel_sahayak.pipelines.section_extract import expand_family, extract_sections

CONCORDANCE_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "law" / "concordance.json"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The applicant is charged under Section 420 IPC.", ["IPC 420"]),
        ("offence punishable under Section 420 of the Indian Penal Code", ["IPC 420"]),
        ("registered under 318(4) BNS", ["BNS 318(4)"]),
        ("registered under Section 318(4) of the Bharatiya Nyaya Sanhita", ["BNS 318(4)"]),
        ("a petition under Section 439 Cr.P.C. for regular bail", ["CrPC 439"]),
        ("a petition under Section 439 CrPC for regular bail", ["CrPC 439"]),
        ("a petition under 483 BNSS for regular bail", ["BNSS 483"]),
        ("Section 483 of the Bharatiya Nagarik Suraksha Sanhita, 2023", ["BNSS 483"]),
        ("FIR No. 112/2024 PS-1 dated 14.08.2024 under 318(4) BNS", ["BNS 318(4)"]),
        ("The applicant was arrested and produced before the Magistrate.", []),
        ("", []),
    ],
)
def test_extract_sections(text, expected):
    """Sections are normalised to 'CODE number': 'Section 420 IPC' -> 'IPC 420', '318(4) BNS' -> 'BNS 318(4)', and so on."""
    assert extract_sections(text) == expected


def test_multiple_sections_in_one_text_in_order_of_appearance():
    """Several sections are all returned, in the order they appear (ASSUMPTION: first-appearance order)."""
    text = "Offences under Section 420 IPC read with Section 406 IPC, and a bail petition under Section 439 Cr.P.C."
    assert extract_sections(text) == ["IPC 420", "IPC 406", "CrPC 439"]


def test_sections_listed_together_share_the_code():
    """ASSUMPTION: 'Sections 420, 406 IPC' gives both IPC 420 and IPC 406."""
    assert extract_sections("Sections 420, 406 IPC") == ["IPC 420", "IPC 406"]


def test_duplicates_are_removed():
    """A section mentioned three times, in three spellings, is returned once."""
    text = "Section 420 IPC ... later Section 420 of the Indian Penal Code ... and again 420 IPC."
    assert extract_sections(text) == ["IPC 420"]


def test_same_number_under_different_codes_stays_distinct():
    """'Section 420 IPC' and 'Section 420 BNS' are different sections."""
    assert set(extract_sections("Section 420 IPC and Section 420 BNS")) == {"IPC 420", "BNS 420"}


# ---- expand_family -----------------------------------------------------------------------------------------------
@pytest.fixture()
def concordance_file(tmp_path) -> str:
    """A concordance JSON file in tmp_path built from tests/fixtures/law/concordance.json."""
    # ASSUMPTION: the on-disk format is a JSON list of ConcordanceEdge dicts, as in the fixture.
    path = tmp_path / "concordance.json"
    shutil.copy(CONCORDANCE_FIXTURE, path)
    assert json.loads(path.read_text())
    return str(path)


def test_ipc_420_expands_to_bns_318_4(concordance_file):
    """Plan §5.4: IPC 420 expands to its BNS equivalent BNS 318(4) and keeps itself."""
    assert set(expand_family(["IPC 420"], concordance_file)) == {"IPC 420", "BNS 318(4)"}


def test_ipc_406_expands_to_bns_316_2(concordance_file):
    """IPC 406 expands to BNS 316(2)."""
    assert set(expand_family(["IPC 406"], concordance_file)) == {"IPC 406", "BNS 316(2)"}


def test_bns_section_expands_back_to_ipc(concordance_file):
    """A BNS-era case asking about BNS 318(4) also reaches precedents decided under IPC 420."""
    assert set(expand_family(["BNS 318(4)"], concordance_file)) == {"BNS 318(4)", "IPC 420"}


def test_section_without_an_edge_expands_to_itself(concordance_file):
    """A section with no concordance edge is its own family."""
    assert expand_family(["IPC 1"], concordance_file) == ["IPC 1"]


def test_split_edge_expands_to_all_new_sections(concordance_file):
    """A split edge (IPC 999 -> BNS 888(1), BNS 888(2)) puts both new sections in the family."""
    assert set(expand_family(["IPC 999"], concordance_file)) == {"IPC 999", "BNS 888(1)", "BNS 888(2)"}


def test_merged_edge_expands_to_all_old_sections(concordance_file):
    """A merge (IPC 777 and IPC 778 -> BNS 666): from BNS 666 both IPC sections are in the family."""
    assert set(expand_family(["BNS 666"], concordance_file)) == {"BNS 666", "IPC 777", "IPC 778"}


def test_family_of_several_sections_is_deduplicated(concordance_file):
    """Two sections of the same family give each member once, e.g. IPC 420 plus BNS 318(4)."""
    out = expand_family(["IPC 420", "BNS 318(4)", "IPC 406"], concordance_file)
    assert len(out) == len(set(out))
    assert set(out) == {"IPC 420", "BNS 318(4)", "IPC 406", "BNS 316(2)"}


def test_crpc_to_bnss_edge_expands(concordance_file):
    """The bail sections bridge too: CrPC 439 <-> BNSS 483."""
    assert set(expand_family(["CrPC 439"], concordance_file)) == {"CrPC 439", "BNSS 483"}
