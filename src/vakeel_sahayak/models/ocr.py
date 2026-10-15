"""Surya (English+Hindi) with Tesseract fallback (plan §12). Heavy libraries are imported lazily."""

from __future__ import annotations

import importlib.util
import io
import shutil

from vakeel_sahayak.models.base import ModelUnavailable, OcrClient

_LANG_SURYA = {"eng": ["en"], "hin": ["hi"], "hin+eng": ["hi", "en"], "eng+hin": ["hi", "en"]}


class SuryaOcrClient(OcrClient):
    """Surya (English+Hindi) with Tesseract fallback (plan §12)."""

    def __init__(self) -> None:
        """Nothing is loaded until the first call."""
        self.name = "surya"
        self._predictors: tuple | None = None

    @staticmethod
    def has_surya() -> bool:
        """True when the surya package is installed."""
        return importlib.util.find_spec("surya") is not None

    @staticmethod
    def has_tesseract() -> bool:
        """True when pytesseract and the tesseract binary are both present."""
        return importlib.util.find_spec("pytesseract") is not None and shutil.which("tesseract") is not None

    @classmethod
    def available(cls) -> bool:
        """True when at least one OCR engine can run."""
        return cls.has_surya() or cls.has_tesseract()

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """OCR. Surya first; Tesseract when Surya is missing or fails.

        Args:
            image: page image bytes (PNG or JPEG)
            lang: 'eng', 'hin' or 'hin+eng'

        Returns:
            (text, conf, boxes).

        Raises:
            ModelUnavailable: neither engine is installed.
        """
        if lang not in _LANG_SURYA:
            raise ValueError(f"lang must be one of {sorted(_LANG_SURYA)}, got {lang!r}")
        if self.has_surya():
            try:
                result = self._surya(image, lang)
                self.name = "surya"
                return result
            except Exception:  # Surya's API changes between releases; fall through to Tesseract
                if not self.has_tesseract():
                    raise
        if self.has_tesseract():
            self.name = "tesseract"
            return self._tesseract(image, lang)
        raise ModelUnavailable("neither Surya nor Tesseract is installed", "ocr")

    def _surya(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        from PIL import Image

        if self._predictors is None:
            from surya.detection import DetectionPredictor
            from surya.recognition import RecognitionPredictor

            self._predictors = (RecognitionPredictor(), DetectionPredictor())
        recognition, detection = self._predictors
        page = Image.open(io.BytesIO(image)).convert("RGB")
        result = recognition([page], [_LANG_SURYA[lang]], detection)[0]
        lines = result.text_lines
        text = "\n".join(line.text for line in lines)
        conf = sum(line.confidence for line in lines) / len(lines) if lines else 0.0
        return text, float(conf), [[float(v) for v in line.bbox] for line in lines]

    def _tesseract(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        import pytesseract
        from PIL import Image

        page = Image.open(io.BytesIO(image))
        data = pytesseract.image_to_data(page, lang=lang, output_type=pytesseract.Output.DICT)
        words, confs, boxes, current, line_key = [], [], [], [], None
        for i, word in enumerate(data["text"]):
            if not word.strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if line_key is not None and key != line_key:
                words.append(" ".join(current))
                current = []
            line_key = key
            current.append(word)
            confs.append(max(0.0, float(data["conf"][i])) / 100.0)
            x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
            boxes.append([float(x), float(y), float(x + w), float(y + h)])
        if current:
            words.append(" ".join(current))
        return "\n".join(words), (sum(confs) / len(confs) if confs else 0.0), boxes
