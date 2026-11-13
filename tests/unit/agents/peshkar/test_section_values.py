"""Section values as a hosted model writes them (the empty statutory position of the blind runs).

On every blind order the hosted extractor answered the sections field with the phrase of the order, for example
"Sections 143, 341, 332 and 353 read with 34 IPC", where the schema wants one object per section; each value failed as
malformed, the dossier had no sections and the brief no statutory position. These tests pin the repair: a string value is
read with the offline reader's rule parser into one item per charged section, each keeping the model's quote.
"""

import pytest

from vakeel_sahayak.agents.peshkar.fields import ExtractedItem, coerce_value, expand_section_items

QUOTE = "registered for the offences punishable under Sections 143, 341, 332 and 353 read with 34 IPC."


def test_a_phrase_becomes_one_item_per_charged_section_with_the_same_quote():
    items = expand_section_items(
        [ExtractedItem(value="Sections 143, 341, 332 and 353 read with 34 IPC", quote=QUOTE, doc="d1", page=1)]
    )
    assert [i.value["as_written"] for i in items] == ["IPC 143", "IPC 341", "IPC 332", "IPC 353", "IPC 34"]
    assert all(i.quote == QUOTE and i.doc == "d1" and i.page == 1 for i in items)
    assert [coerce_value("sections", i.value)["section"] for i in items] == ["143", "341", "332", "353", "34"]


def test_the_procedural_provision_of_the_petition_is_not_a_charged_section():
    """The model also lists 'Section 438 of the Code of Criminal Procedure' (the anticipatory-bail provision)."""
    items = expand_section_items(
        [
            ExtractedItem(
                value="Section 438 of the Code of Criminal Procedure",
                quote="under Section 438 of the Code of Criminal Procedure",
            ),
            ExtractedItem(
                value="Sections 294, 323, 324, 506, 34, 326 of the IPC",
                quote="for the offence under Sections 294, 323, 324, 506, 34, 326 of the IPC",
            ),
        ]
    )
    as_written = [i.value["as_written"] if isinstance(i.value, dict) else i.value for i in items]
    assert "Section 438 of the Code of Criminal Procedure" in as_written  # left as it was, so it is still refused below
    assert [a for a in as_written if a.startswith("IPC")] == [
        "IPC 294",
        "IPC 323",
        "IPC 324",
        "IPC 506",
        "IPC 34",
        "IPC 326",
    ]
    with pytest.raises(ValueError):
        coerce_value("sections", "Section 438 of the Code of Criminal Procedure")


def test_special_acts_and_suffixed_sections():
    items = expand_section_items(
        [ExtractedItem(value="u/s 22(c)/25/29 of the NDPS Act", quote="registered u/s 22(c)/25/29 of the NDPS Act")]
    )
    assert [i.value["as_written"] for i in items] == ["NDPS 22(c)", "NDPS 25", "NDPS 29"]
    items = expand_section_items(
        [ExtractedItem(value="Sections 498A/304B/34 of the Indian Penal Code, 1860", quote="x y")]
    )
    assert [i.value["section"] for i in items] == ["498A", "304B", "34"]


def test_a_section_repeated_across_items_is_kept_once():
    items = expand_section_items(
        [
            ExtractedItem(value="Section 420 IPC", quote="a b"),
            ExtractedItem(value="Sections 420 and 34 IPC", quote="c d"),
        ]
    )
    assert [i.value["as_written"] for i in items] == ["IPC 420", "IPC 34"]


def test_object_values_pass_unchanged_and_a_missing_as_written_or_numeric_section_is_filled():
    obj = ExtractedItem(value={"as_written": "BNS 318(4)", "code": "BNS", "section": "318(4)"}, quote="a b")
    assert expand_section_items([obj]) == [obj]
    assert coerce_value("sections", {"code": "IPC", "section": 307})["as_written"] == "IPC 307"
    assert coerce_value("sections", {"code": "IPC", "section": 307})["section"] == "307"
    assert coerce_value("sections", {"as_written": None, "code": "IPC", "section": "302"})["as_written"] == "IPC 302"
    with pytest.raises(ValueError):
        coerce_value("sections", {"code": "IPC"})
