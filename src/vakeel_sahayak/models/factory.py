"""Factory resolving model roles to clients using configs/models.yaml (plan §12).

**Mode** (`models_mode()`): `VS_MODELS` = `offline` | `real` | `auto` (default `auto`; configs/models.yaml may set a
top-level `mode`).

- `offline`: every LLM role is the deterministic `OfflineLLM`, NLI is the lexical `OfflineNliClient`;
- `real`: the configured backends, strictly (a missing dependency raises `ModelUnavailable`, never a silent stand-in);
- `auto`: the configured backend; when its dependencies are missing the client is still returned (construction is lazy)
  and raises `ModelUnavailable` on first use. For `agents_14b`, `VS_ALLOW_LOCAL_FALLBACK=1` allows the plan's laptop
  fallback (Qwen3-8B, 4-bit) when vLLM cannot run.
- The evaluation labeler is not a system role: use `models.labeler.EvalLabeler`; the training teacher is `models.teacher.TeacherClient`.

**Roles** are the keys of `llm:` in configs/models.yaml: `agents_14b` (Sutradhar, Vakeel, Abhiyojak, Pairokar; vLLM on
Ada), `munshi_4b` (adapter off) and `extractor_4b` (adapter on) on the laptop, `fallback_8b`; `eval_labeler` is configured there but refused by `get_llm` (`teacher` resolves to a plain vLLM client for the A5 prompted-32B ablation).
`role_where(role)` says where a role's model runs; agents apply the privacy boundary to every 'ada' role, whatever
client stands in for it.

**Overrides** (tests, baselines): `set_client(kind, client)` for 'ocr', 'vision', 'asr', 'translator', 'nli', 'tts', 'langid', 'llm' (every role) or 'llm:<role>'; `reset_clients()` drops overrides and cached clients.

**Sarvam** (external API, off by default; `models.sarvam`): when `VS_SARVAM` is not `off`, SARVAM_API_KEY is set and the capability is enabled in
configs/models.yaml, `get_vision`, `get_ocr` (only with `sarvam.vision.use_for_ocr`), `get_asr`, `get_translator` and an LLM role whose
`runtime` is `sarvam` return a wrapper that tries Sarvam through the privacy policy and falls back to the local client when Sarvam is
blocked or fails. With Sarvam off the getters return exactly the local clients. `VS_MODELS=offline` forces offline everywhere.
`get_tts()` (Bulbul, test-set construction and optional read-back) and `get_langid()` (/text-lid) have no local twin: tts raises
ModelUnavailable when Sarvam is off, langid returns None.
"""

from __future__ import annotations

import os
import threading
from functools import cache

from vakeel_sahayak.models.base import (
    AsrClient,
    EmbeddingClient,
    LLMClient,
    ModelUnavailable,
    NliClient,
    OcrClient,
    TranslationClient,
    VisionClient,
)

EVAL_ONLY_ROLES = ("eval_labeler",)
MODES = ("offline", "real", "auto")
LLM_ROLES = ("agents_14b", "munshi_4b", "extractor_4b", "fallback_8b", "teacher", "eval_labeler")
_ROLE_DEFAULTS: dict[str, dict[str, object]] = {
    "agents_14b": {"model": "Qwen/Qwen3-14B-AWQ", "runtime": "vllm", "where": "ada"},
    "munshi_4b": {"model": "Qwen/Qwen3-4B", "runtime": "local", "where": "laptop", "quant": "int4", "adapter": None},
    "extractor_4b": {"model": "Qwen/Qwen3-4B", "runtime": "local", "where": "laptop", "quant": "int4", "adapter": "models/extractor-qlora"},
    "fallback_8b": {"model": "Qwen/Qwen3-8B", "runtime": "local", "where": "laptop", "quant": "int4"},
    "teacher": {"model": "Qwen/Qwen3-32B-AWQ", "runtime": "vllm", "where": "ada"},
    "eval_labeler": {"model": "meta-llama/Llama-3.1-8B-Instruct", "runtime": "local", "where": "laptop", "quant": "int4"},
}
_OVERRIDES: dict[str, object] = {}
_LLM_CACHE: dict[tuple[str, str], LLMClient] = {}
_LOCK = threading.RLock()


def models_mode() -> str:
    """'offline', 'real' or 'auto' (`VS_MODELS`, else configs/models.yaml `mode`, else 'auto')."""
    raw = os.environ.get("VS_MODELS")
    if not raw:
        try:
            from vakeel_sahayak.config import load_config

            raw = str(load_config().models.get("mode") or "auto")
        except (FileNotFoundError, ValueError):
            raw = "auto"
    mode = raw.strip().lower()
    if mode not in MODES:
        raise ValueError(f"VS_MODELS must be one of {MODES}, got {raw!r}")
    return mode


