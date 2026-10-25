"""T2 messy bundles (plan §15.2): 100 T1 cases, each bundled with 2-3 constructed companion documents (FIR on the IIF-1 layout, remand order,
custody certificate) filled with the case's G3 values and Faker names, rendered as K1-K6; plus ~200 HLDC Hindi documents and, if
available, e-SCR Hindi judgments; about 600 bundles, 4,800 pages. Answers come from CONSTRUCTION: page text, document boundaries and
types, field values. Also the companion makers, the renderers, the degrader and the scripted counsel of §15.5.

# ASSUMPTION: T2 output = out_dir/bundles/<bundle_id>.pdf plus out_dir/truth.jsonl with one row per bundle:
#   {"bundle_id", "case_id", "kind": "K1".."K6", "pages": [{"page", "text"}], "documents": [{"doc_id", "type", "pages": [a, b]}],
#    "fields": {<G3 field>: value}}
# PDF reading needs PyMuPDF (`require_pymupdf`).
"""

from __future__ import annotations

import re
import struct
import zlib

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_rows, write_t1_dir
from vakeel_sahayak.testsets import companions, degrade, rendering
from vakeel_sahayak.testsets.t2_messy_bundles import build_t2, scripted_counsel

G3 = {
    "fir": {"number": "112/2024", "police_station": "PS-1", "date": "2024-08-14"},
    "offence_date": "2024-08-10",
    "sections": ["318(4) BNS"],
    "arrest_date": "2024-08-20",
    "first_remand": "2024-08-21",
    "custody_days": 167,
}
DEVANAGARI = re.compile("[ऀ-ॿ]")


def date_forms(iso: str) -> list[str]:
    y, m, d = iso.split("-")
    return [iso, f"{d}.{m}.{y}", f"{d}-{m}-{y}", f"{d}/{m}/{y}"]


def has_date(text: str, iso: str) -> bool:
    return any(f in text for f in date_forms(iso))


# ---------------------------------------------------------------- companion documents (filled with G3 values)
def test_fir_carries_the_case_values():
    """The FIR is filled with the G3 FIR number, station and sections, so every field has a known answer."""
    text = companions.make_fir(G3, lang="en")
    assert "112/2024" in text and "PS-1" in text and "318(4)" in text
    assert has_date(text, "2024-08-10") or has_date(text, "2024-08-14")


def test_hindi_fir_is_devanagari_with_the_same_numbers():
    """lang='hi' renders Hindi (NLLB-200 en->hi); numbers and the section stay as they are, so answers are known by construction."""
    text = companions.make_fir(G3, lang="hi")
    assert DEVANAGARI.search(text) and "112/2024" in text and "318(4)" in text


def test_remand_order_carries_arrest_and_first_remand_dates():
    text = companions.make_remand_order(G3)
    assert has_date(text, "2024-08-21")
    assert "remand" in text.lower()


def test_custody_certificate_carries_the_custody_figures():
    text = companions.make_custody_certificate(G3)
    assert has_date(text, "2024-08-20")
    assert "custody" in text.lower()


@pytest.mark.parametrize("maker", [companions.make_fir, companions.make_remand_order, companions.make_custody_certificate])
def test_companions_are_deterministic_and_use_no_real_party_names(maker):
    """Same record -> same text; and names come from Faker (no name from a real case file): the text holds no case-0007 party name."""
    assert maker(G3) == maker(G3)
    for real in ("Ramesh Kumar Yadav", "Sunita Devi Sharma"):
        assert real not in maker(G3)


def test_companion_values_follow_the_record():
    """Change the FIR number in the record and the document changes with it (the text is built from G3, not canned)."""
    other = {**G3, "fir": {**G3["fir"], "number": "777/2023"}}
    assert "777/2023" in companions.make_fir(other, lang="en") and "112/2024" not in companions.make_fir(other, lang="en")


