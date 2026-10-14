"""Fine-tuning data step 4 (plan §12): for 30% of the kept pairs the input is replaced by OCR output of a degraded rendering of the
same text (Augraphy + Surya); the target dossier is unchanged, so the extractor learns to read OCR noise.

The image pipeline is replaced by two spies: `testsets.degrade.degrade_page` (Augraphy) and the OCR client from `models.factory`
(Surya). The OCR stand-in corrupts digits the way a bad scan does, so a noisy input is recognisably different from the clean one.
# SKELETON-GAP: how the text becomes an image before degrading is not specified (testsets.rendering only renders PDFs). The tests
# that run `augment_pairs` need PyMuPDF for that step (`require_pymupdf`); the selection logic is what they check.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.finetune._helpers import pair_row, patch_everywhere, read_rows, write_jsonl
from vakeel_sahayak.finetune.noise_augment import augment_pairs
from vakeel_sahayak.models.base import OcrClient


class SpyOcr(OcrClient):
    """Surya stand-in: returns a fixed noisy transcript derived from the image bytes, and counts calls."""

    def __init__(self) -> None:
        self.calls = 0

    def ocr(self, image: bytes, lang: str):
        self.calls += 1
        return "NOISY-OCR " + str(abs(hash(image)) % 10**6), 0.6, []


class Rig:
    def __init__(self, monkeypatch) -> None:
        self.degraded: list[tuple[str, int]] = []  # (severity, seed)
        self.ocr = SpyOcr()

        def degrade(image: bytes, severity: str = "medium", seed: int = 0) -> bytes:
            self.degraded.append((severity, seed))
            return b"DEGRADED" + bytes([seed % 256]) + image[:8]

        patch_everywhere(monkeypatch, "vakeel_sahayak.testsets.degrade", "degrade_page", degrade)
        patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_ocr", lambda *a, **k: self.ocr)


@pytest.fixture()
def rig(monkeypatch, require_pymupdf):
    return Rig(monkeypatch)


def make_pairs(tmp_path, n: int):
    rows = [pair_row(f"o{i:03d}") for i in range(n)]
    return write_jsonl(tmp_path / "pairs.jsonl", rows), rows


def test_signature_and_default_fraction_is_thirty_percent():
    """augment_pairs(pairs_path, out_path, fraction=0.3): 30% is the plan's share."""
    params = inspect.signature(augment_pairs).parameters
    assert list(params) == ["pairs_path", "out_path", "fraction"]
    assert params["fraction"].default == 0.3


def test_thirty_percent_of_pairs_get_a_noisy_input(tmp_path, rig):
    """100 pairs -> 30 augmented; the function returns the number augmented and every pair stays in the output."""
    src, rows = make_pairs(tmp_path, 100)
    out = tmp_path / "noisy.jsonl"
    n = augment_pairs(str(src), str(out))
    assert n == 30
    written = read_rows(out)
    assert [r["doc_id"] for r in written] == [r["doc_id"] for r in rows]
    changed = [w for w, r in zip(written, rows) if w["facts"] != r["facts"]]
    assert len(changed) == 30


def test_the_target_dossier_is_never_changed(tmp_path, rig):
    """Plan §12 step 4: 'the target dossier is unchanged' for augmented and unaugmented pairs alike."""
    src, rows = make_pairs(tmp_path, 40)
    out = tmp_path / "noisy.jsonl"
    augment_pairs(str(src), str(out))
    assert [r["dossier"] for r in read_rows(out)] == [r["dossier"] for r in rows]


def test_the_noisy_input_is_the_ocr_output_of_a_degraded_rendering(tmp_path, rig):
    """Every augmented input comes from the OCR client, once per augmented pair, on an image that went through degrade_page."""
    src, rows = make_pairs(tmp_path, 20)
    out = tmp_path / "noisy.jsonl"
    n = augment_pairs(str(src), str(out), fraction=0.3)
    assert n == 6 and rig.ocr.calls == 6 and len(rig.degraded) == 6
    noisy = [w["facts"] for w, r in zip(read_rows(out), rows) if w["facts"] != r["facts"]]
    assert len(noisy) == 6 and all("NOISY-OCR" in t for t in noisy)


def test_unselected_pairs_are_byte_identical(tmp_path, rig):
    """The other 70%: the row is copied as it was (clean facts input, same dossier)."""
    src, rows = make_pairs(tmp_path, 100)
    out = tmp_path / "noisy.jsonl"
    augment_pairs(str(src), str(out))
    same = [w for w, r in zip(read_rows(out), rows) if w == r]
    assert len(same) == 70


@pytest.mark.parametrize(("fraction", "expected"), [(0.0, 0), (0.1, 5), (0.5, 25), (1.0, 50)])
def test_fraction_controls_the_number_augmented(tmp_path, rig, fraction, expected):
    src, _ = make_pairs(tmp_path, 50)
    assert augment_pairs(str(src), str(tmp_path / "o.jsonl"), fraction=fraction) == expected


@pytest.mark.parametrize("fraction", [-0.1, 1.5])
def test_fraction_outside_zero_one_is_rejected(tmp_path, fraction):
    """ASSUMPTION: a share outside [0, 1] is a ValueError raised before any rendering."""
    src, _ = make_pairs(tmp_path, 5)
    with pytest.raises(ValueError):
        augment_pairs(str(src), str(tmp_path / "o.jsonl"), fraction=fraction)


def test_selection_and_degradation_are_deterministic(tmp_path, rig):
    """Seeds are fixed (plan §17 reproducibility): the same input gives the same selection and the same degradation seeds."""
    src, _ = make_pairs(tmp_path, 60)
    augment_pairs(str(src), str(tmp_path / "a.jsonl"))
    first = list(rig.degraded)
    rig.degraded.clear()
    augment_pairs(str(src), str(tmp_path / "b.jsonl"))
    assert rig.degraded == first
    assert read_rows(tmp_path / "a.jsonl") == read_rows(tmp_path / "b.jsonl")


def test_degradation_seeds_differ_between_pairs(tmp_path, rig):
    """Each augmented pair gets its own degradation (a different Augraphy seed), not one noise pattern copied 30 times."""
    src, _ = make_pairs(tmp_path, 100)
    augment_pairs(str(src), str(tmp_path / "o.jsonl"))
    assert len({seed for _, seed in rig.degraded}) == 30


def test_the_augmented_pairs_are_spread_over_the_file_not_a_prefix(tmp_path, rig):
    """The 30% is a sample, not the first 30 rows (a prefix would correlate noise with date order). ASSUMPTION: seeded sampling."""
    src, rows = make_pairs(tmp_path, 100)
    out = tmp_path / "noisy.jsonl"
    augment_pairs(str(src), str(out))
    idx = [i for i, (w, r) in enumerate(zip(read_rows(out), rows)) if w["facts"] != r["facts"]]
    assert idx != list(range(30)) and max(idx) > 60
