"""scripts/extract_gap_statutes.py on tiny synthetic PDFs (no dependency on data/): sections, footnotes, state amendments, flags."""

from __future__ import annotations

import importlib.util
import json
import re
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



def _gazette(tmp_path: Path) -> Path:
    """Two Gazette-style pages: body text 10 pt, headings as 8 pt margin notes (right on the first page, left on the second)."""
    even = [
        (142, 100, 10, "1. (1) This Act may be called the Sanhita."),
        (487, 100, 8, "Short title."),
        (142, 200, 10, "2. A police officer making an arrest shall take the person"),
        (118, 212, 10, "before a Magistrate."),
        (487, 200, 8, "Person arrested to"),
        (487, 209, 8, "be taken before"),
        (487, 218, 8, "Magistrate."),
        (142, 300, 10, "3. No police officer shall detain a person"),
        (118, 312, 10, "for more than twenty-four hours."),
        (487, 300, 8, "Person arrested not"),
        (487, 309, 8, "to be detained."),
        (142, 330, 10, "(2) Second sub-section of 3."),
        (217, 44, 8, "THE GAZETTE OF INDIA EXTRAORDINARY"),
    ]
    odd = [
        (142, 100, 10, "4. Officers in charge shall report."),
        (60, 100, 8, "Police to report."),
        (142, 150, 10, "5. Not a heading: no margin note beside it."),
    ]
    return _pdf(tmp_path / "gazette.pdf", [even, odd])


def test_gazette_sections_take_headings_from_either_margin(tmp_path):
    found = gap.gazette_sections(_gazette(tmp_path), ["2", "3", "4"])
    assert found["3"] == ("Person arrested not to be detained", "3. No police officer shall detain a person for more than twenty-four hours.\n(2) Second sub-section of 3.")
    assert found["2"][0] == "Person arrested to be taken before Magistrate"
    assert found["4"] == ("Police to report", "4. Officers in charge shall report. 5. Not a heading: no margin note beside it.")


def test_build_gazette_rows_use_the_store_form(tmp_path):
    rows, missing = gap.build_gazette_rows("BNSS", _gazette(tmp_path), "https://example.org/g.pdf", ["3", "999"], "2026-11-02")
    assert missing == ["999"]
    assert rows[0]["text"].startswith("Person arrested not to be detained\n\n3. Person arrested not to be detained.—No police officer")
    assert (rows[0]["code"], rows[0]["section"], rows[0]["retrieved"]) == ("BNSS", "3", "2026-11-02")


def test_fetch_pinned_refuses_a_file_with_another_hash(tmp_path):
    f = tmp_path / "g.pdf"
    f.write_bytes(b"%PDF-1.4 not the gazette")
    with pytest.raises(ValueError, match="not the pinned"):
        gap.fetch_pinned("https://example.org/g.pdf", f, "0" * 64)
    assert gap.fetch_pinned("https://example.org/g.pdf", f, gap.sha256_of(f)) == f


def _companies_act(tmp_path: Path) -> Path:
    """A consolidated-Act page in the CrPC layout (numbers rise in small steps, as the reader requires): s.2 ends at s.3, its footnote is dropped."""
    return _pdf(tmp_path / "companies.pdf", [[
        (72, 80, 10, "1. Short title.-This Act may be called the Companies Act."),
        (72, 110, 10, "2. Investigation into affairs of Company by Serious Fraud Investigation Office.-(1) Text."),
        (72, 125, 10, "(6) No person accused shall be released on bail unless the court is satisfied."),
        (72, 155, 10, "3. Investigation into company's affairs in other cases.-Other text."),
        (72, 500, 9, "1. Subs. by Act 21 of 2015, s. 19."),
    ]])


def test_companies_act_row_is_the_wanted_section_alone(tmp_path):
    rows, missing = gap.build_rows("Companies Act", _companies_act(tmp_path), gap.COMPANIES_URL, ["2", "999"], "2026-11-07")
    assert missing == ["999"] and [r["section"] for r in rows] == ["2"]
    assert rows[0]["code"] == "Companies Act" and rows[0]["source_url"] == gap.COMPANIES_URL
    assert "(6) No person accused" in rows[0]["text"] and "Other text" not in rows[0]["text"] and "Subs. by" not in rows[0]["text"]


