"""vLLM client for Qwen3-14B-AWQ / Qwen3-32B-AWQ on Ada, run inside the experiment script with no long-lived server (plan §12, §17); reached through an SSH tunnel in the demo (plan §13.1).

Two transports, chosen at construction:

- **HTTP** (OpenAI-compatible `/chat/completions`): when a base URL is given or `VS_VLLM_BASE_URL` is set (the demo's
  SSH tunnel). Structured outputs use `response_format: json_schema`; servers that predate it get `guided_json`.
- **In process** (`vllm.LLM`): inside an Ada shard script (plan §17). Structured outputs use guided decoding
  (`GuidedDecodingParams`, or `StructuredOutputsParams` on newer vLLM). Prefix caching is on (plan §11).

Qwen3's thinking mode is switched off (`enable_thinking: False`); a stray `<think>` block is stripped anyway. vLLM is
imported lazily, so the package imports without it; nothing connects or loads until the first call.
"""

from __future__ import annotations

import importlib.util
import os
import threading
from typing import Any

from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, approx_tokens, strip_thinking
from vakeel_sahayak.models.prompting import to_messages

DEFAULT_MODEL = "Qwen/Qwen3-14B-AWQ"
_ENGINES: dict[tuple, Any] = {}
_ENGINE_LOCK = threading.Lock()


def _normalise_base_url(url: str) -> str:
    url = url.rstrip("/")
    return url if url.endswith("/v1") else url + "/v1"


