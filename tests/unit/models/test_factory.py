"""models/factory resolves roles in configs/models.yaml to clients (plan §12).

Behaviour tests fail until the factory is implemented. The clients must be constructible without loading model weights
or importing torch / vLLM / transformers / openai (heavy imports are lazy), which is enforced by blocking those imports.
"""

from __future__ import annotations

import inspect
import sys

import pytest

from vakeel_sahayak.models import factory
from vakeel_sahayak.models.base import (
    AsrClient,
    EmbeddingClient,
    LLMClient,
    NliClient,
    OcrClient,
    TranslationClient,
    VisionClient,
)

HEAVY = ["torch", "vllm", "transformers", "openai", "peft", "bitsandbytes"]


@pytest.fixture()
def no_heavy_imports(monkeypatch):
    """Make `import torch` (etc.) raise ImportError for the duration of a test (and select VS_MODELS=auto, the non-offline mode)."""
    monkeypatch.setenv("VS_MODELS", "auto")  # RECONCILED: the default mode is now offline; these tests check the configured backends
    for name in HEAVY:
        monkeypatch.setitem(sys.modules, name, None)


def test_factory_signatures():
    """get_llm takes a role; the other getters take no arguments."""
    assert list(inspect.signature(factory.get_llm).parameters) == ["role"]
    for name in ("get_vision", "get_ocr", "get_asr", "get_translator", "get_nli", "get_embedder"):
        assert list(inspect.signature(getattr(factory, name)).parameters) == [], name


@pytest.mark.parametrize("role", ["agents_14b", "munshi_4b", "extractor_4b", "fallback_8b"])
def test_get_llm_returns_llm_client_for_every_system_role(role, no_heavy_imports):
    """Every system LLM role in models.yaml resolves to an LLMClient without importing heavy libraries."""
    assert isinstance(factory.get_llm(role), LLMClient)


def test_get_llm_maps_runtime_to_client_class(no_heavy_imports):
    """runtime 'vllm' roles give VllmClient and runtime 'local' roles give LocalLLMClient (models.yaml)."""
    from vakeel_sahayak.models.local_llm import LocalLLMClient
    from vakeel_sahayak.models.vllm_client import VllmClient

    assert isinstance(factory.get_llm("agents_14b"), VllmClient)  # ASSUMPTION: class follows `runtime`
    assert isinstance(factory.get_llm("munshi_4b"), LocalLLMClient)
    assert isinstance(factory.get_llm("extractor_4b"), LocalLLMClient)


@pytest.mark.parametrize("role", ["", "no_such_role", "AGENTS_14B", "vision"])
def test_get_llm_unknown_role_raises(role):
    """An unknown role raises KeyError or ValueError (never returns a default model)."""
    with pytest.raises((KeyError, ValueError)):
        factory.get_llm(role)


def test_get_llm_refuses_the_evaluation_labeler_role():
    """The system must not obtain the eval-only Llama labeler through get_llm (plan §12: system_use false)."""
    # ASSUMPTION: refusal is a KeyError / ValueError / PermissionError.
    with pytest.raises((KeyError, ValueError, PermissionError)):
        factory.get_llm("eval_labeler")


@pytest.mark.parametrize(
    "getter,iface",
    [
        ("get_vision", VisionClient),
        ("get_ocr", OcrClient),
        ("get_asr", AsrClient),
        ("get_translator", TranslationClient),
        ("get_nli", NliClient),
        ("get_embedder", EmbeddingClient),
    ],
)
def test_other_getters_return_the_right_interface(getter, iface, no_heavy_imports):
    """Each getter returns a client implementing its interface, constructed lazily."""
    assert isinstance(getattr(factory, getter)(), iface)
