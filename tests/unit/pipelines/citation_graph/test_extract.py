"""Regex extraction of Indian citations (plan §5.3 'Extraction'): INSC neutral, SCC, AIR, SCC OnLine, Cri LJ and
'X v. State of Y' case names. Resolution against Open India Law metadata is a separate step (resolve.py)."""

from __future__ import annotations

import pytest

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations

FORMATS = [
    pytest.param("2024 INSC 123", id="INSC_neutral"),
    pytest.param("(2022) 10 SCC 51", id="SCC"),
    pytest.param("AIR 2014 SC 2756", id="AIR"),
    pytest.param("2021 SCC OnLine Del 1234", id="SCC_OnLine"),
    pytest.param("2019 Cri LJ 100", id="Cri_LJ"),
]


@pytest.mark.parametrize("cite", FORMATS)
def test_each_citation_format_is_extracted_alone(cite):
    """A bare citation string is returned as that exact string."""
    assert extract_citations(cite) == [cite]


@pytest.mark.parametrize("cite", FORMATS)
def test_each_citation_format_is_extracted_inside_a_sentence(cite):
    """A citation in running text is found, without the surrounding words."""
    text = f"The Court relied on the decision reported at {cite} while granting bail to the applicant."
    assert extract_citations(text) == [cite]


@pytest.mark.parametrize(
    "name",
    ["Satender Kumar Antil v. CBI", "Arnesh Kumar v. State of Bihar", "Sanjay Chandra v. CBI"],
)
def test_case_names_are_extracted(name):
    """'X v. Y' and 'X v. State of Y' case names are found."""
    out = extract_citations(f"In {name} the Supreme Court laid down guidelines on arrest.")
    assert any(name in c for c in out), out


def test_name_and_reporter_citation_are_both_found():
    """A case name followed by its SCC citation gives both the name and the citation."""
    out = extract_citations("Reliance is placed on Arnesh Kumar v. State of Bihar, (2014) 8 SCC 273 and on 2024 INSC 123.")
    assert any("Arnesh Kumar v. State of Bihar" in c for c in out)
    assert "(2014) 8 SCC 273" in out
    assert "2024 INSC 123" in out


def test_several_citations_keep_order_of_appearance():
    """ASSUMPTION: results are in order of appearance in the text."""
    text = "See 2019 Cri LJ 100, then AIR 2014 SC 2756 and finally (2022) 10 SCC 51."
    assert extract_citations(text) == ["2019 Cri LJ 100", "AIR 2014 SC 2756", "(2022) 10 SCC 51"]


@pytest.mark.parametrize(
    "text",
    [
        "The applicant was arrested on 20.08.2024 under Section 420 IPC and remanded to custody.",
        "AIR conditioning was installed in the court room in 2014 after the renovation.",
        "He has been in custody for 10 years and the trial is not likely to conclude.",
        "The applicant said that the State of Bihar was not a party and the matter was heard in 2022.",
        "",
    ],
    ids=["dates_and_sections", "air_word", "years_and_numbers", "state_of_without_v", "empty"],
)
def test_plain_text_has_no_false_positives(text):
    """Dates, section numbers, years and ordinary words are not citations."""
    assert extract_citations(text) == []
