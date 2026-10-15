"""IndicTrans2 Hindi to English (plan §4.5). Imported lazily."""

from __future__ import annotations

import importlib.util

from vakeel_sahayak.models.base import ModelUnavailable, TranslationClient

_CODES = {"hi": "hin_Deva", "en": "eng_Latn"}


class IndicTrans2Client(TranslationClient):
    """IndicTrans2 Hindi to English (plan §4.5)."""

    is_identity = False

    def __init__(self, model_id: str | None = None) -> None:
        """Choose the checkpoint (default from configs/models.yaml `translation.model`); weights load on first use."""
        self.name = "indictrans2"
        self.model_id = model_id
        self._loaded: tuple | None = None

    @staticmethod
    def available() -> bool:
        """True when transformers, torch and IndicTransToolkit are installed."""
        return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch", "IndicTransToolkit"))

    def _load(self) -> tuple:
        if self._loaded is None:
            if not self.available():
                raise ModelUnavailable("IndicTrans2 (transformers, torch, IndicTransToolkit) is not installed", "translation")
            from IndicTransToolkit.processor import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            model_id = self.model_id
            if not model_id:
                from vakeel_sahayak.config import load_config

                model_id = str((load_config().models.get("translation") or {}).get("model", "ai4bharat/indictrans2-indic-en-1B"))
            tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_id, trust_remote_code=True)
            self._loaded = (IndicProcessor(inference=True), tokenizer, model)
        return self._loaded

    def translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        """Translate Hindi to English, line by line so the layout survives.

        Args:
            text: Hindi (or mixed) text
            src: 'hi'
            tgt: 'en'

        Returns:
            Translation.

        Raises:
            ValueError: for a direction other than hi to en.
            ModelUnavailable: the translation libraries are missing.
        """
        if (src, tgt) != ("hi", "en"):
            raise ValueError("IndicTrans2 is used for hi to en only")
        processor, tokenizer, model = self._load()
        lines = text.split("\n")
        todo = [(i, ln) for i, ln in enumerate(lines) if ln.strip()]
        batch = processor.preprocess_batch([ln for _, ln in todo], src_lang=_CODES[src], tgt_lang=_CODES[tgt])
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_length=256, num_beams=4)
        decoded = tokenizer.batch_decode(out, skip_special_tokens=True)
        for (i, _), line in zip(todo, processor.postprocess_batch(decoded, lang=_CODES[tgt]), strict=True):
            lines[i] = line
        return "\n".join(lines)