def test_store_build_keeps_a_companies_act_gap_row(tmp_path):
    from vakeel_sahayak.schemas.store_rows import StatuteRow
    from vakeel_sahayak.stores.law_statutes import _merge_gap_rows

    (tmp_path / "companies_act.jsonl").write_text(
        json.dumps({"code": "Companies Act", "section": "212", "text": "212. Investigation.-(6) bail", "source_url": "u", "retrieved": "d"}) + "\n",
        encoding="utf-8",
    )
    rows = _merge_gap_rows([StatuteRow(code="IPC", section="420", text="cheating")], tmp_path)
    assert {(r.code, r.section) for r in rows} == {("IPC", "420"), ("Companies Act", "212")}


def test_companies_act_pdf_is_pinned_to_a_sha256():
    assert re.fullmatch(r"[0-9a-f]{64}", gap.COMPANIES_SHA256) and gap.COMPANIES_URL.startswith("https://")


# ---------------------------------------------------------------- First Schedule table (offence, punishment, triable by)


@pytest.mark.parametrize(
    ("cell", "want"),
    [
        ("Death, or imprisonment for life, and fine.", "death"),
        ("Imprisonment for life, or imprisonment for 10 years and fine.", "life imprisonment"),
        ("Rigorous imprisonment for not less than 20 years which may extend to the remainder of that person's natural life", "life imprisonment"),
        ("Imprisonment for 7 years and fine.", "7 years"),
        ("Imprisonment for three years and fine.", "3 years"),
        ("Imprisonment of 1 year which may extend to 5 years, and with fine.", "5 years"),
        ("Simple imprisonment for 1 month, or fine of 500 rupees, or both.", "1 month"),
        ("Simple imprisonment for 24 hours, or fine of 10 rupees, or both.", "24 hours"),
        ("Fine of 200 rupees.", "fine"),
        ("Same as for offence abetted.", None),
        ("Imprisonment extending to a quarter part of the longest term provided for the offence, or fine, or both.", None),
        ("", None),
    ],
)
def test_schedule_max_punishment_is_normalised_or_none(cell, want):
    assert gap.schedule_max_punishment(cell) == want


def test_punishment_rank_orders_the_normalised_labels():
    labels = ["life imprisonment", "fine", "7 years", "24 hours", "death", "6 months", "1 year"]
    assert sorted(labels, key=gap.punishment_rank) == ["fine", "24 hours", "6 months", "1 year", "7 years", "life imprisonment", "death"]


def test_a_conditional_flag_cell_is_none():
    assert gap._cell_flag("Cognizable if information relating to the offence is given by the person aggrieved", "cog", None) == (None, "cond")
    assert gap._cell_flag("Non-cognizable Ditto", "cog", True) == (False, "ok")  # a Ditto after a value is not read as a Ditto


def test_columns_follow_the_punishment_and_bail_edges_of_the_page():
    xs = [64, 91, 231, 231, 231, 357, 420, 510]
    texts = ["465", "Forgery", "Imprisonment", "or both.", "Imprisonment", "Non-cognizable", "Bailable", "Any Magistrate."]
    assert gap._columns(xs, texts) == [0, 1, 2, 2, 2, 3, 4, 5]
    assert gap._columns([97, 240, 258, 365, 422, 440], ["Hurt", "word", "Imprisonment", "Cognizable", "if", "Non-bailable"]) == [1, 1, 2, 3, 3, 4]


