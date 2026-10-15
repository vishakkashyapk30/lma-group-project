"""Qwen3-4B (base or +QLoRA adapter, int4) on the laptop for Munshi and Peshkar (plan §12).

One copy of the base weights serves both roles: `munshi_4b` runs with the adapter off and `extractor_4b` (Peshkar's
fine-tuned extractor) with it on. The adapter is loaded with peft on top of the shared base, and each call switches it
on or off under a lock (`set_adapter`, or the `adapter(enabled)` context manager). transformers, torch, bitsandbytes and
peft are imported lazily; nothing loads until the first call.

Plain transformers has no grammar-constrained decoding, so a JSON schema is shown in the prompt and the reply is
validated and repaired by `orchestration.structured_output` (the vLLM client constrains decoding itself).
"""

from __future__ import annotations

import importlib.util
import json
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, approx_tokens, strip_thinking
from vakeel_sahayak.models.prompting import to_messages

DEFAULT_MODEL = "Qwen/Qwen3-4B"
_LOADED: dict[tuple[str, str, str | None], dict[str, Any]] = {}
_LOAD_LOCK = threading.RLock()


def resolve_adapter_path(adapter: str | None) -> str | None:
    """An adapter path from configs/models.yaml made absolute (relative paths are taken from the repository root)."""
    if not adapter:
        return None
    p = Path(adapter).expanduser()
    if p.is_absolute():
        return str(p)
    from vakeel_sahayak.config import load_config

    return str((Path(load_config().config_dir).resolve().parent / p).resolve())


