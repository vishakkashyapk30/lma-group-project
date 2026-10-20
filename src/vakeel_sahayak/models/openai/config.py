"""OpenAI settings from configs/models.yaml `openai:` (model names, endpoints and PRICES live there, not in code).

`DEFAULTS` mirrors the yaml so the package works without it; the yaml wins key by key. The API key is read from the
environment variable OPENAI_API_KEY only (`api_key()`), never from a file, and is never put in a log, an event, the ledger
or an error message.

Spending cap: `effective_cap_usd()` is `openai.cap_usd` / env `VS_OPENAI_CAP_USD` (default 4.50) clamped to `HARD_MAX_USD`
(5.00, the team's whole OpenAI budget). The clamp is in code, so no config or env value can raise the cap above it.
"""

from __future__ import annotations

import copy
import logging
import math
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

log = logging.getLogger("vakeel_sahayak.openai")

KEY_ENV = "OPENAI_API_KEY"
CAP_ENV = "VS_OPENAI_CAP_USD"
RUN_CAP_ENV = "VS_OPENAI_RUN_CAP_USD"
HARD_MAX_USD = 5.00  # the whole OpenAI budget; the cap can never be configured above this
DEFAULT_CAP_USD = 4.50  # safety margin of 0.50 USD for estimation error
DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mode": "public",
    "base_url": "https://api.openai.com",
    "timeout_s": 120.0,
    "retries": {"max": 4, "base_delay_s": 1.0, "max_delay_s": 30.0},
    "endpoints": {"chat": "/v1/chat/completions"},
    "chat": {"model": "gpt-6-luna", "reasoning_effort": "none", "strict_json": "auto", "max_tokens_cap": 4096, "reasoning_headroom_tokens": 0, "send_temperature": True},
    "prices": {
        "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
        "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20},
        "gpt-5.4-nano": {"input": 0.20, "cached_input": 0.02, "output": 1.25},
        "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
        "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    },
    "cap_usd": DEFAULT_CAP_USD,
    "run_cap_usd": None,
    "ledger": {"path": None, "cache_path": None},
    "use": {"llm": True},
}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def openai_config() -> dict[str, Any]:
    """The `openai:` section of configs/models.yaml merged over the built-in defaults."""
    try:
        from vakeel_sahayak.config import load_config

        raw = load_config().models.get("openai") or {}
    except (FileNotFoundError, ValueError):
        raw = {}
    return _merge(DEFAULTS, raw if isinstance(raw, dict) else {})


def api_key() -> str | None:
    """The API key from the environment (None when unset or blank). Never log or store the return value."""
    return (os.environ.get(KEY_ENV) or "").strip() or None


def key_is_set() -> bool:
    """True when OPENAI_API_KEY is set (does not reveal it)."""
    return api_key() is not None


# ------------------------------------------------------------------------------------------------ cap


def _usd(raw: Any) -> float | None:
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def effective_cap_usd() -> float:
    """The spending cap in USD: env `VS_OPENAI_CAP_USD`, else yaml `openai.cap_usd`, else 4.50; never above `HARD_MAX_USD`, never below 0.

    An unparseable value falls back to the default; a value above the hard maximum is clamped (and logged).
    """
    raw = os.environ.get(CAP_ENV)
    src = CAP_ENV
    if raw is None or not raw.strip():
        raw, src = openai_config().get("cap_usd"), "openai.cap_usd"
    val = _usd(raw)
    if val is None:
        log.warning("%s is not a number; using the default cap of %.2f USD", src, DEFAULT_CAP_USD)
        return DEFAULT_CAP_USD
    if val > HARD_MAX_USD:
        log.warning("%s=%s is above the hard maximum; the cap is clamped to %.2f USD", src, val, HARD_MAX_USD)
        return HARD_MAX_USD
    return max(0.0, val)


def effective_run_cap_usd() -> float | None:
    """The optional per-run soft cap (`VS_OPENAI_RUN_CAP_USD`, else yaml `openai.run_cap_usd`), never above the total cap; None when unset."""
    raw = os.environ.get(RUN_CAP_ENV)
    if raw is None or not raw.strip():
        raw = openai_config().get("run_cap_usd")
    if raw is None or str(raw).strip() == "":
        return None
    val = _usd(raw)
    if val is None:
        log.warning("the run cap is not a number; ignoring it")
        return None
    return max(0.0, min(val, effective_cap_usd()))


def usd_to_micro(usd: float) -> int:
    """USD to whole micro-USD (rounded down, so a cap never grows by rounding)."""
    return int(Decimal(str(usd)) * 1_000_000)


# ------------------------------------------------------------------------------------------------ prices


@dataclass(frozen=True)
class Price:
    """USD per million tokens (OpenAI's price pages are in this unit; 1 USD/M = 1 micro-USD per token)."""

    input: Decimal
    cached_input: Decimal
    output: Decimal


def price_of(model: str, cfg: dict[str, Any] | None = None) -> Price | None:
    """The price-table entry of a model (exact name, or a dated snapshot 'name-YYYY-MM-DD' of a listed model); None when unlisted."""
    table = (cfg or openai_config()).get("prices") or {}
    entry = table.get(model)
    if entry is None:
        base = "-".join(model.split("-")[:-3]) if len(model.split("-")) > 3 else ""
        entry = table.get(base) if base else None
    if entry is None:
        return None
    inp = Decimal(str(entry["input"]))
    return Price(inp, Decimal(str(entry.get("cached_input", entry["input"]))), Decimal(str(entry["output"])))


def data_dir() -> Path:
    """The data directory (`VS_DATA_DIR`, else configs/paths.yaml)."""
    try:
        from vakeel_sahayak.config import load_config

        return Path(load_config().paths.data_dir)
    except (FileNotFoundError, ValueError):
        return Path(os.environ.get("VS_DATA_DIR") or "data")


def ledger_path() -> Path:
    """SQLite spend ledger (default `<data>/openai/ledger.sqlite`; yaml `openai.ledger.path`)."""
    p = openai_config()["ledger"].get("path")
    return Path(p) if p else data_dir() / "openai" / "ledger.sqlite"


def cache_path() -> Path:
    """SQLite response cache (default `<data>/openai/cache.sqlite`; yaml `openai.ledger.cache_path`)."""
    p = openai_config()["ledger"].get("cache_path")
    return Path(p) if p else data_dir() / "openai" / "cache.sqlite"
