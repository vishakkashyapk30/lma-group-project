"""Qwen3-VL 4-bit (4B laptop; 8B Ada) or Qwen2.5-VL-7B (plan §12). Imported lazily; never summarises."""

from __future__ import annotations

import importlib.util
import io

from vakeel_sahayak.models.base import ModelUnavailable, VisionClient

TRANSCRIBE_PROMPT = (
    "Transcribe all the text on this page exactly as written, in reading order. Keep Hindi in Devanagari and English "
    "in Latin letters. Do not summarise, translate, explain or add anything. Write [illegible] for words you cannot read."
)


class LocalVisionClient(VisionClient):
    """Qwen3-VL 4-bit (4B laptop; 8B Ada) or Qwen2.5-VL-7B (plan §12)."""

    def __init__(self, model_id: str | None = None, quant_4bit: bool = True) -> None:
        """Choose the model (default from configs/models.yaml `vision.default`); weights load on first use."""
        self.name = "qwen3-vl"
        self.model_id = model_id
        self.quant_4bit = quant_4bit
        self._loaded: tuple | None = None

    @staticmethod
    def available() -> bool:
        """True when transformers and torch are installed."""
        return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch"))

    def _model_id(self) -> str:
        if self.model_id:
            return self.model_id
        from vakeel_sahayak.config import load_config

        return str(((load_config().models.get("vision") or {}).get("default") or {}).get("model", "Qwen/Qwen3-VL-4B-Instruct"))

    def _load(self) -> tuple:
        if self._loaded is None:
            if not self.available():
                raise ModelUnavailable("transformers and torch are not installed, so the vision model cannot run", "vision")
            from transformers import AutoModelForImageTextToText, AutoProcessor

            kwargs: dict = {"device_map": "auto", "torch_dtype": "auto"}
            if self.quant_4bit:
                try:
                    from transformers import BitsAndBytesConfig

                    kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
                except ImportError:
                    pass
            model_id = self._model_id()
            self._loaded = (AutoProcessor.from_pretrained(model_id), AutoModelForImageTextToText.from_pretrained(model_id, **kwargs))
        return self._loaded

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        """Transcribe only; never summarise.

        Args:
            image: page image bytes
            lang_hint: 'hi', 'en' or None, added to the prompt

        Returns:
            Transcript.

        Raises:
            ModelUnavailable: transformers or torch is missing.
        """
        from PIL import Image

        processor, model = self._load()
        hint = {"hi": " The page is mostly Hindi.", "en": " The page is mostly English."}.get(lang_hint or "", "")
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": TRANSCRIBE_PROMPT + hint}]}]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        page = Image.open(io.BytesIO(image)).convert("RGB")
        inputs = processor(text=[prompt], images=[page], return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
        return str(processor.batch_decode(out[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True)[0]).strip()