class LocalLLMClient(LLMClient):
    """Qwen3-4B (base or +QLoRA adapter, int4) on the laptop for Munshi and Peshkar (plan §12)."""

    name = "local-transformers"
    where = "laptop"

    def __init__(
        self,
        model: str | None = None,
        adapter: str | None = None,
        use_adapter: bool | None = None,
        *,
        role: str | None = None,
        quant: str | None = "int4",
        device: str | None = None,
        enable_thinking: bool = False,
    ) -> None:
        """Configure the client; weights load on the first call.

        Args:
            model: Hugging Face id of the base model (default Qwen/Qwen3-4B)
            adapter: QLoRA adapter folder (configs/models.yaml `extractor_4b.adapter`)
            use_adapter: generate with the adapter on (default: on when an adapter is given)
            role: the configs/models.yaml role this client serves
            quant: 'int4' (bitsandbytes NF4), 'int8' or None for fp16
            device: 'cuda:0', 'cpu' or None (`VS_LOCAL_LLM_DEVICE`, else automatic)
            enable_thinking: Qwen3 thinking mode (off)
        """
        self.model_id = model or DEFAULT_MODEL
        self.adapter_path = resolve_adapter_path(adapter)
        self.use_adapter = bool(self.adapter_path) if use_adapter is None else bool(use_adapter)
        self.role = role
        self.quant = quant
        self.device = device or os.environ.get("VS_LOCAL_LLM_DEVICE") or None
        self.enable_thinking = enable_thinking

    @staticmethod
    def available(adapter: str | None = None) -> bool:
        """True when transformers and torch (and peft, if an adapter is wanted) are installed."""
        mods = ["transformers", "torch"] + (["peft"] if adapter else [])
        return all(importlib.util.find_spec(m) is not None for m in mods)

    # ----------------------------------------------------------------------------- adapter switch

    def set_adapter(self, enabled: bool) -> None:
        """Switch the QLoRA adapter on (extractor) or off (base model) for this client's next calls."""
        if enabled and not self.adapter_path:
            raise ValueError("this client has no adapter configured")
        self.use_adapter = bool(enabled)

    @contextmanager
    def adapter(self, enabled: bool) -> Iterator[LocalLLMClient]:
        """Temporarily switch the adapter (A5 compares the tuned and the base 4B on the same weights)."""
        before = self.use_adapter
        self.set_adapter(enabled)
        try:
            yield self
        finally:
            self.use_adapter = before

    # ----------------------------------------------------------------------------- loading

    def _key(self) -> tuple[str, str, str | None]:
        return (self.model_id, str(self.quant), self.device)

    def _load(self) -> dict[str, Any]:
        """Load (once per process) the base weights, then the adapter if this client needs it."""
        if not self.available(self.adapter_path if self.use_adapter else None):
            raise ModelUnavailable("transformers and torch (and peft for the adapter) are needed for the local model", "models")
        with _LOAD_LOCK:
            entry = _LOADED.get(self._key())
            if entry is None:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                kwargs: dict[str, Any] = {"torch_dtype": torch.float16}
                if self.quant in ("int4", "int8"):
                    try:
                        from transformers import BitsAndBytesConfig

                        kwargs["quantization_config"] = (
                            BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)
                            if self.quant == "int4"
                            else BitsAndBytesConfig(load_in_8bit=True)
                        )
                    except ImportError as exc:
                        raise ModelUnavailable("bitsandbytes is needed for the int4 local model", "models") from exc
                kwargs["device_map"] = self.device or "auto"
                try:
                    tok = AutoTokenizer.from_pretrained(self.model_id)
                    model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
                except OSError as exc:
                    raise ModelUnavailable(f"the local model {self.model_id!r} could not be loaded: {exc}", "models") from exc
                model.eval()
                entry = {"tokenizer": tok, "model": model, "adapters": set(), "lock": threading.Lock()}
                _LOADED[self._key()] = entry
            if self.use_adapter and self.adapter_path and self.adapter_path not in entry["adapters"]:
                if not Path(self.adapter_path).exists():
                    raise ModelUnavailable(
                        f"the extractor adapter {self.adapter_path!r} does not exist yet; train it with finetune/train_qlora.py", "train"
                    )
                from peft import PeftModel

                name = f"adapter{len(entry['adapters'])}"
                if entry["adapters"]:
                    entry["model"].load_adapter(self.adapter_path, adapter_name=name)
                else:
                    entry["model"] = PeftModel.from_pretrained(entry["model"], self.adapter_path, adapter_name=name)
                entry.setdefault("names", {})[self.adapter_path] = name
                entry["adapters"].add(self.adapter_path)
            return entry

    # ----------------------------------------------------------------------------- generation

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Generate with the adapter on or off as configured.

        Args:
            prompt: the full prompt
            max_tokens: new-token limit
            temperature: 0.0 for greedy decoding
            json_schema: shown in the prompt (validated and repaired by the caller)

        Returns:
            Completion text.

        Raises:
            ModelUnavailable: the libraries, the weights or the adapter are missing.
        """
        return self.chat(to_messages(prompt), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        json_schema: dict | None = None,
    ) -> str:
        """Generate from chat messages (see `generate`)."""
        import torch

        entry = self._load()
        tok, model = entry["tokenizer"], entry["model"]
        if json_schema is not None and "OUTPUT SCHEMA" not in messages[-1]["content"]:
            messages = [*messages[:-1], {"role": messages[-1]["role"], "content": messages[-1]["content"]
                        + "\n\nReply with JSON only, matching this schema:\n" + json.dumps(json_schema, ensure_ascii=False)}]  # fmt: skip
        try:
            text_in = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=self.enable_thinking)
        except TypeError:
            text_in = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok(text_in, return_tensors="pt").to(model.device)
        gen_kwargs: dict[str, Any] = {"max_new_tokens": max_tokens, "do_sample": temperature > 0}
        if temperature > 0:
            gen_kwargs["temperature"] = temperature
        with entry["lock"], torch.no_grad():
            is_peft = bool(entry["adapters"])
            if is_peft and self.use_adapter and self.adapter_path:
                model.set_adapter(entry["names"][self.adapter_path])
                out = model.generate(**inputs, **gen_kwargs)
            elif is_peft:
                with model.disable_adapter():
                    out = model.generate(**inputs, **gen_kwargs)
            else:
                out = model.generate(**inputs, **gen_kwargs)
        new = out[0][inputs["input_ids"].shape[1] :]
        text = strip_thinking(tok.decode(new, skip_special_tokens=True))
        self.record_usage(int(inputs["input_ids"].shape[1]), int(new.shape[0]))
        return text

    def count_tokens(self, text: str) -> int:
        """Exact count once the tokenizer is loaded, else an estimate (counting never loads the weights)."""
        entry = _LOADED.get(self._key())
        if entry is not None:
            return len(entry["tokenizer"].encode(text))
        return approx_tokens(text)


LocalLLM = LocalLLMClient  # the plan's name for the extractor / Munshi controller client (plan §12)