def role_config(role: str) -> dict[str, object]:
    """The configs/models.yaml entry of an LLM role (built-in defaults fill missing keys).

    Raises:
        ValueError: for an unknown role.
    """
    try:
        from vakeel_sahayak.config import load_config

        llm = (load_config().models.get("llm") or {})
    except (FileNotFoundError, ValueError):
        llm = {}
    if role not in llm and role not in _ROLE_DEFAULTS:
        raise ValueError(f"unknown model role {role!r}: use one of {sorted(set(llm) | set(_ROLE_DEFAULTS))}")
    return {**_ROLE_DEFAULTS.get(role, {}), **(llm.get(role) or {})}


def role_where(role: str) -> str:
    """Where a role's model runs: 'ada' or 'laptop' (payloads for 'ada' must be pseudonymised, plan §16)."""
    return str(role_config(role).get("where") or "laptop")


def _build_real(role: str, cfg: dict[str, object]) -> LLMClient:
    """The configured client for a role (may raise ModelUnavailable when used)."""
    runtime = str(cfg.get("runtime") or "local")
    model = str(cfg.get("model") or "")
    if runtime == "vllm":
        from vakeel_sahayak.models.vllm_client import VllmClient

        served = os.environ.get("VS_VLLM_MODEL") if role == "agents_14b" else None
        client: LLMClient = VllmClient(served or model or None, role=role)
    else:
        from vakeel_sahayak.models.local_llm import LocalLLMClient

        adapter = cfg.get("adapter")
        client = LocalLLMClient(model or None, adapter=str(adapter) if adapter else None, role=role, quant=str(cfg.get("quant") or "int4"))
    client.where = str(cfg.get("where") or client.where)
    return client


def _real_available(role: str, cfg: dict[str, object]) -> bool:
    runtime = str(cfg.get("runtime") or "local")
    if runtime == "vllm":
        from vakeel_sahayak.models.vllm_client import VllmClient

        return VllmClient.available()
    from vakeel_sahayak.models.local_llm import LocalLLMClient

    return LocalLLMClient.available(str(cfg["adapter"]) if cfg.get("adapter") else None)


def _sarvam_active(capability: str) -> bool:
    """True when a Sarvam client should be tried: not forced offline, mode not off, key set, capability switched on in the yaml."""
    from vakeel_sahayak.models.sarvam.config import key_is_set, sarvam_config
    from vakeel_sahayak.models.sarvam.policy import SarvamMode, sarvam_mode

    if os.environ.get("VS_MODELS", "").strip().lower() == "offline" or models_mode() == "offline":
        return False
    return sarvam_mode() is not SarvamMode.OFF and key_is_set() and bool(sarvam_config()["use"].get(capability, True))


def _sarvam_state() -> str:
    from vakeel_sahayak.models.sarvam.config import key_is_set
    from vakeel_sahayak.models.sarvam.policy import sarvam_mode

    return f"{sarvam_mode().value}:{key_is_set()}"


def _offline(role: str, cfg: dict[str, object]) -> LLMClient:
    from vakeel_sahayak.models.offline_llm import OfflineLLM

    return OfflineLLM(role=role, where=str(cfg.get("where") or "laptop"))


def get_llm(role: str) -> LLMClient:
    """Return the configured client for a role.

    Args:
        role: role key from configs/models.yaml, e.g. 'agents_14b', 'munshi_4b', 'extractor_4b'

    Returns:
        LLMClient. `client.is_offline` is True for the deterministic stand-in; `client.where` is the role's location.

    Raises:
        ValueError: unknown role or VS_MODELS value.
        ModelUnavailable: VS_MODELS=real and the backend's dependencies are missing.
    """
    if role in EVAL_ONLY_ROLES:
        raise ValueError(f"{role!r} is not a system role (plan §12: evaluation only); use models.labeler.EvalLabeler")
    override = _OVERRIDES.get(f"llm:{role}") or _OVERRIDES.get("llm")
    if override is not None:
        return override  # type: ignore[return-value]
    cfg = role_config(role)
    mode = models_mode()
    with _LOCK:
        key = (role, f"{mode}|{_sarvam_state()}")
        if key in _LLM_CACHE:
            return _LLM_CACHE[key]
        if cfg.get("runtime") == "sarvam":
            client = _resolve_sarvam_role(role, cfg, mode)
        else:
            client = _resolve(role, cfg, mode)
        _LLM_CACHE[key] = client
        return client


def _resolve(role: str, cfg: dict[str, object], mode: str) -> LLMClient:
    """The local/vLLM/offline client of a role."""
    if mode == "offline":
        return _offline(role, cfg)
    if _real_available(role, cfg):
        return _build_real(role, cfg)
    if mode == "real":
        raise ModelUnavailable(f"VS_MODELS=real but the backend for {role!r} ({cfg.get('runtime')}) cannot run here", "models")
    if role == "agents_14b" and os.environ.get("VS_ALLOW_LOCAL_FALLBACK") == "1" and _real_available("fallback_8b", role_config("fallback_8b")):
        client = _build_real("fallback_8b", role_config("fallback_8b"))
        client.where = str(cfg.get("where") or "ada")  # same privacy rules as the role it stands in for
        return client
    return _build_real(role, cfg)  # lazy: raises ModelUnavailable on first use, never a silent stand-in


