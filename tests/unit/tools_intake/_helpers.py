"""Helpers for the intake-tool unit tests: argument-validation assertion, patching, counsel channel, fake clients."""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

from tests.fakes.models import FakeOcr, FakeVision
from vakeel_sahayak.models.base import OcrClient, VisionClient
from vakeel_sahayak.tools.base import ToolError


def assert_rejects(fn, *args, **kwargs) -> None:
    """The tool refuses a bad argument: raises ValueError (or FileNotFoundError for a missing file), or returns a ToolError.

    NotImplementedError is deliberately not caught: until the tool exists the test fails with it.
    """
    try:
        result = fn(*args, **kwargs)
    except (ValueError, FileNotFoundError):
        return
    assert isinstance(result, ToolError), f"expected ValueError or ToolError for bad arguments, got {result!r}"


def patch_everywhere(monkeypatch, module_name: str, attr: str, value: Any) -> None:
    """Patch `module.attr` at its source and on every imported vakeel_sahayak module aliasing it (raising=False)."""
    mod = importlib.import_module(module_name)
    original = getattr(mod, attr, None)
    monkeypatch.setattr(mod, attr, value, raising=False)
    for name, other in list(sys.modules.items()):
        if name.startswith("vakeel_sahayak") and other is not None and other is not mod:
            if original is not None and getattr(other, attr, None) is original:
                monkeypatch.setattr(other, attr, value, raising=False)


class AnyImageOcr(OcrClient):
    """OCR that returns the same transcript for any image (the tool renders the page itself, so bytes are unknown)."""

    def __init__(self, text: str = "FIR No. 112/2024", conf: float = 0.88) -> None:
        self.text, self.conf = text, conf
        self.calls: list[tuple[bytes, str]] = []

    def ocr(self, image: bytes, lang: str):
        self.calls.append((image, lang))
        return self.text, self.conf, [[0.0, 0.0, 100.0, 20.0]]


class AnyImageVision(VisionClient):
    """Vision transcription returning the same text for any image."""

    def __init__(self, text: str = "transcribed page text") -> None:
        self.text = text
        self.calls: list[bytes] = []

    def transcribe_page(self, image: bytes, lang_hint: str | None = None) -> str:
        self.calls.append(image)
        return self.text


__all__ = ["AnyImageOcr", "AnyImageVision", "FakeOcr", "FakeVision", "assert_rejects", "patch_everywhere", "install_counsel"]


class CounselChannel:
    """Stand-in for the LangGraph interrupt through which ask_user reaches counsel."""

    def __init__(self, answer: str = "counsel answer") -> None:
        self.answer = answer
        self.payloads: list[Any] = []

    @staticmethod
    def questions_in(payload: Any) -> list[str]:
        if isinstance(payload, dict):
            for key in ("questions", "question"):
                if key in payload:
                    q = payload[key]
                    return list(q) if isinstance(q, (list, tuple)) else [q]
        if isinstance(payload, (list, tuple)):
            return list(payload)
        return [str(payload)]

    def interrupt(self, payload: Any) -> list[str]:
        self.payloads.append(payload)
        return [f"{self.answer} {i + 1}" for i, _ in enumerate(self.questions_in(payload))]

    @property
    def asked(self) -> list[str]:
        """All questions put to counsel across calls, in order."""
        return [q for p in self.payloads for q in self.questions_in(p)]


def install_counsel(monkeypatch) -> CounselChannel:
    """Route ask_user's blocking call to a recording stub.

    ASSUMPTION: ask_user blocks through a callable named `interrupt` (LangGraph's `interrupt`), either imported at module
    level into `vakeel_sahayak.tools.interaction` or imported lazily from `langgraph.types`. Both are patched.
    """
    channel = CounselChannel()
    interaction = importlib.import_module("vakeel_sahayak.tools.interaction")
    monkeypatch.setattr(interaction, "interrupt", channel.interrupt, raising=False)
    try:
        types_mod = importlib.import_module("langgraph.types")
        monkeypatch.setattr(types_mod, "interrupt", channel.interrupt, raising=False)
    except ImportError:
        fake_pkg = types.ModuleType("langgraph")
        fake_types = types.ModuleType("langgraph.types")
        fake_types.interrupt = channel.interrupt  # type: ignore[attr-defined]
        fake_pkg.types = fake_types  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "langgraph", fake_pkg)
        monkeypatch.setitem(sys.modules, "langgraph.types", fake_types)
    return channel