def _schedule_pdf(tmp_path: Path) -> Path:
    """One page of a First Schedule with the hard cases met in the CrPC text (all coordinates in points, 8 pt type)."""
    head = [
        (240, 60, 11, "THE FIRST SCHEDULE"),
        (186, 90, 10, "I.–OFFENCES UNDER THE INDIAN PENAL CODE"),
        (258, 110, 8, "Punishment"),
        (330, 110, 8, "Cognizable or non-"),
        (70, 125, 8, "1"), (170, 125, 8, "2"), (318, 125, 8, "3"), (390, 125, 8, "4"), (466, 125, 8, "5"), (529, 125, 8, "6"),
    ]  # fmt: skip
    body = [
        # s.354C: two sub-rows (first / second conviction), the second with a blank offence cell; the entry was inserted by an amending Act
        (60, 160, 8, "354C"), (97, 160, 8, "Voyeurism."), (258, 160, 8, "Imprisonment for 3 years and fine."),
        (365, 160, 8, "Cognizable"), (440, 160, 8, "Bailable"), (510, 160, 8, "Any Magistrate."),
        (258, 178, 8, "Imprisonment for 7 years for second conviction."), (365, 178, 8, "Cognizable"), (440, 178, 8, "Non-bailable"),
        (510, 178, 8, "Any Magistrate.]"),
        # s.355: Ditto under the amended entry whose sub-rows differ: unresolved; s.356 repeats it
        (60, 200, 8, "355"), (97, 200, 8, "Assault with intent to dishonour."), (294, 200, 8, "Ditto"), (365, 200, 8, "Non-cognizable"),
        (460, 200, 8, "Ditto"), (520, 200, 8, "Ditto."),
        (60, 220, 8, "356"), (97, 220, 8, "Assault in attempt to commit theft."), (258, 220, 8, "Imprisonment for 2 years, or fine, or both."),
        (365, 220, 8, "Cognizable"), (460, 220, 8, "Ditto"), (520, 220, 8, "Ditto."),
        # s.225A: a heading line with no other cell, then sub-rows (a) and (b) only 12 pt apart
        (60, 250, 8, "225A"), (97, 250, 8, "Omission to apprehend, in cases not otherwise provided for:-"),
        (97, 262, 8, "(a) intentional omission;"), (258, 262, 8, "Imprisonment for 3 years, or fine, or both."),
        (365, 262, 8, "Non-cognizable"), (440, 262, 8, "Bailable"), (480, 262, 8, "Magistrate of the first class."),
        (97, 274, 8, "(b) negligent omission."), (258, 274, 8, "Simple imprisonment for 2 years, or fine, or both."),
        (384, 274, 8, "Ditto"), (460, 274, 8, "Ditto"), (510, 274, 8, "Any Magistrate."),
        # s.501: the section number and the offence printed as one PDF line
        (63, 300, 8, "501(a) Printing defamatory matter."), (258, 300, 8, "Simple imprisonment for 2 years, or fine, or both."),
        (365, 300, 8, "Non-cognizable"), (440, 300, 8, "Bailable"), (510, 300, 8, "Court of Session."),
        # s.498A: a conditional cognizable cell
        (60, 330, 8, "498A"), (97, 330, 8, "Cruelty by husband."), (258, 330, 8, "Imprisonment for three years and fine."),
        (365, 330, 8, "Cognizable if information"), (365, 340, 8, "is given by the person aggrieved."),
        (440, 330, 8, "Non-bailable"), (480, 330, 8, "Magistrate of the first class."),
    ]  # fmt: skip
    part2 = [
        (186, 400, 10, "II.–CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS"),
        (64, 430, 8, "If punishable with death"), (349, 430, 8, "Cognizable"), (402, 430, 8, "Non-bailable"), (483, 430, 8, "Court of Session."),
    ]  # fmt: skip
    return _pdf(tmp_path / "sched2.pdf", [head + body + part2])


def test_first_schedule_hard_cases(tmp_path):
    rows, notes = gap.parse_first_schedule(_schedule_pdf(tmp_path))
    by = {r["section"]: r for r in rows}
    assert list(by) == ["354C", "355", "356", "225A", "501", "498A"]  # Part II on the same page is not read
    c = by["354C"]
    assert len(c["subrows"]) == 2 and c["subrows"][1]["offence"] is None
    assert (c["cognisable"], c["bailable"], c["max_punishment"]) == (True, None, "7 years")  # bailable differs by sub-row
    s355 = by["355"]
    assert (s355["cognisable"], s355["bailable"], s355["punishment"], s355["max_punishment"]) == (False, None, None, None)
    assert s355["triable_by"] == "Any Magistrate"  # both sub-rows above agree, so that Ditto is read
    assert set(s355["subrows"][0]["ditto_ambiguous"]) == {"punishment", "bailable"}
    assert "bailable" in s355["ditto_from_amended_entry"]
    assert by["356"]["bailable"] is None and by["356"]["max_punishment"] == "2 years"
    a = by["225A"]
    assert a["offence"].startswith("Omission to apprehend") and "(b) negligent omission." in a["offence"]
    assert len(a["subrows"]) == 2 and (a["cognisable"], a["bailable"], a["max_punishment"]) == (False, True, "3 years")
    assert a["triable_by"] == "Magistrate of the first class | Any Magistrate"
    assert by["501"]["offence"] == "Printing defamatory matter." and by["501"]["triable_by"] == "Court of Session"
    assert by["498A"]["cognisable"] is None and by["498A"]["bailable"] is False
    assert by["498A"]["subrows"][0]["cognisable_text"].startswith("Cognizable if information")
    assert any(n.startswith("s.355") for n in notes)


