"""scripts/extract_gap_statutes.py on tiny synthetic PDFs (no dependency on data/): sections, footnotes, state amendments, flags."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pymupdf
import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "extract_gap_statutes.py"
_spec = importlib.util.spec_from_file_location("extract_gap_statutes", _SCRIPT)
assert _spec and _spec.loader
gap = importlib.util.module_from_spec(_spec)
sys.modules["extract_gap_statutes"] = gap
_spec.loader.exec_module(gap)


def _pdf(path: Path, pages: list[list[tuple[float, float, float, str]]]) -> Path:
    """Write a PDF; each page is a list of (x, y, font size, text). The base-14 font cannot draw an em dash, so fixtures use ".-"."""
    doc = pymupdf.open()
    for items in pages:
        page = doc.new_page(width=595, height=842)
        for x, y, size, text in items:
            page.insert_text((x, y), text, fontsize=size, fontname="helv")
    doc.save(path)
    return path


def _act(tmp_path: Path) -> Path:
    page1 = [
        (60, 70, 11, "1. Short title.-This Act is short."),  # arrangement-style entry: no dash after the heading
        (60, 90, 11, "2. Heading two.-(1) Two text."),
        (60, 110, 11, "3. When police may arrest.-(1) Any police officer may arrest;"),
        (60, 124, 11, "(a) first limb;"),
        (60, 138, 11, "Provided that a safeguard applies."),
        (50, 152, 7, "1"),
        (60, 152, 11, "[3A. Notice of appearance.-(1) The police officer shall issue a notice."),
        (60, 166, 11, "(2) The person shall comply.]"),
        (60, 700, 9, "1. Ins. by Act 41 of 2010, s. 2 (w.e.f. 2-11-2010)."),
        (60, 712, 9, "continued footnote line"),
        (290, 748, 11, "39"),
    ]
    page2 = [
        (60, 80, 11, "5. Procedure.-(1) Central text of s.5."),
        (60, 94, 11, "Explanation.-An explanation of the Central section."),
        (240, 120, 10, "STATE AMENDMENTS"),
        (60, 140, 10, "Gujarat"),
        (60, 154, 10, "In section 167 for the words, other words shall be substituted."),
        (60, 180, 11, "6. Next section.-Text of s.6."),
    ]
    return _pdf(tmp_path / "act.pdf", [page1, page2])


def test_sections_footnotes_and_amendment_markers(tmp_path):
    lines = gap.pdf_lines(_act(tmp_path))
    found = gap.split_sections(lines, ["3", "3A", "5"])
    assert found["3"].startswith("3. When police may arrest.")
    assert "Provided that a safeguard applies." in found["3"]
    assert "3A" not in found["3"]  # the next section starts at the bracketed marker
    assert found["3A"].startswith("3A. Notice of appearance.")
    assert "(2) The person shall comply." in found["3A"]
    assert "[" not in found["3A"] and "]" not in found["3A"]
    assert "Ins. by Act" not in found["3A"] and "continued footnote" not in found["3A"]
    assert "39" not in found["3A"].split()  # page number dropped


def test_state_amendments_are_cut_but_explanation_kept(tmp_path):
    found = gap.split_sections(gap.pdf_lines(_act(tmp_path)), ["5"])
    text = found["5"]
    assert "Central text of s.5." in text
    assert "Explanation.-An explanation of the Central section." in text
    assert "Gujarat" not in text and "STATE AMENDMENT" not in text and "substituted" not in text
    assert "6." not in text


def test_ocr_fixes_are_mechanical():
    assert gap.apply_ocr_fixes("under Sec. 27Al of Psychottopic substances") == "under Sec. 27A of Psychotropic substances"


def test_ndps_flags_are_read_from_section_37_text():
    s37 = (
        "37. Offences to be cognizable and non-bailable.—(1) Notwithstanding anything,—\n"
        "(a) every offence punishable under this Act shall be cognizable;\n"
        "(b) no person accused of an offence punishable for offences under section 19 or section 24 or section 27A "
        "shall be released on bail or on his own bond unless—\n"
        "(i) the Public Prosecutor has been given an opportunity to oppose the application for such release, and"
    )
    flags = gap.ndps_flags({"37": s37, "19": "x", "24": "x", "31A": "x"})
    assert flags["37"] == {"cognisable": True, "bailable": False}
    assert flags["19"] == {"cognisable": True, "bailable": False}
    assert flags["31A"] == {"cognisable": True}  # named by s.37 for cognizability only, not for the bail bar
    assert gap.ndps_flags({"37": "37. Something else."})["37"] == {}


@pytest.mark.parametrize(
    ("cell", "kind", "prev", "want"),
    [
        ("Non-cognizable.", "cog", None, False),
        ("Cognizable", "cog", None, True),
        ("Non- bailable.", "bail", None, False),
        ("Bailable", "bail", None, True),
        ("Ditto", "bail", False, False),
        ("According as offence abetted is bailable or non-bailable.", "bail", True, None),
    ],
)
def test_cell_flags(cell, kind, prev, want):
    assert gap._cell_flag(cell, kind, prev)[0] is want


def test_first_schedule_table_is_parsed_by_columns(tmp_path):
    def row(y, sec, offence, cog, bail):
        return [(66, y, 8, sec), (97, y, 8, offence), (258, y, 8, "Imprisonment"), (365, y, 8, cog), (440, y, 8, bail), (510, y, 8, "Session.")]

    head = [
        (240, 60, 11, "THE FIRST SCHEDULE"),
        (186, 90, 10, "I.–OFFENCES UNDER THE INDIAN PENAL CODE"),
        (63, 110, 8, "Cognizable or non-"),
        (70, 125, 8, "1"), (170, 125, 8, "2"), (318, 125, 8, "3"), (390, 125, 8, "4"), (466, 125, 8, "5"), (529, 125, 8, "6"),
    ]  # fmt: skip
    body = (
        row(160, "302", "Murder", "Cognizable", "Non-bailable")
        + row(200, "323", "Hurt", "Non-cognizable", "Bailable")
        + [(66, 240, 8, "324"), (97, 240, 8, "Hurt by weapon"), (294, 240, 8, "Ditto"), (384, 240, 8, "Cognizable"), (460, 240, 8, "Ditto")]
        + row(280, "420", "Cheating", "Ditto", "Ditto")
        + row(320, "109", "Abetment", "According as offence abetted is cognizable", "According as offence abetted is bailable")
    )
    tail = [(186, 600, 10, "II.–CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS")]
    pdf = _pdf(tmp_path / "sched.pdf", [head + body + tail])
    rows, notes = gap.parse_first_schedule(pdf)
    by = {r["section"]: r for r in rows}
    assert (by["302"]["cognisable"], by["302"]["bailable"]) == (True, False)
    assert (by["323"]["cognisable"], by["323"]["bailable"]) == (False, True)
    assert by["324"]["cognisable"] is True  # col 4 reads Cognizable
    assert by["420"]["cognisable"] is True and by["420"]["bailable"] is True  # Ditto repeats the row above (324: Cognizable, Ditto of Bailable)
    assert by["109"]["cognisable"] is None and by["109"]["bailable"] is None
    assert any("s.109" in n for n in notes)
