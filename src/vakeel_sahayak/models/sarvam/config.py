"""Sarvam settings from configs/models.yaml `sarvam:` (model names and endpoints live there, not in code).

`DEFAULTS` mirrors the yaml so the package works without it; the yaml wins key by key. The mode is resolved in
`policy.sarvam_mode`. The API key is read from the environment variable SARVAM_API_KEY only (`api_key()`), never from a
file, and is never put in a log, an event or an error message.
"""

from __future__ import annotations

import copy
import os
from typing import Any

KEY_ENV = "SARVAM_API_KEY"
DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mode": "public",
    "base_url": "https://api.sarvam.ai",
    "auth_header": "api-subscription-key",
    "timeout_s": 120.0,
    "retries": {"max": 5, "base_delay_s": 1.0, "max_delay_s": 60.0},
    "endpoints": {
        "chat": "/v1/chat/completions",
        "translate": "/translate",
        "transliterate": "/transliterate",
        "language_id": "/text-lid",
        "speech_to_text": "/speech-to-text",
        "text_to_speech": "/text-to-speech",
        "vision_digitise": "/doc-ai/v1/job/digitise",
        "vision_status": "/doc-ai/v1/job/{job_id}/status",
        "vision_download": "/doc-ai/v1/job/{job_id}/download-url",
    },
    "chat": {"model": "sarvam-105b", "reasoning_effort": None, "strict_json": False, "max_tokens_cap": 4096},
    "translate": {
        "model": "sarvam-translate:v1",
        "mode": "formal",
        "max_chars": {"mayura:v1": 1000, "sarvam-translate:v1": 2000},
        "numerals_format": "international",
    },
    "speech_to_text": {"model": "saaras:v4", "mode": "codemix", "max_seconds": 30},
    "text_to_speech": {"model": "bulbul:v4-flash", "speaker": "simran_en_customer", "sample_rate": 24000},
    "vision": {"output_format": "md", "poll_interval_s": 2.0, "timeout_s": 300.0, "use_for_ocr": False},
    # Spend ledger (models/sarvam/spend.py). Prices: Sarvam dashboard 2026-10-26 (owner-reported). Chat: INR per 1M tokens. Characters: INR per 10,000 characters.
    "ledger": {"path": None, "cache_path": None, "default_cap_inr": 25.0},
    "prices_inr_per_1m": {
        "sarvam-105b": {"input": 15, "cached": 5, "output": 60},
        "mimo-v2.6-flash": {"input": 12.5, "cached": 0.25, "output": 25},
        "mimo-v2.6-pro": {"input": 40, "cached": 0.3, "output": 80},
        "deepseek-v4.1-flash": {"input": 25, "cached": 0.5, "output": 105},
        "glm-5.3-flash": {"input": 13.5, "cached": 2.5, "output": 45},
        "gemma-4": {"input": 35, "cached": 10, "output": 90},
    },
    "prices_inr_per_10k_chars": {"translate": 20, "transliterate": 20, "language_id": 3.5, "text_to_speech": 30},
    "use": {"ocr": True, "vision": True, "translation": True, "asr": True, "llm": True, "tts": True, "language_id": True},
}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def sarvam_config() -> dict[str, Any]:
    """The `sarvam:` section of configs/models.yaml merged over the built-in defaults."""
    try:
        from vakeel_sahayak.config import load_config

        raw = load_config().models.get("sarvam") or {}
    except (FileNotFoundError, ValueError):
        raw = {}
    return _merge(DEFAULTS, raw if isinstance(raw, dict) else {})


def api_key() -> str | None:
    """The API key from the environment (None when unset or blank). Never log or store the return value."""
    return (os.environ.get(KEY_ENV) or "").strip() or None


def key_is_set() -> bool:
    """True when SARVAM_API_KEY is set (does not reveal it)."""
    return api_key() is not None