def test_schedule_table_and_meta_name_the_source(tmp_path):
    pdf = _schedule_pdf(tmp_path)
    rows, notes = gap.parse_first_schedule(pdf)
    table, meta = gap.schedule_table(rows, notes, pdf, "2026-11-13")
    assert all(r["code"] == "IPC" and r["source"] == {"url": gap.CRPC_URL, "sha256": gap.sha256_of(pdf)} for r in table)
    assert set(table[0]) >= {"section", "offence", "punishment", "max_punishment", "cognisable", "bailable", "triable_by", "subrows"}
    assert meta["coverage"]["rows"] == 6 and meta["coverage"]["bailable_non_null"].startswith("3/6")
    assert meta["generated"] == "2026-11-13" and meta["source_sha256"] == gap.sha256_of(pdf)


def test_main_writes_the_schedule_table_offline(tmp_path, capsys):
    pdf = _schedule_pdf(tmp_path)
    out = tmp_path / "configs" / "fs.jsonl"
    assert gap.main(["--only", "schedule", "--crpc-pdf", str(pdf), "--out", str(tmp_path / "gaps"), "--schedule-out", str(out)]) == 0
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [r["section"] for r in rows] == ["354C", "355", "356", "225A", "501", "498A"]
    assert json.loads(out.with_suffix(".meta.json").read_text(encoding="utf-8"))["coverage"]["rows"] == 6
    flags = [json.loads(x) for x in (tmp_path / "gaps" / "first_schedule_ipc.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(r["text"] == "" for r in flags) and {r["section"] for r in flags} <= {r["section"] for r in rows}
    assert "not the pinned PDF" in capsys.readouterr().err  # the synthetic PDF is not the pinned CrPC file: warned, not refused


_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "first_schedule_crpc_ipc.jsonl"


def test_committed_schedule_table_is_well_formed():
    rows = [json.loads(x) for x in _CONFIG.read_text(encoding="utf-8").splitlines()]
    assert len(rows) >= 390 and len({r["section"] for r in rows}) == len(rows)
    for r in rows:
        assert r["code"] == "IPC" and r["source"]["sha256"] == gap.CRPC_SHA256
        assert r["bailable"] in (True, False, None) and r["cognisable"] in (True, False, None)
        assert r["max_punishment"] is None or r["max_punishment"] in ("death", "life imprisonment", "fine") or re.fullmatch(
            r"\d+ (years?|months?|weeks?|days?|hours?)", r["max_punishment"]
        )
    by = {r["section"]: r for r in rows}  # cells as printed in the official text (pages 195 to 222 of the pinned PDF)
    assert (by["302"]["bailable"], by["302"]["max_punishment"]) == (False, "death")
    assert (by["323"]["bailable"], by["323"]["cognisable"]) == (True, False)
    assert (by["420"]["bailable"], by["420"]["max_punishment"]) == (False, "7 years")
    assert by["143"]["bailable"] is True and by["341"]["bailable"] is True


def test_ndps_rows_cover_the_penal_sections(tmp_path):
    page = [
        (72, 80, 10, "1. Short title.-This Act may be called the Act."),
        (72, 100, 10, "2. Definitions.-In this Act, small quantity means a quantity."),
        (72, 120, 10, "3. Punishment for contravention.-Whoever contravenes shall be punishable,-"),
        (72, 134, 10, "(a) with rigorous imprisonment for a term which may extend to one year;"),
        (72, 148, 10, "(b) with rigorous imprisonment for a term which may extend to twenty years."),
        (72, 170, 10, "4. Offences to be cognizable and non-bailable.-(1) Notwithstanding anything,-"),
        (72, 184, 10, "(a) every offence punishable under this Act shall be cognizable;"),
    ]
    rows, missing = gap.build_rows("NDPS", _pdf(tmp_path / "ndps.pdf", [page]), gap.NDPS_URL, None, "2026-11-13")
    by = {r["section"]: r for r in rows}
    assert missing == [] and list(by) == ["1", "2", "3", "4"]
    assert by["3"]["max_punishment"] == "20 years"  # the heavier of its two limbs
    assert "cognisable" not in by["2"] and "max_punishment" not in by["2"]


def _bnss_schedule_pdf(tmp_path: Path) -> Path:
    """A Gazette-style BNSS First Schedule page: fixed columns (58, 94, 193, 298, 385, 454), entries numbered '318(2)', and one PDF
    line that holds the ends of two cells, as the Gazette prints them."""
    fused = "Imprisonment for life"
    while 193 + pymupdf.get_text_length(fused + " ", fontname="helv", fontsize=8) < 290:
        fused += " "
    fused += "Cognizable."
    page = [
        (174, 60, 10, "I.-OFFENCES UNDER THE BHARATIYA NYAYA SANHITA"),
        (63, 80, 8, "Section"), (134, 80, 8, "Offence"), (217, 80, 8, "Punishment"),
        (73, 95, 8, "1"), (145, 95, 8, "2"), (235, 95, 8, "3"), (319, 95, 8, "4"), (409, 95, 8, "5"), (490, 95, 8, "6"),
        (58, 120, 8, "103(1)"), (94, 120, 8, "Murder."), (193, 120, 8, fused), (385, 120, 8, "Non-bailable."), (454, 120, 8, "Court of Session."),
        (193, 130, 8, "and fine."),
        (58, 150, 8, "318(2)"), (94, 150, 8, "Cheating."), (193, 150, 8, "Imprisonment for 3 years,"), (298, 150, 8, "Non-cognizable."),
        (385, 150, 8, "Bailable."), (454, 150, 8, "Any Magistrate."),
        (193, 160, 8, "or fine, or both."),
        (58, 180, 8, "318(4)"), (94, 180, 8, "Cheating and dishonestly"), (193, 180, 8, "Imprisonment for 7 years"),
        (298, 180, 8, "Cognizable."), (385, 180, 8, "Non-bailable."), (454, 180, 8, "Magistrate of the first"),
        (94, 190, 8, "inducing delivery of property."), (193, 190, 8, "and fine."), (454, 190, 8, "class."),
        (180, 230, 10, "II.-CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS"),
        (57, 250, 8, "If punishable with death"), (298, 250, 8, "Cognizable."), (385, 250, 8, "Non-bailable."),
    ]  # fmt: skip
    return _pdf(tmp_path / "bnss_sched.pdf", [page])


def test_bnss_schedule_rows_keep_the_sub_section_and_split_fused_cells(tmp_path):
    rows, _notes = gap.parse_bnss_schedule(_bnss_schedule_pdf(tmp_path))
    by = {r["section"]: r for r in rows}
    assert list(by) == ["103", "318"]  # Part II is not read
    m = by["103"]
    assert m["punishment"] == "Imprisonment for life and fine." and (m["cognisable"], m["bailable"]) == (True, False)
    assert m["max_punishment"] == "life imprisonment" and m["subrows"][0]["subsection"] == "(1)"
    c = by["318"]
    assert [x["subsection"] for x in c["subrows"]] == ["(2)", "(4)"]
    assert [x["bailable"] for x in c["subrows"]] == [True, False] and c["bailable"] is None and c["max_punishment"] == "7 years"
    assert c["subrows"][1]["triable_by"] == "Magistrate of the first class"
    table, meta = gap.schedule_table(rows, _notes, tmp_path / "bnss_sched.pdf", "2026-11-13", code="BNS")
    assert {r["code"] for r in table} == {"BNS"} and table[0]["source"]["url"] == gap.BNSS_URL
    assert meta["script"].endswith("--only bnss_schedule")


def test_committed_bns_schedule_table_is_well_formed():
    rows = [json.loads(x) for x in (_CONFIG.parent / "first_schedule_bnss_bns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) >= 280 and len({r["section"] for r in rows}) == len(rows)
    assert all(r["code"] == "BNS" and r["source"]["sha256"] == gap.BNSS_SHA256 for r in rows)
    by = {r["section"]: r for r in rows}  # cells as printed in the Gazette (BNSS 2023, First Schedule, Part I)
    assert (by["103"]["bailable"], by["103"]["max_punishment"]) == (False, "death")
    assert [(x["subsection"], x["bailable"]) for x in by["318"]["subrows"]] == [("(2)", True), ("(3)", True), ("(4)", False)]