def _resolve_sarvam_role(role: str, cfg: dict[str, object], mode: str) -> LLMClient:
    """A role configured `runtime: sarvam`: Sarvam-105B through the privacy policy, else the role's `fallback:` (default: the built-in runtime)."""
    where = str(cfg.get("where") or _ROLE_DEFAULTS.get(role, {}).get("where") or "ada")
    fallback = {**_ROLE_DEFAULTS.get(role, {}), **dict(cfg.get("fallback") or {}), "where": where}  # type: ignore[call-overload]
    if not _sarvam_active("llm"):
        return _resolve(role, fallback, mode)
    from vakeel_sahayak.models.sarvam.adapters import SarvamLLMClient
    from vakeel_sahayak.models.sarvam.fallback import FallbackLLM
    from vakeel_sahayak.models.sarvam.policy import DataClass

    public = role == "teacher"  # the teacher only reads public orders; agent roles carry pseudonymised client text
    primary = SarvamLLMClient(
        str(cfg.get("model") or "") or None, data=DataClass.PUBLIC if public else DataClass.CLIENT_TEXT,
        where="api" if public else where, role=role,
    )  # fmt: skip
    return FallbackLLM(primary, lambda: _resolve(role, fallback, mode), "api" if public else where)


def set_client(kind: str, client: object | None) -> None:
    """Use a given client for 'ocr', 'vision', 'asr', 'translator', 'nli', 'llm' or 'llm:<role>' (tests, baselines); None removes the override."""
    if client is None:
        _OVERRIDES.pop(kind, None)
    else:
        _OVERRIDES[kind] = client


def reset_clients() -> None:
    """Drop every override and cached heavy client."""
    _OVERRIDES.clear()
    _heavy.cache_clear()
    with _LOCK:
        _LLM_CACHE.clear()
    _nli_cached.cache_clear()


@cache
def _heavy(kind: str) -> object | None:
    """The first installed heavy backend for a kind, built once (None when none is installed)."""
    if kind == "ocr":
        from vakeel_sahayak.models.ocr import SuryaOcrClient

        return SuryaOcrClient() if SuryaOcrClient.available() else None
    if kind == "vision":
        from vakeel_sahayak.models.vlm import LocalVisionClient

        return LocalVisionClient() if LocalVisionClient.available() else None
    if kind == "translator":
        from vakeel_sahayak.models.translation import IndicTrans2Client

        return IndicTrans2Client() if IndicTrans2Client.available() else None
    from vakeel_sahayak.models.asr import IndicConformerAsrClient, WhisperAsrClient

    for cls in (WhisperAsrClient, IndicConformerAsrClient):  # Whisper first until the dev comparison picks one
        if cls.available():
            return cls()
    return None


def _pick(kind: str, offline: type) -> object:
    """Override, else the installed heavy backend, else the offline fallback (VS_MODELS=offline forces the fallback)."""
    if kind in _OVERRIDES:
        return _OVERRIDES[kind]
    if os.environ.get("VS_MODELS", "auto") != "offline":
        heavy = _heavy(kind)
        if heavy is not None:
            return heavy
    return offline()


def get_vision() -> VisionClient:
    """Configured vision client: Sarvam Vision first when active (policy-gated, local on a block), else Qwen3-VL when installed, else the offline fallback (stand-in images only).

    Returns:
        VisionClient.
    """
    from vakeel_sahayak.models.offline import OfflineVisionClient

    if "vision" in _OVERRIDES:
        return _OVERRIDES["vision"]  # type: ignore[return-value]
    if _sarvam_active("vision"):
        from vakeel_sahayak.models.sarvam.adapters import SarvamVisionClient
        from vakeel_sahayak.models.sarvam.fallback import FallbackVision

        return FallbackVision(SarvamVisionClient(), lambda: _pick("vision", OfflineVisionClient))  # type: ignore[return-value]
    return _pick("vision", OfflineVisionClient)  # type: ignore[return-value]