# ---------------------------------------------------------------- renderers K1, K2, K4, K6 and the K3 degrader
def page_texts(pdf: str) -> list[str]:
    import fitz  # PyMuPDF

    with fitz.open(pdf) as doc:
        return [p.get_text() for p in doc]


def page_has_image(pdf: str) -> bool:
    import fitz

    with fitz.open(pdf) as doc:
        return all(p.get_images() for p in doc)


def test_k1_born_digital_has_a_text_layer(tmp_path, require_pymupdf):
    out = tmp_path / "k1.pdf"
    rendering.render_born_digital("FIR No. 112/2024 under Section 318(4) BNS", str(out))
    assert "112/2024" in " ".join(page_texts(str(out)))


def test_k2_scanned_is_image_only(tmp_path, require_pymupdf):
    """K2: pages are images; the text layer is empty, so extraction needs OCR."""
    out = tmp_path / "k2.pdf"
    rendering.render_scanned("FIR No. 112/2024 under Section 318(4) BNS", str(out))
    assert "".join(page_texts(str(out))).strip() == "" and page_has_image(str(out))


def test_k4_phone_photo_is_image_only(tmp_path, require_pymupdf):
    out = tmp_path / "k4.pdf"
    rendering.render_phone_photo("Remand order dated 21.08.2024", str(out))
    assert "".join(page_texts(str(out))).strip() == "" and page_has_image(str(out))


def test_k5_hindi_born_digital_has_unicode_devanagari(tmp_path, require_pymupdf):
    out = tmp_path / "k5.pdf"
    rendering.render_born_digital("प्रथम सूचना रिपोर्ट सं. 112/2024", str(out), lang="hi")
    assert DEVANAGARI.search(" ".join(page_texts(str(out))))


def test_k6_legacy_font_text_layer_decodes_to_latin_gibberish(tmp_path, require_pymupdf):
    """K6: Hindi typed in a Kruti Dev-style font: the text layer is non-empty but holds no Devanagari (plan §4.2 legacy-font rung)."""
    out = tmp_path / "k6.pdf"
    rendering.render_legacy_font("प्रथम सूचना रिपोर्ट सं. 112/2024", str(out))
    text = " ".join(page_texts(str(out)))
    assert text.strip() and not DEVANAGARI.search(text)


