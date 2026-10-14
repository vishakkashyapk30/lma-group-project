"""Helpers for the tool-module tests (case, caselaw, advocacy, drafting): install the in-memory stores and record which stores a tool opens.

The tools reach stores only through `vakeel_sahayak.stores.registry.open_store(name, path, case_id)` (skeleton.md, tests/fakes/__init__.py),
so "store routing" is tested by recording those calls: which StoreName was opened, and with which case id.
"""

from __future__ import annotations

import sys

from tests.fakes.stores import install_fake_stores
from tests.unit.tools_law_case._helpers import assert_tool_error  # noqa: F401  (re-exported)
from vakeel_sahayak.schemas.enums import StoreName


def install_recording_stores(monkeypatch, world) -> list[tuple[StoreName, str | None]]:
    """Install `world.stores` as `open_store` everywhere; return the list that every `open_store` call appends (name, case_id) to."""
    install_fake_stores(monkeypatch, world.stores)
    import vakeel_sahayak.stores.registry as registry

    fake = registry.open_store
    opened: list[tuple[StoreName, str | None]] = []

    def recording(name, path=None, case_id=None):
        opened.append((StoreName(name), case_id))
        return fake(name, path, case_id)

    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("vakeel_sahayak") and mod is not None and getattr(mod, "open_store", None) is fake:
            monkeypatch.setattr(mod, "open_store", recording)
    return opened


def stores_touched(world) -> set[StoreName]:
    """Stores of the world whose in-memory fake logged at least one call."""
    return {name for name, store in world.stores.items() if store.calls}
