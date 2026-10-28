"""Hosted LLM providers by CONFIGURATION: adding a provider is a yaml block plus an environment variable, no code change.

Providers come from configs/models.yaml `providers:` and, merged over it entry by entry, from an optional UNTRACKED override file
(`configs/providers.local.yaml`, or the path in `VS_PROVIDERS_FILE`). Each entry:

    providers:
      <name>:                         # what VS_LLM_BACKEND / VS_LABELER / VS_TEACHER name
        protocol: openai_compat       # openai_compat (any /chat/completions service) | gemini_native (generateContent) | builtin
        base_url: https://...         # for openai_compat the URL the chat path is appended to
        chat_path: /chat/completions  # openai_compat only (default /chat/completions)
        api_version: v1beta           # gemini_native only
        auth_header: Authorization    # header that carries the key (never the URL)
        auth_scheme: Bearer           # prefix of the header value ('' for a bare key, e.g. x-goog-api-key)
        key_env: GROQ_API_KEY         # env var with the key (default <NAME>_API_KEY); a pool: <key_env>S (comma list) or <key_env>_1 .. _N
        free: true                    # free tier (no money); `paid: true` puts the provider behind the paid lock (models/paid_lock.py)
        data_class_allowed: public_only   # public_only | pseudonymised | consented: the privacy gate reads this (sarvam.policy.authorize)
        structured: schema            # schema | json_mode | prompt  (how JSON is asked for; degraded automatically on a 400)
        system_instruction: true      # false: the system text is folded into the first user turn
        thinking: {budget: 0}         # gemini_native: thinkingConfig; openai_compat: {reasoning_effort: low} etc.
        max_tokens_field: max_tokens  # openai_compat: or max_completion_tokens
        default_model: <id>
        roles: {agents: <id>, labeler: <id>, teacher: <id>}   # optional per-role model ids
        failover: [<id>, ...]         # optional: models tried in order when one model's daily cap is hit (opt-in, VS_HOSTED_FAILOVER=1)
        family: <name>                # model family for the labeler-independence rule (default: from the model id)
        quota_day_tz: UTC             # time zone of the daily counter (Google resets at midnight Pacific)
        limits: {rpm: 10, rpd: 500, tpm: 250000}   # provider default
        models:                       # limits (and quirks) belong to a MODEL
          <id>: {rpm: 15, rpd: 500, tpm: 250000, system_instruction: false, structured: prompt, family: gemma}

`builtin` entries (openai, sarvam) keep their special adapters (`models.openai`, `models.sarvam`); the registry only records their
policy fields (paid, data class) so the lock and the gate see one list. A provider entry with an unknown protocol is ignored with a
warning. The key value is never read here: only whether its variable is set.
"""

from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("vakeel_sahayak.registry")

PROTOCOLS = ("openai_compat", "gemini_native", "builtin")
DATA_CLASS_LEVELS = ("public_only", "pseudonymised", "consented")
BUILTIN = ("openai", "sarvam")
OVERRIDE_ENV = "VS_PROVIDERS_FILE"
OVERRIDE_DEFAULT = "providers.local.yaml"  # next to configs/models.yaml; gitignored
FAILOVER_ENV = "VS_HOSTED_FAILOVER"


