"""Factory resolving model roles to clients using configs/models.yaml (plan §12)."""

from __future__ import annotations

from vakeel_sahayak.models.base import (
    AsrClient,
    EmbeddingClient,
    LLMClient,
    NliClient,
    OcrClient,
    TranslationClient,
    VisionClient,
)


def get_llm(role: str) -> LLMClient:
    """Return the configured client for a role.

    Args:
        role: role key from configs/models.yaml, e.g. 'agents_14b', 'munshi_4b', 'extractor_4b'

    Returns:
        LLMClient.
    """
    raise NotImplementedError


def get_vision() -> VisionClient:
    """Configured vision client.

    Returns:
        VisionClient.
    """
    raise NotImplementedError


def get_ocr() -> OcrClient:
    """Configured OCR client.

    Returns:
        OcrClient.
    """
    raise NotImplementedError


def get_asr() -> AsrClient:
    """Configured ASR client.

    Returns:
        AsrClient.
    """
    raise NotImplementedError


def get_translator() -> TranslationClient:
    """Configured translator.

    Returns:
        TranslationClient.
    """
    raise NotImplementedError


def get_nli() -> NliClient:
    """Configured NLI checker.

    Returns:
        NliClient.
    """
    raise NotImplementedError


def get_embedder() -> EmbeddingClient:
    """Configured embedder: BGE-M3 when installed, else the deterministic offline fallback (override with VS_EMBEDDER).

    Returns:
        EmbeddingClient.
    """
    from vakeel_sahayak.models.embeddings import get_embedder as _get

    return _get()  # type: ignore[return-value]
