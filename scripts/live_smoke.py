"""Live smoke test of the hosted backends (Sarvam and OpenAI) with PUBLIC text only.

Keys are read from the repo's untracked `.env` (or the environment) into THIS process only and are never printed.
At most 3 tiny OpenAI calls (the spending cap and ledger still apply) and one call per Sarvam capability.
Usage: .venv/bin/python scripts/live_smoke.py [sarvam|openai|all]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vakeel_sahayak.config import parse_dotenv  # noqa: E402

for _k, _v in parse_dotenv(ROOT / ".env").items():
    if _k in ("SARVAM_API_KEY", "OPENAI_API_KEY") and _v and not os.environ.get(_k):
        os.environ[_k] = _v
os.environ["VS_EXTERNAL"] = "public"  # only public text may leave the machine in this script

from vakeel_sahayak.models.sarvam.policy import public_scope  # noqa: E402

TEXT = "The accused was arrested on 20.08.2024 and the charge sheet was filed on 02.11.2024."
RESULTS: list[tuple[str, bool, str]] = []


def step(name: str, fn) -> None:
    """Run one check; record pass/fail with a short, key-free note."""
    try:
        note = fn()
        RESULTS.append((name, True, str(note)[:140]))
    except Exception as exc:  # noqa: BLE001 - report every failure kind
        RESULTS.append((name, False, f"{type(exc).__name__}: {str(exc)[:120]}"))


def sarvam() -> None:
    if not os.environ.get("SARVAM_API_KEY"):
        RESULTS.append(("sarvam", False, "SARVAM_API_KEY not set")); return
    from vakeel_sahayak.models.sarvam.api import SarvamApi

    api = SarvamApi()
    with public_scope("live-smoke"):
        step("sarvam.language-id", lambda: f"lang={api.identify_language(TEXT).language_code}")
        step("sarvam.translate en->hi", lambda: f"{len(api.translate(TEXT, 'en-IN', 'hi-IN').text)} chars, devanagari={any(0x900 <= ord(c) <= 0x97F for c in api.translate(TEXT, 'en-IN', 'hi-IN').text)}")
        step("sarvam.chat", lambda: (lambda r: f"tokens in/out={r.prompt_tokens}/{r.completion_tokens}, reply={r.text.strip()[:30]!r}")(api.chat([{"role": "user", "content": "Reply with exactly the word OK."}], max_tokens=64)))
        step("sarvam.tts", lambda: (lambda r: f"audio chunks={len(getattr(r, 'audios', None) or getattr(r, 'audio', []) or [])}")(api.text_to_speech("The accused was arrested.", language="en")))


def openai() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        RESULTS.append(("openai", False, "OPENAI_API_KEY not set")); return
    from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
    from vakeel_sahayak.models.openai.ledger import report

    llm = OpenAILLMClient()
    with public_scope("live-smoke"):
        step("openai.chat", lambda: f"model={llm.version()}, reply={llm.chat([{'role': 'user', 'content': 'Reply with exactly the word OK.'}], max_tokens=64).strip()[:20]!r}, cost_usd={llm.spend_usd():.6f}")
        schema = {"type": "object", "properties": {"arrest_date": {"type": "string"}}, "required": ["arrest_date"], "additionalProperties": False}
        step("openai.structured-json", lambda: f"parsed={json.loads(llm.chat([{'role': 'user', 'content': 'Give the arrest date as YYYY-MM-DD: ' + TEXT}], max_tokens=96, json_schema=schema))}")
        step("openai.cache-hit-free", lambda: f"repeat call cache_hits={(llm.chat([{'role': 'user', 'content': 'Reply with exactly the word OK.'}], max_tokens=64), llm.cache_hits)[1]}")
    r = report()
    RESULTS.append(("openai.ledger", True, f"spent_usd={r.get('spent_usd')}, remaining_usd={r.get('remaining_usd')}, cap_usd={r.get('cap_usd')}"))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("sarvam", "all"):
        sarvam()
    if which in ("openai", "all"):
        openai()
    width = max(len(n) for n, _, _ in RESULTS)
    for name, ok, note in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}  {note}")
    sys.exit(0 if all(ok for _, ok, _ in RESULTS) else 1)
