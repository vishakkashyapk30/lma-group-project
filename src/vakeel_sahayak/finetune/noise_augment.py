"""Step 4: for 30% of kept pairs, replace the input with Surya OCR of an Augraphy-degraded rendering of the same text; target unchanged (plan §12).

The facts text is drawn onto a page image (`testsets.rendering`), degraded with `testsets.degrade.degrade_page` (Pillow/NumPy; Augraphy when
requested, Sarkar et al., ICDAR 2023) and read back with the configured OCR client (Surya or Tesseract). Which pairs are noisy is a seeded
sample, and every noisy pair gets its own degradation seed, so a run is reproducible and the noise is not one pattern copied 30 times.
Needs PyMuPDF (page rendering); the OCR client falls back as configured in `models.factory.get_ocr`.
"""

from __future__ import annotations

import random
import re
from typing import Any

from vakeel_sahayak.finetune._io import read_rows, write_rows

SEED = 20260
SEVERITIES = ("light", "medium", "heavy")


def _lang(text: str) -> str:
    return "hi" if re.search(r"[ऀ-ॿ]", text) else "en"


def noisy_text(text: str, seed: int, severity: str = "medium") -> str:
    """OCR of a degraded rendering of `text` (all pages joined); an empty string when the OCR read nothing."""
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.testsets import degrade, rendering

    lang = _lang(text)
    ocr = factory.get_ocr()
    parts: list[str] = []
    for page_no, page in enumerate(rendering.paginate(text, lang) or [text]):
        image = rendering._page_png(page, lang)
        image = degrade.degrade_page(image, severity=severity, seed=seed * 1000 + page_no)
        result = ocr.ocr(image, lang)
        parts.append(str(result[0] if isinstance(result, tuple) else result).strip())
    return "\n".join(p for p in parts if p)


def select_noisy(n_rows: int, fraction: float, seed: int = SEED) -> list[int]:
    """Sorted row indices of the seeded sample that gets noise: round(fraction * n_rows) of them, spread over the file."""
    k = round(fraction * n_rows)
    return sorted(random.Random(seed).sample(range(n_rows), k))


def augment_pairs(pairs_path: str, out_path: str, fraction: float = 0.3) -> int:
    """Create noisy inputs.

    Args:
        pairs_path: JSONL of {"doc_id", "facts", "dossier"} rows (the kept pairs)
        out_path: same rows, with the facts of the selected share replaced by OCR text; every dossier unchanged
        fraction: share of pairs made noisy, in [0, 1]

    Returns:
        Number augmented.
    """
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"fraction must be in [0, 1], got {fraction}")
    rows: list[dict[str, Any]] = list(read_rows(pairs_path))
    chosen = select_noisy(len(rows), fraction)
    done = 0
    for idx in chosen:
        text = noisy_text(str(rows[idx].get("facts", "")), seed=idx)
        if text:  # nothing read: keep the clean input rather than train on an empty one
            rows[idx] = {**rows[idx], "facts": text}
            done += 1
    write_rows(out_path, rows)
    return done


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.noise_augment PAIRS OUT [FRACTION]."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (2, 3):
        print("usage: python -m vakeel_sahayak.finetune.noise_augment PAIRS.jsonl OUT.jsonl [FRACTION]")
        return 2
    print(f"augmented {augment_pairs(args[0], args[1], float(args[2]) if len(args) == 3 else 0.3)} pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