def get_ocr() -> OcrClient:
    """Configured OCR client: Surya or Tesseract when installed, else the offline fallback (stand-in images only).

    With `sarvam.vision.use_for_ocr` and Sarvam active, Sarvam Vision answers first (policy-gated, local on a block).

    Returns:
        OcrClient.
    """
    from vakeel_sahayak.models.offline import OfflineOcrClient

    if "ocr" in _OVERRIDES:
        return _OVERRIDES["ocr"]  # type: ignore[return-value]
    if _sarvam_active("ocr"):
        from vakeel_sahayak.models.sarvam.config import sarvam_config

        if sarvam_config()["vision"].get("use_for_ocr"):
            from vakeel_sahayak.models.sarvam.adapters import SarvamVisionClient
            from vakeel_sahayak.models.sarvam.fallback import FallbackOcr

            return FallbackOcr(SarvamVisionClient(), lambda: _pick("ocr", OfflineOcrClient))  # type: ignore[return-value]
    return _pick("ocr", OfflineOcrClient)  # type: ignore[return-value]


def get_asr() -> AsrClient:
    """Configured ASR client: Saaras first when Sarvam is active (consent-gated, local on a block), else Whisper or IndicConformer, else the transcript-sidecar fallback.

    Returns:
        AsrClient.
    """
    from vakeel_sahayak.models.offline import OfflineAsrClient

    if "asr" in _OVERRIDES:
        return _OVERRIDES["asr"]  # type: ignore[return-value]
    if _sarvam_active("asr"):
        from vakeel_sahayak.models.sarvam.adapters import SarvamAsr
        from vakeel_sahayak.models.sarvam.fallback import FallbackAsr

        return FallbackAsr(SarvamAsr(), lambda: _pick("asr", OfflineAsrClient))  # type: ignore[return-value]
    return _pick("asr", OfflineAsrClient)  # type: ignore[return-value]


def get_translator() -> TranslationClient:
    """Configured translator: Sarvam-Translate first when active (policy-gated, local on a block), else IndicTrans2 when installed, else the offline word-level glossary (marked, not IndicTrans2).

    Returns:
        TranslationClient. Clients carry `name` and `is_identity`.
    """
    from vakeel_sahayak.models.offline import GlossaryTranslator

    if "translator" in _OVERRIDES:
        return _OVERRIDES["translator"]  # type: ignore[return-value]
    if _sarvam_active("translation"):
        from vakeel_sahayak.models.sarvam.adapters import SarvamTranslator
        from vakeel_sahayak.models.sarvam.fallback import FallbackTranslator

        return FallbackTranslator(SarvamTranslator(), lambda: _pick("translator", GlossaryTranslator))  # type: ignore[return-value]
    return _pick("translator", GlossaryTranslator)  # type: ignore[return-value]


def get_tts() -> object:
    """Sarvam Bulbul text-to-speech (`SarvamTts.synthesize`), for T8 synthetic dictation and the optional read-back audio.

    There is no local twin (indic-parler-tts is a test-construction model run offline), so this raises when Sarvam cannot be used.
    Calls are still gated per call: use `with public_scope():` for constructed text.

    Raises:
        ModelUnavailable: Sarvam is off, forced offline, switched off for tts, or has no key.
    """
    if "tts" in _OVERRIDES:
        return _OVERRIDES["tts"]
    if not _sarvam_active("tts"):
        raise ModelUnavailable("Sarvam text-to-speech is not active (VS_SARVAM=off, VS_MODELS=offline, no SARVAM_API_KEY or disabled in models.yaml)")
    from vakeel_sahayak.models.sarvam.adapters import SarvamTts

    return SarvamTts()


def get_langid() -> object | None:
    """Sarvam `/text-lid` (`SarvamLangId`) for Munshi's script detection, or None when Sarvam is not active (the local heuristic then applies)."""
    if "langid" in _OVERRIDES:
        return _OVERRIDES["langid"]
    if not _sarvam_active("language_id"):
        return None
    from vakeel_sahayak.models.sarvam.adapters import SarvamLangId

    return SarvamLangId()


@cache
def _nli_cached(mode: str) -> NliClient:
    from vakeel_sahayak.models.nli import DebertaNliClient, OfflineNliClient

    if mode == "offline":
        return OfflineNliClient()
    if DebertaNliClient.available():
        return DebertaNliClient()
    if mode == "real":
        raise ModelUnavailable("VS_MODELS=real but transformers/torch are missing, so DeBERTa NLI cannot run", "models")
    return OfflineNliClient()


def get_nli() -> NliClient:
    """Configured NLI checker: DeBERTa-v3 when transformers and torch are installed, else the offline lexical checker.

    Returns:
        NliClient (`is_offline` tells which). Thresholds: `models.nli.nli_threshold(kind, client)`.
    """
    if "nli" in _OVERRIDES:
        return _OVERRIDES["nli"]  # type: ignore[return-value]
    return _nli_cached(models_mode())


def get_embedder() -> EmbeddingClient:
    """Configured embedder: BGE-M3 when installed, else the deterministic offline fallback (override with VS_EMBEDDER).

    Returns:
        EmbeddingClient.
    """
    from vakeel_sahayak.models.embeddings import get_embedder as _get

    return _get()  # type: ignore[return-value]
