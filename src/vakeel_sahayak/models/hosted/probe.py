"""Startup probe of a configured provider: which model ids the key can use, and a one-request smoke call of the chosen model.

    python -m vakeel_sahayak.models.hosted.probe models [--provider gemini]            # GET /v1beta/models (gemini_native) or /models (openai_compat)
    python -m vakeel_sahayak.models.hosted.probe smoke  [--provider gemini] [--model ID]

`models` lists, per key fingerprint, the ids that support generateContent (Gemini) or every listed id (OpenAI-compatible), and marks which
configured models are missing. It sends no prompt and counts no quota row (listing models is not a generation request).

`smoke` sends ONE short PUBLIC request (constructed text, `public_scope`) with a system instruction and a JSON schema through the normal client,
so the gate, the key pool and the ledger apply. If the model refuses the system instruction or JSON mode (Gemma on the Gemini API may), the
client falls back to folding the system text into the user turn and to JSON in the prompt; the mode that worked is printed and remembered in the
ledger for the model, and the run manifest records it. The mode variable must allow public data (`VS_GEMINI=public`; `make gemini-models` sets it).
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx

from vakeel_sahayak.models.hosted.keys import pool, scrub
from vakeel_sahayak.models.registry import ProviderSpec, get_provider

SMOKE_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}}, "required": ["ok", "word"]}
SMOKE_MESSAGES = [
    {"role": "system", "content": "You answer with a JSON object only. Set word to the word given by the user."},
    {"role": "user", "content": "The word is: bail. Set ok to true."},
]


def _json_object(text: str) -> Any:
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    try:
        return json.loads(s[i : j + 1]) if 0 <= i < j else None
    except ValueError:
        return None


def _spec(name: str) -> ProviderSpec:
    spec = get_provider(name)
    if spec is None or spec.builtin:
        raise SystemExit(f"no generic provider {name!r} in configs/models.yaml providers:")
    return spec


def list_models(spec: ProviderSpec, transport: httpx.BaseTransport | None = None, environ: dict[str, str] | None = None) -> dict[str, Any]:
    """{key fingerprint: {'models': [ids], 'error': str|None}} plus 'configured_missing' (configured ids no key lists)."""
    out: dict[str, Any] = {}
    keys = pool(spec.key_env, environ)
    if not keys:
        raise SystemExit(f"{spec.key_env} is not set (nor {spec.key_env}S / {spec.key_env}_1..N): nothing to probe")
    base = spec.base_url.rstrip("/")
    for key in keys:
        ids: list[str] = []
        err = None
        headers = {spec.auth_header: f"{spec.auth_scheme} {key.value}".strip() if spec.auth_scheme else key.value}
        try:
            with httpx.Client(transport=transport, timeout=float(spec.timeout_s)) as client:
                if spec.protocol == "gemini_native":
                    token = None
                    for _ in range(50):
                        params = {"pageSize": "1000", **({"pageToken": token} if token else {})}
                        resp = client.get(f"{base}/{spec.api_version}/models", headers=headers, params=params)
                        if resp.status_code >= 400:
                            err = scrub(f"HTTP {resp.status_code}: {resp.text[:200]}", keys)
                            break
                        data = resp.json()
                        for m in data.get("models") or []:
                            if "generateContent" in (m.get("supportedGenerationMethods") or []):
                                ids.append(str(m.get("name", "")).removeprefix("models/"))
                        token = data.get("nextPageToken")
                        if not token:
                            break
                else:
                    resp = client.get(base + "/models", headers=headers)
                    if resp.status_code >= 400:
                        err = scrub(f"HTTP {resp.status_code}: {resp.text[:200]}", keys)
                    else:
                        ids = [str(m.get("id", "")).removeprefix("models/") for m in resp.json().get("data") or []]
        except httpx.HTTPError as exc:
            err = type(exc).__name__
        out[key.fp] = {"models": sorted(set(ids)), "error": err}
    listed = set().union(*(set(v["models"]) for v in out.values())) if out else set()
    return {"provider": spec.name, "keys": out, "configured_missing": sorted(m for m in (spec.models or {}) if m not in listed)}


def smoke(spec: ProviderSpec, model: str | None = None, **client_kw: Any) -> dict[str, Any]:
    """One public request with a system instruction and a JSON schema; returns the model, the mode that worked, whether the reply is valid JSON."""
    from vakeel_sahayak.models.hosted.client import HostedLLMClient
    from vakeel_sahayak.models.sarvam.policy import DataClass, public_scope

    client = HostedLLMClient(spec, model, data=DataClass.PUBLIC, role="probe", **client_kw)
    with public_scope("probe-smoke"):
        text = client.chat(SMOKE_MESSAGES, max_tokens=64, temperature=0.0, json_schema=SMOKE_SCHEMA)
    obj = _json_object(text)
    return {"provider": spec.name, "model": client.model_id, "mode": client.last_mode, "served_model": client.version(),
            "json_ok": isinstance(obj, dict) and obj.get("word", "").strip().lower() == "bail"}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    """CLI (module doc)."""
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args.pop(0) if args else "models"

    def opt(name: str, default: str | None = None) -> str | None:
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default

    spec = _spec(opt("--provider", "gemini") or "gemini")
    if cmd == "models":
        rep = list_models(spec)
        if "--json" in args:
            print(json.dumps(rep, indent=2))
            return 0
        for fp, v in rep["keys"].items():
            print(f"{fp}: " + (f"ERROR {v['error']}" if v["error"] else f"{len(v['models'])} models: {', '.join(v['models'])}"))
        if rep["configured_missing"]:
            print("configured in configs/models.yaml but not listed for any key (fix the ids): " + ", ".join(rep["configured_missing"]))
        return 0
    if cmd == "smoke":
        rep = smoke(spec, opt("--model"))
        print(json.dumps(rep, indent=2))
        return 0 if rep["json_ok"] else 1
    print("usage: probe models|smoke [--provider NAME] [--model ID] [--json]", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