class VllmClient(LLMClient):
    """vLLM client for Qwen3-14B-AWQ / Qwen3-32B-AWQ on Ada, run inside the experiment script with no long-lived server (plan §12, §17); reached through an SSH tunnel in the demo (plan §13.1)."""

    name = "vllm"
    where = "ada"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        *,
        role: str | None = None,
        api_key: str | None = None,
        timeout: float = 900.0,
        enable_thinking: bool = False,
        engine_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Configure the client; nothing connects or loads yet.

        Args:
            model: served model name / checkpoint (default Qwen/Qwen3-14B-AWQ, or `VS_VLLM_MODEL`)
            base_url: OpenAI-compatible endpoint, e.g. 'http://localhost:8001/v1' (default `VS_VLLM_BASE_URL`); None
                with no variable set means in-process vLLM
            role: the configs/models.yaml role this client serves (for logs)
            api_key: bearer token for the endpoint, if any (`VS_VLLM_API_KEY`)
            timeout: seconds per HTTP request
            enable_thinking: Qwen3 thinking mode (off for every agent call)
            engine_kwargs: extra `vllm.LLM(...)` arguments (tensor_parallel_size, max_model_len, gpu_memory_utilization)
        """
        self.model_id = model or os.environ.get("VS_VLLM_MODEL") or DEFAULT_MODEL
        env_url = os.environ.get("VS_VLLM_BASE_URL")
        self.base_url = _normalise_base_url(base_url or env_url) if (base_url or env_url) else None
        self.role = role
        self.api_key = api_key or os.environ.get("VS_VLLM_API_KEY")
        self.timeout = timeout
        self.enable_thinking = enable_thinking
        self.engine_kwargs = dict(engine_kwargs or {})
        self._tokenizer = None
        self._legacy_guided = False  # set when the server rejected response_format

    @property
    def mode(self) -> str:
        """'http' or 'inprocess'."""
        return "http" if self.base_url else "inprocess"

    @staticmethod
    def available(base_url: str | None = None) -> bool:
        """True when an endpoint is configured or vLLM is importable (checked without importing it)."""
        return bool(base_url or os.environ.get("VS_VLLM_BASE_URL")) or importlib.util.find_spec("vllm") is not None

    # ----------------------------------------------------------------------------- generation

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Generate from one user prompt.

        Args:
            prompt: the full prompt (the shared layout of `models.prompting`)
            max_tokens: completion limit
            temperature: 0.0 for deterministic runs
            json_schema: constrain decoding to this schema (vLLM structured outputs)

        Returns:
            Completion text.

        Raises:
            ModelUnavailable: no endpoint and no vLLM, or the endpoint cannot be reached.
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
        if self.mode == "http":
            return self._http(messages, max_tokens, temperature, json_schema)
        return self._inprocess(messages, max_tokens, temperature, json_schema)

    def _http(self, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None) -> str:
        import httpx

        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        if json_schema is not None:
            if self._legacy_guided:
                body["guided_json"] = json_schema
            else:
                body["response_format"] = {"type": "json_schema", "json_schema": {"name": "output", "schema": json_schema}}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.base_url}/chat/completions"
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
            if resp.status_code == 400 and json_schema is not None and not self._legacy_guided:
                self._legacy_guided = True  # older vLLM: guided decoding via the extra body field
                body.pop("response_format", None)
                body["guided_json"] = json_schema
                resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelUnavailable(f"the vLLM endpoint {self.base_url} failed: {exc}", "models") from exc
        data = resp.json()
        text = strip_thinking(str(data["choices"][0]["message"].get("content") or ""))
        usage = data.get("usage") or {}
        if usage:
            self.record_usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))
        return text

    def _engine(self) -> Any:
        if importlib.util.find_spec("vllm") is None:
            raise ModelUnavailable("vLLM is not installed and no VS_VLLM_BASE_URL endpoint is set", "models")
        kwargs = {"enable_prefix_caching": True, **self.engine_kwargs}
        if "AWQ" in self.model_id.upper() and "quantization" not in kwargs:
            kwargs["quantization"] = "awq"
        if "tensor_parallel_size" not in kwargs and os.environ.get("VS_VLLM_TP"):
            kwargs["tensor_parallel_size"] = int(os.environ["VS_VLLM_TP"])
        key = (self.model_id, tuple(sorted((k, str(v)) for k, v in kwargs.items())))
        with _ENGINE_LOCK:
            if key not in _ENGINES:
                from vllm import LLM

                _ENGINES[key] = LLM(model=self.model_id, **kwargs)
            return _ENGINES[key]

    @staticmethod
    def _sampling(max_tokens: int, temperature: float, json_schema: dict | None) -> Any:
        from vllm import SamplingParams

        if json_schema is None:
            return SamplingParams(max_tokens=max_tokens, temperature=temperature)
        try:  # vLLM >= 0.10
            from vllm.sampling_params import StructuredOutputsParams

            return SamplingParams(max_tokens=max_tokens, temperature=temperature, structured_outputs=StructuredOutputsParams(json=json_schema))
        except (ImportError, TypeError):
            from vllm.sampling_params import GuidedDecodingParams

            return SamplingParams(max_tokens=max_tokens, temperature=temperature, guided_decoding=GuidedDecodingParams(json=json_schema))

    def _inprocess(self, messages: list[dict[str, str]], max_tokens: int, temperature: float, json_schema: dict | None) -> str:
        llm = self._engine()
        params = self._sampling(max_tokens, temperature, json_schema)
        try:
            outputs = llm.chat(messages, params, use_tqdm=False, chat_template_kwargs={"enable_thinking": self.enable_thinking})
        except TypeError:  # older vLLM without chat_template_kwargs
            outputs = llm.chat(messages, params, use_tqdm=False)
        out = outputs[0]
        text = strip_thinking(out.outputs[0].text)
        self.record_usage(len(out.prompt_token_ids or []), len(out.outputs[0].token_ids or []))
        return text

    # ----------------------------------------------------------------------------- tokens

    def count_tokens(self, text: str) -> int:
        """Exact count with the engine's tokenizer in process, or the model's tokenizer when transformers is installed; else an estimate."""
        if self.mode == "inprocess" and _ENGINES:
            try:
                return len(self._engine().get_tokenizer().encode(text))
            except Exception:  # noqa: BLE001 - counting must never break a run
                pass
        if self._tokenizer is None and importlib.util.find_spec("transformers") is not None:
            try:
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            except Exception:  # noqa: BLE001 - offline machine: fall back to the estimate
                self._tokenizer = False
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        return approx_tokens(text)