def png_bytes(w: int = 64, h: int = 64) -> bytes:
    """A small grey-gradient PNG built with zlib/struct (no imaging library)."""
    raw = b"".join(b"\x00" + bytes((x * 4 + y) % 256 for x in range(w)) for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_k3_degrade_is_deterministic_for_a_seed_and_differs_across_seeds():
    pytest.importorskip("PIL")  # RECONCILED: the degrader is Pillow/NumPy (docs say Augraphy only if it installs cleanly; it pulls OpenCV), so these need Pillow, not Augraphy
    img = png_bytes()
    a, b, c = degrade.degrade_page(img, "medium", seed=1), degrade.degrade_page(img, "medium", seed=1), degrade.degrade_page(img, "medium", seed=2)
    assert a == b and a != c and a != img


def test_degrade_severity_changes_the_output_and_unknown_severity_is_rejected():
    pytest.importorskip("PIL")  # RECONCILED: see test_k3_degrade_is_deterministic_for_a_seed_and_differs_across_seeds
    img = png_bytes()
    assert degrade.degrade_page(img, "light", seed=0) != degrade.degrade_page(img, "heavy", seed=0)
    with pytest.raises(ValueError):
        degrade.degrade_page(img, "catastrophic", seed=0)


# ---------------------------------------------------------------- the T2 build
def build(tmp_path, n_cases: int = 12, **kw):
    t1 = write_t1_dir(tmp_path, n=n_cases)
    out = tmp_path / "t2"
    manifest = build_t2(str(t1), kw.get("hldc"), kw.get("escr"), str(out))
    return manifest, read_rows(out / "truth.jsonl"), out


def test_each_case_is_bundled_with_two_or_three_companions(tmp_path, require_pymupdf):
    """Every bundle holds the T1 case's own document plus 2-3 constructed companions: 3 or 4 documents."""
    m, truth, _ = build(tmp_path)
    assert_manifest(m, "T2")
    assert truth and all(3 <= len(t["documents"]) <= 4 for t in truth)


def test_document_boundaries_types_and_pages_tile_the_bundle(tmp_path, require_pymupdf):
    """Truth is exact: documents are consecutive, non-overlapping page ranges covering every page, each with a document type."""
    _, truth, _ = build(tmp_path)
    for t in truth:
        spans = [tuple(d["pages"]) for d in t["documents"]]
        assert spans[0][0] == 1 and spans[-1][1] == len(t["pages"])
        assert all(b[0] == a[1] + 1 for a, b in zip(spans, spans[1:]))
        assert all(d["type"] for d in t["documents"])


def test_all_six_input_kinds_k1_to_k6_appear(tmp_path, require_pymupdf):
    _, truth, _ = build(tmp_path, n_cases=30)
    assert {t["kind"] for t in truth} == {f"K{i}" for i in range(1, 7)}


def test_field_values_in_truth_are_the_case_g3_values(tmp_path, require_pymupdf):
    """Field answers come from the T1 case's G3, copied unchanged."""
    _, truth, _ = build(tmp_path)
    by_case = {c["case_id"]: c for c in read_rows(tmp_path / "t1" / "cases.jsonl")}
    for t in truth:
        if t["case_id"] in by_case:
            g3 = by_case[t["case_id"]]["gold"]["G3"]
            assert t["fields"]["arrest_date"] == g3["arrest_date"] and t["fields"]["fir"]["number"] == g3["fir"]["number"]


def test_planned_scale_with_hldc_documents(tmp_path, require_pymupdf):
    """Plan: 100 T1 cases -> ~600 bundles / ~4,800 pages once the ~200 HLDC Hindi documents are added; a smaller pool scales down, not up."""
    hldc = tmp_path / "hldc"
    hldc.mkdir()
    (hldc / "docs.jsonl").write_text("\n".join('{"doc_id": "h%d", "text": "प्रथम सूचना रिपोर्ट"}' % i for i in range(20)) + "\n", encoding="utf-8")
    m, truth, _ = build(tmp_path, n_cases=10, hldc=str(hldc))
    assert m.size == len(truth) >= 10 + 20


def test_escr_is_optional(tmp_path, require_pymupdf):
    """'if available': both optional inputs may be None."""
    m, truth, _ = build(tmp_path, hldc=None, escr=None)
    assert m.size == len(truth) > 0


def test_build_is_deterministic(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=8)
    a, b = tmp_path / "a", tmp_path / "b"
    build_t2(str(t1), None, None, str(a))
    build_t2(str(t1), None, None, str(b))
    assert (a / "truth.jsonl").read_bytes() == (b / "truth.jsonl").read_bytes()


# ---------------------------------------------------------------- scripted counsel (plan §15.5)
TRUTH = {"arrest_date": "2024-08-20", "fir_number": "112/2024", "clean_copy": "CLEAN COPY OF PAGE 3"}


def test_scripted_counsel_gives_true_values_when_asked():
    counsel = scripted_counsel(TRUTH)
    assert "20.08.2024" in counsel("What is the date of arrest?") or "2024-08-20" in counsel("What is the date of arrest?")
    assert "112/2024" in counsel("What is the FIR number?")


def test_scripted_counsel_supplies_a_clean_copy_when_asked_for_one():
    """'It knows the true values and supplies a clean copy when asked for one.'"""
    counsel = scripted_counsel(TRUTH)
    assert counsel("Page 3 of the FIR is unreadable. Can you upload a clearer copy?") == TRUTH["clean_copy"]


def test_scripted_counsel_never_invents_an_unknown_value():
    """A question about something outside the truth gets a non-answer, not a made-up value."""
    answer = scripted_counsel(TRUTH)("What is the accused's shoe size?")
    assert not re.search(r"\d", answer)