@dataclass(frozen=True)
class ProviderSpec:
    """One hosted provider as configured."""

    name: str
    protocol: str
    base_url: str = ""
    chat_path: str = "/chat/completions"
    api_version: str = "v1beta"
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    key_env: str = ""
    free: bool = False
    paid: bool = False
    data_class_allowed: str = "public_only"
    structured: str = "schema"
    system_instruction: bool = True
    thinking: dict[str, Any] = field(default_factory=dict)
    max_tokens_field: str = "max_tokens"
    max_tokens_cap: int = 4096
    default_model: str = ""
    roles: dict[str, str] = field(default_factory=dict)
    failover: tuple[str, ...] = ()
    family: str = ""
    quota_day_tz: str = "UTC"
    limits: dict[str, int] = field(default_factory=dict)
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeout_s: float = 120.0
    retries: dict[str, float] = field(default_factory=dict)
    max_wait_s: float = 900.0
    learn: dict[str, float] = field(default_factory=dict)
    mode_env: str = ""
    enabled: bool = False
    mode: str = "public"
    models_path: str = ""  # gemini_native: GET /<api_version>/models lists the ids the key can use

    @property
    def builtin(self) -> bool:
        """True for openai and sarvam (their own adapters)."""
        return self.protocol == "builtin"

    def model_for(self, role: str | None = None) -> str:
        """The model id for a role ('agents', 'labeler', 'teacher'), else the default model."""
        return str((self.roles or {}).get(role or "", "") or self.default_model)

    def model_cfg(self, model: str) -> dict[str, Any]:
        """The entry of a model (empty when unlisted)."""
        return dict((self.models or {}).get(model) or {})

    def limits_for(self, model: str) -> dict[str, int]:
        """{'rpm', 'rpd', 'tpm'} of a model: env `VS_<NAME>_RPM|RPD|TPM`, else the model entry, else the provider's `limits`, else low defaults."""
        base = {"rpm": 5, "rpd": 20, "tpm": 16000}
        out: dict[str, int] = {}
        m = self.model_cfg(model)
        for k in ("rpm", "rpd", "tpm"):
            raw: Any = os.environ.get(f"VS_{self.name.upper()}_{k.upper()}")
            if raw is None or not str(raw).strip():
                raw = m.get(k, (self.limits or {}).get(k, base[k]))
            try:
                v = int(float(str(raw)))
            except (TypeError, ValueError):
                v = base[k]
            out[k] = max(0, v)
        return out

    def quirk(self, model: str, key: str, default: Any = None) -> Any:
        """A per-model setting (system_instruction, structured, thinking, family) falling back to the provider's."""
        m = self.model_cfg(model)
        if key in m:
            return m[key]
        return getattr(self, key, default) if hasattr(self, key) else default

    def family_of(self, model: str | None) -> str:
        """Model family of a model of this provider (model entry `family`, else provider `family`, else from the id)."""
        fam = self.model_cfg(model or "").get("family") or self.family
        if fam:
            return str(fam)
        from vakeel_sahayak.models.base import model_family

        return model_family(model or self.default_model)

    def failover_models(self, first: str) -> list[str]:
        """`first`, then the configured failover models when `VS_HOSTED_FAILOVER=1` (one model only otherwise: paired comparisons need one model)."""
        out = [first]
        if (os.environ.get(FAILOVER_ENV) or "").strip().lower() in ("1", "true", "yes"):
            out += [m for m in self.failover if m and m != first]
        return out


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _override_path() -> Path | None:
    raw = os.environ.get(OVERRIDE_ENV)
    if raw and raw.strip():
        return Path(raw.strip())
    try:
        from vakeel_sahayak.config import resolve_config_dir

        return Path(resolve_config_dir(None)) / OVERRIDE_DEFAULT
    except Exception:  # noqa: BLE001
        return None


_CACHE: dict[str, Any] = {}


def _stamp() -> tuple[Any, ...]:
    """What the provider list depends on: the config dir, the override path and both files' modification times."""
    try:
        from vakeel_sahayak.config import resolve_config_dir

        cdir = Path(resolve_config_dir(None))
    except Exception:  # noqa: BLE001
        cdir = Path("configs")
    over = _override_path()
    times = []
    for p in (cdir / "models.yaml", over):
        try:
            times.append(p.stat().st_mtime_ns if p is not None else None)
        except OSError:
            times.append(None)
    return (str(cdir), str(over), *times)


