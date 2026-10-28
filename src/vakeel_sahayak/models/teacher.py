"""Teacher for training data only: Qwen3-32B-AWQ on Ada or a Mistral API model; public orders only (plan §12, §17). Teacher and labeler must differ in family.

`TeacherClient` is an LLMClient that delegates to its backend:

- 'vllm': Qwen3-32B-AWQ through `VllmClient` (in process inside an Ada shard, or an endpoint);
- 'mistral': the Mistral chat API through `MistralApiClient` (needs `MISTRAL_API_KEY`); the teacher only ever reads
  *public* training orders, never counsel's files, so an external API is allowed here (plan §17);
- 'offline': the deterministic `OfflineLLM` (pipeline tests only; its dossiers are not training data).

`dossier_from_facts` asks for a CaseDossier with a quoted source sentence per field (plan §12 step 1); `span_check`
filtering of those quotes happens in `finetune/`.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from vakeel_sahayak.models.base import LLMClient, ModelUnavailable, approx_tokens, model_family, strip_thinking
from vakeel_sahayak.models.prompting import render_prompt, to_messages
from vakeel_sahayak.schemas.dossier import CaseDossier

DEFAULT_TEACHER = "Qwen/Qwen3-32B-AWQ"
DEFAULT_MISTRAL = "mistral-small-latest"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_OPENAI = "gpt-6-luna"  # overridden by configs/models.yaml openai.chat.model
DEFAULT_SARVAM = "sarvam-105b"  # optional non-Qwen teacher (VS_TEACHER=sarvam); public orders only


def assert_families_differ(teacher_model: str, labeler_model: str) -> None:
    """Raise ValueError when the teacher and the evaluation labeler are of the same model family (plan §17)."""
    if model_family(teacher_model) == model_family(labeler_model):
        raise ValueError(f"teacher {teacher_model!r} and labeler {labeler_model!r} are both {model_family(teacher_model)} models")


def _yaml_runtime() -> str | None:
    """`llm.teacher.runtime` when it names an external API option ('openai' or 'sarvam'); the yaml default (vllm) is not an override."""
    from vakeel_sahayak.config import load_config

    runtime = str((((load_config().models.get("llm") or {}).get("teacher")) or {}).get("runtime") or "")
    return runtime if runtime in ("openai", "sarvam") or _is_hosted(runtime) else None


def _is_hosted(name: str | None) -> bool:
    """True for a configured generic provider (models/registry.py), e.g. 'gemini'."""
    if not name or name in ("vllm", "mistral", "sarvam", "openai", "offline"):
        return False
    from vakeel_sahayak.models.registry import is_hosted

    return is_hosted(name)


def _openai_default() -> str:
    from vakeel_sahayak.models.openai.config import openai_config

    return str(openai_config()["chat"]["model"])


class MistralApiClient(LLMClient):
    """Mistral chat-completions API (JSON mode for structured calls). Public training orders only."""

    name = "mistral-api"
    where = "api"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: float = 120.0) -> None:
        """Configure; the key comes from `MISTRAL_API_KEY` when not given."""
        self.model_id = model or DEFAULT_MISTRAL
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.timeout = timeout

    @staticmethod
    def available() -> bool:
        """True when an API key is set."""
        return bool(os.environ.get("MISTRAL_API_KEY"))

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """One chat call (pinned model, temperature 0 by default)."""
        return self.chat(to_messages(prompt), max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        json_schema: dict | None = None,
    ) -> str:
        """Chat call; a schema switches on JSON mode (validation and repair are the caller's)."""
        if not self.api_key:
            raise ModelUnavailable("MISTRAL_API_KEY is not set")
        import httpx

        body: dict[str, Any] = {"model": self.model_id, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if json_schema is not None:
            body["response_format"] = {"type": "json_object"}
        try:
            resp = httpx.post(MISTRAL_URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelUnavailable(f"the Mistral API failed: {exc}") from exc
        data = resp.json()
        usage = data.get("usage") or {}
        if usage:
            self.record_usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))
        return strip_thinking(str(data["choices"][0]["message"].get("content") or ""))

    def count_tokens(self, text: str) -> int:
        """Estimate (the API reports exact usage per call)."""
        return approx_tokens(text)


class TeacherClient:
    """Teacher dossier generator. Deliberately not an `LLMClient`: no agent can be handed it (training data only, plan §12)."""

    name = "teacher"

    def __init__(self, backend: str | None = None, model: str | None = None, client: LLMClient | None = None) -> None:
        """Choose the backend.

        Args:
            backend: 'vllm', 'mistral', 'sarvam' / 'openai' (optional non-Qwen, public orders only, `openai` spend-capped) or 'offline' (default: `VS_TEACHER`, else 'mistral' when a key is set and
                'vllm' otherwise; 'offline' when `VS_MODELS=offline`)
            model: checkpoint or API model name
            client: an LLMClient to use directly (tests, a shared engine)
        """
        if backend is None:
            from vakeel_sahayak.models.factory import models_mode
            if models_mode() == "offline":
                backend = "offline"
            else:
                backend = os.environ.get("VS_TEACHER") or _yaml_runtime() or ("mistral" if MistralApiClient.available() else "vllm")
        if backend not in ("vllm", "mistral", "sarvam", "openai", "offline") and not _is_hosted(backend):
            raise ValueError(f"unknown teacher backend {backend!r}")
        hosted_model = None
        if _is_hosted(backend):
            from vakeel_sahayak.models.registry import get_provider

            spec = get_provider(backend)
            hosted_model = spec.model_for("teacher") if spec else None
        self.backend = backend
        self._client = client
        self.model_id = model or hosted_model or (
            DEFAULT_MISTRAL if backend == "mistral" else DEFAULT_SARVAM if backend == "sarvam" else _openai_default() if backend == "openai"
            else DEFAULT_TEACHER if backend == "vllm" else "offline-template"
        )  # fmt: skip
        self.where = "api" if backend in ("mistral", "sarvam", "openai") or hosted_model else "ada" if backend == "vllm" else "laptop"
        self.is_offline = backend == "offline"

    @property
    def family(self) -> str:
        """Model family of the teacher ('qwen' for vLLM Qwen3, 'mistral', 'sarvam', 'openai', 'offline')."""
        if _is_hosted(self.backend):
            from vakeel_sahayak.models.registry import get_provider

            spec = get_provider(self.backend)
            return spec.family_of(self.model_id) if spec else model_family(self.model_id)
        return "offline" if self.backend == "offline" else self.backend if self.backend in ("sarvam", "openai") else model_family(self.model_id)

    @property
    def client(self) -> LLMClient:
        """The backend client (built on first use)."""
        if self._client is None:
            if self.backend in ("sarvam", "openai"):
                from vakeel_sahayak.models.paid_lock import assert_unlocked

                assert_unlocked(self.backend)  # paid provider locked unless VS_ALLOW_PAID names it
            if _is_hosted(self.backend):
                from vakeel_sahayak.models.hosted.client import HostedLLMClient
                from vakeel_sahayak.models.paid_lock import assert_unlocked
                from vakeel_sahayak.models.sarvam.policy import DataClass

                assert_unlocked(self.backend)
                self._client = HostedLLMClient(self.backend, self.model_id, data=DataClass.PUBLIC, where="api", role="teacher")
            elif self.backend == "mistral":
                self._client = MistralApiClient(self.model_id)
            elif self.backend == "sarvam":
                from vakeel_sahayak.models.sarvam.adapters import SarvamLLMClient
                from vakeel_sahayak.models.sarvam.policy import DataClass

                self._client = SarvamLLMClient(self.model_id, data=DataClass.PUBLIC, where="api", role="teacher")
            elif self.backend == "openai":
                from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
                from vakeel_sahayak.models.sarvam.policy import DataClass

                self._client = OpenAILLMClient(self.model_id, data=DataClass.PUBLIC, where="api", role="teacher")
            elif self.backend == "vllm":
                from vakeel_sahayak.models.vllm_client import VllmClient

                self._client = VllmClient(self.model_id, role="teacher")
            else:
                from vakeel_sahayak.models.offline_llm import OfflineLLM

                self._client = OfflineLLM(role="teacher", where="ada")
        return self._client

    def generate(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None
    ) -> str:
        """Delegate to the backend (usage accumulates on `self.client.usage`)."""
        return self.client.generate(prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def count_tokens(self, text: str) -> int:
        """The backend's count."""
        return self.client.count_tokens(text)

    def dossier_from_facts(self, facts_text: str) -> CaseDossier:
        """Output a CaseDossier quoting a source sentence per field (plan §12 step 1).

        Args:
            facts_text: the facts section of a public *train* order

        Returns:
            CaseDossier (every field VERIFIED needs its quote; unknown fields stay UNSUPPORTED).
        """
        from vakeel_sahayak.orchestration.structured_output import constrained_generate

        case_id = "train-" + hashlib.sha256(facts_text.encode("utf-8")).hexdigest()[:12]
        schema = CaseDossier.model_json_schema()
        prompt = render_prompt(
            "teacher.dossier_from_facts",
            "Read the facts section of this public Indian bail order and fill the CaseDossier. For every field you fill, "
            "copy the exact source sentence into source.quote and set status VERIFIED. Leave a field UNSUPPORTED (value "
            "null) when the text does not state it. Dates are YYYY-MM-DD. Use case_id exactly as given.",
            {"case_id": case_id, "facts": facts_text},
            system="You extract structured case facts from court orders. You never guess.",
            schema=schema,
        )
        return constrained_generate(self.client, prompt, CaseDossier, max_tokens=3000)
