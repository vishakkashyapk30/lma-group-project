"""T2 (new tests): the truth rows say exactly what an extractor should find in each rendered bundle, and the Pillow degrader behaves."""

from __future__ import annotations

import re

import pytest

from tests.unit.testsets._helpers import read_rows, write_t1_dir
from vakeel_sahayak.testsets import degrade, rendering
from vakeel_sahayak.testsets.t2_messy_bundles import build_t2, build_t2_with

DEVANAGARI = re.compile("[ऀ-ॿ]")


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract(pdf) -> list[str]:
    import fitz

    with fitz.open(str(pdf)) as doc:
        return [p.get_text() for p in doc]


def test_paginate_is_the_truth_of_the_pages_and_normalises_punctuation():
    pages = rendering.paginate("A’s “quoted” order – dated 20.08.2024\n\n" + "word " * 1600)
    assert len(pages) >= 2 and pages[0].startswith("A's \"quoted\" order - dated 20.08.2024")
    assert rendering.paginate("") == [""]


def test_legacy_encode_has_no_devanagari_and_keeps_digits_and_latin():
    out = rendering.legacy_encode("प्रथम सूचना रिपोर्ट सं. 112/2024 FIR ९")
    assert not DEVANAGARI.search(out) and "112/2024" in out and "FIR" in out and out.endswith("9")


def test_k1_and_k5_text_layers_equal_the_truth_pages(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=6)
    build_t2(str(t1), None, None, str(tmp_path / "t2"))
    truth = read_rows(tmp_path / "t2" / "truth.jsonl")
    checked = 0
    for t in truth:
        if t["kind"] in ("K1", "K5"):
            got = extract(tmp_path / "t2" / t["pdf"])
            assert len(got) == len(t["pages"])
            assert [squash(g) for g in got] == [squash(p["text"]) for p in t["pages"]], t["bundle_id"]
            checked += 1
    assert checked >= 6


def test_image_kinds_have_no_text_and_k6_has_gibberish_not_devanagari(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=3)
    build_t2(str(t1), None, None, str(tmp_path / "t2"))
    for t in read_rows(tmp_path / "t2" / "truth.jsonl"):
        text = "".join(extract(tmp_path / "t2" / t["pdf"]))
        if t["kind"] in ("K2", "K3", "K4"):
            assert text.strip() == "" and t["text_layer"] == "none"
        if t["kind"] == "K6":
            assert text.strip() and not DEVANAGARI.search(text) and t["text_layer"] == "legacy_gibberish"
            assert all(DEVANAGARI.search(p["text"]) for p in t["pages"][:1])  # the truth is the Hindi text


def test_companion_fields_are_in_every_bundle_and_custody_fields_only_with_a_certificate(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=10)
    build_t2(str(t1), None, None, str(tmp_path / "t2"))
    for t in read_rows(tmp_path / "t2" / "truth.jsonl"):
        types = {d["type"] for d in t["documents"]}
        assert {"COURT_ORDER", "FIR", "REMAND_ORDER"} <= types
        assert ("custody_days" in t["fields"]) == ("CUSTODY_CERTIFICATE" in types)
        assert t["fields"]["fir"]["number"] and t["fields"]["first_remand"]


def test_small_builds_report_sizes_and_what_is_missing(tmp_path, require_pymupdf):
    t1 = write_t1_dir(tmp_path, n=8)
    m = build_t2_with(str(t1), None, None, str(tmp_path / "t2"), n_cases=5, kinds=("K1", "K6"))
    assert m.size == 10 and m.details["bundles_per_kind"] == {"K1": 5, "K6": 5} and m.details["hldc_available"] is False
    assert any("HLDC" in x for x in m.details["not_built"])


def test_the_blind_slice_is_not_used(tmp_path, require_pymupdf):
    import json

    t1 = write_t1_dir(tmp_path, n=40)
    keep = [f"t1-{i:03d}" for i in range(20)]
    (t1 / "manifest_open.json").write_text(json.dumps({"slice": "open", "case_ids": keep}), encoding="utf-8")
    build_t2_with(str(t1), None, None, str(tmp_path / "t2"), n_cases=30, kinds=("K1",))
    assert {t["case_id"] for t in read_rows(tmp_path / "t2" / "truth.jsonl")} <= set(keep)


# ---------------------------------------------------------------- the Pillow degrader
def png() -> bytes:
    import io

    from PIL import Image

    img = Image.new("L", (160, 220), 255)
    for y in range(20, 200, 12):
        for x in range(10, 150, 3):
            img.putpixel((x, y), 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("severity", ["light", "medium", "heavy"])
def test_degrader_is_deterministic_and_seed_dependent(severity):
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    img = png()
    assert degrade.degrade_page(img, severity, seed=3) == degrade.degrade_page(img, severity, seed=3)
    assert degrade.degrade_page(img, severity, seed=3) != degrade.degrade_page(img, severity, seed=4)


def test_heavier_severity_changes_more_pixels():
    pytest.importorskip("PIL")
    np = pytest.importorskip("numpy")
    import io

    from PIL import Image

    img = png()
    base = np.asarray(Image.open(io.BytesIO(img)).convert("L"), dtype=float)
    diff = {s: float(np.abs(np.asarray(Image.open(io.BytesIO(degrade.degrade_page(img, s, seed=1))).convert("L"), dtype=float) - base).mean()) for s in ("light", "heavy")}
    assert diff["heavy"] > diff["light"]