def raw_providers() -> dict[str, dict[str, Any]]:
    """`providers:` of configs/models.yaml merged with the untracked override file (entry by entry, key by key); re-read when a file changes."""
    stamp = _stamp()
    if _CACHE.get("stamp") == stamp:
        return copy.deepcopy(_CACHE["value"])
    value = _read_providers()
    _CACHE.update(stamp=stamp, value=value)
    return copy.deepcopy(value)


def _read_providers() -> dict[str, dict[str, Any]]:
    try:
        from vakeel_sahayak.config import load_config

        base = dict(load_config().models.get("providers") or {})
    except (FileNotFoundError, ValueError):
        base = {}
    path = _override_path()
    if path is not None and path.is_file():
        import yaml

        try:
            extra = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            log.warning("provider override file %s is unreadable (%s); ignored", path, type(exc).__name__)
            extra = {}
        extra = extra.get("providers", extra) if isinstance(extra, dict) else {}
        base = _merge(base, extra if isinstance(extra, dict) else {})
    return {str(k): v for k, v in base.items() if isinstance(v, dict)}


_FIELDS = set(ProviderSpec.__dataclass_fields__)


def _spec(name: str, raw: dict[str, Any]) -> ProviderSpec | None:
    protocol = str(raw.get("protocol") or ("builtin" if name in BUILTIN else ""))
    if protocol not in PROTOCOLS:
        log.warning("provider %r has unknown protocol %r (use one of %s); ignored", name, protocol, PROTOCOLS)
        return None
    level = str(raw.get("data_class_allowed") or "public_only")
    if level not in DATA_CLASS_LEVELS:
        log.warning("provider %r: data_class_allowed %r is unknown; using public_only", name, level)
        level = "public_only"
    kw = {k: v for k, v in raw.items() if k in _FIELDS and k not in ("name", "protocol", "data_class_allowed")}
    if "failover" in kw:
        kw["failover"] = tuple(str(m) for m in (kw["failover"] or []))
    if "models" in kw:
        kw["models"] = {str(k): dict(v or {}) for k, v in (kw["models"] or {}).items()}
    if protocol != "builtin":
        kw.setdefault("key_env", f"{name.upper().replace('-', '_')}_API_KEY")  # gemini -> GEMINI_API_KEY (configs never need to spell a key variable)
    if protocol == "gemini_native":
        kw.setdefault("auth_header", "x-goog-api-key")
        kw.setdefault("auth_scheme", "")
    try:
        return ProviderSpec(name=name, protocol=protocol, data_class_allowed=level, **kw)
    except TypeError as exc:
        log.warning("provider %r is malformed (%s); ignored", name, exc)
        return None


def providers() -> dict[str, ProviderSpec]:
    """Every configured provider by name (read fresh each time: config and env may change between calls in tests)."""
    out: dict[str, ProviderSpec] = {}
    for name, raw in raw_providers().items():
        spec = _spec(name.strip().lower(), raw)
        if spec is not None:
            out[spec.name] = spec
    return out


def get_provider(name: str) -> ProviderSpec | None:
    """The provider named `name`, or None."""
    return providers().get((name or "").strip().lower())


def provider_names() -> list[str]:
    """Names of every configured provider (builtin ones included)."""
    return sorted(providers())


def hosted_names() -> list[str]:
    """Names of the generic (non-builtin) providers: these run through `models.hosted.HostedLLMClient`."""
    return sorted(n for n, s in providers().items() if not s.builtin)


def is_hosted(name: str | None) -> bool:
    """True when `name` is a generic configured provider."""
    spec = get_provider(name or "")
    return spec is not None and not spec.builtin


def paid_provider_names() -> list[str]:
    """Providers marked `paid: true` (they sit behind the paid lock)."""
    return sorted(n for n, s in providers().items() if s.paid)


def data_class_allowed(name: str) -> str | None:
    """The most the provider may receive ('public_only', 'pseudonymised', 'consented'), or None for an unconfigured name."""
    spec = get_provider(name)
    return spec.data_class_allowed if spec else None
