"""Local Tesseract OCR adapter used when Surya is unavailable.

The adapter deliberately calls the system binary instead of requiring the optional
``pytesseract`` package.  It is selected only in ``VS_MODELS=auto|real`` by the
model factory, so the deterministic offline mode remains dependency-free.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from vakeel_sahayak.models.base import ModelUnavailable, OcrClient


def tesseract_languages() -> set[str]:
    """Language packs available to the local Tesseract binary (empty when absent)."""
    executable = shutil.which("tesseract")
    if not executable:
        return set()
    result = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, check=False, timeout=30)
    return {line.strip() for line in result.stdout.splitlines()[1:] if line.strip()}


class TesseractCliOcr(OcrClient):
    """Tesseract via its command-line interface, with English fallback when a requested pack is missing."""

    name = "tesseract-cli"

    @staticmethod
    def available() -> bool:
        """Whether a usable Tesseract binary and at least one language pack exist."""
        return bool(tesseract_languages())

    def __init__(self) -> None:
        self.last_note = ""

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """Return text, mean word confidence and boxes for a rendered page."""
        executable = shutil.which("tesseract")
        if not executable:
            raise ModelUnavailable("the tesseract binary is not installed", "ocr")
        available = tesseract_languages()
        requested = [item for item in lang.split("+") if item]
        selected = [item for item in requested if item in available] or (["eng"] if "eng" in available else [])
        if not selected:
            raise ModelUnavailable("Tesseract has no requested language data", "ocr")
        self.last_note = "" if len(selected) == len(requested) else f"tesseract data missing for {sorted(set(requested) - set(selected))}; read with {selected}"
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "page.png"
            image_path.write_bytes(image)
            result = subprocess.run(
                [executable, str(image_path), "stdout", "-l", "+".join(selected), "tsv"],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
        if result.returncode:
            detail = result.stderr.strip().splitlines()[0] if result.stderr.strip() else f"exit {result.returncode}"
            raise ModelUnavailable(f"Tesseract failed ({detail})", "ocr")
        lines: list[str] = []
        words: list[str] = []
        confidences: list[float] = []
        boxes: list[list[float]] = []
        current_key: tuple[str, str, str] | None = None
        for row in result.stdout.splitlines()[1:]:
            columns = row.split("\t")
            if len(columns) < 12 or not columns[11].strip():
                continue
            key = (columns[2], columns[3], columns[4])
            if current_key is not None and key != current_key:
                lines.append(" ".join(words))
                words = []
            current_key = key
            words.append(columns[11])
            try:
                confidences.append(max(0.0, float(columns[10])) / 100.0)
                x, y, width, height = (float(columns[index]) for index in (6, 7, 8, 9))
            except ValueError:
                continue
            boxes.append([x, y, x + width, y + height])
        if words:
            lines.append(" ".join(words))
        return "\n".join(lines), (sum(confidences) / len(confidences) if confidences else 0.0), boxes
