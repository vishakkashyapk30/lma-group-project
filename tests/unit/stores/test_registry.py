"""open_store and open_all (plan §5.1, §5.5).

Dispatch is tested with every store class's `open` (and `bind_case`) patched to a recorder, so no on-disk store is needed;
the tests fail until open_store/open_all are implemented. ASSUMPTION: a case.* store requested without a case_id raises ValueError.
"""

from __future__ import annotations

import importlib

import pytest

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.stores.base import CaseStore, SharedStore
from vakeel_sahayak.stores.registry import STORE_CLASSES, open_all, open_store

CASE_STORES = [StoreName.CASE_DOCS, StoreName.CASE_TIMELINE, StoreName.CASE_FACTS]
SHARED = [s for s in StoreName if s not in CASE_STORES]


def cls_of(name: StoreName) -> type:
    module, _, cls = STORE_CLASSES[name.value].rpartition(".")
    return getattr(importlib.import_module(module), cls)


@pytest.fixture()
def recorder(monkeypatch):
    """Patch open/bind_case on all ten classes; returns the list of (store name, method, args) calls."""
    calls: list[tuple[str, str, tuple]] = []
    for name in StoreName:
        cls = cls_of(name)

        def _open(self, path=None, _n=name.value):
            calls.append((_n, "open", (path,)))

        monkeypatch.setattr(cls, "open", _open)
        if issubclass(cls, CaseStore):

            def _bind(self, case_id, _n=name.value):
                calls.append((_n, "bind_case", (case_id,)))

            monkeypatch.setattr(cls, "bind_case", _bind)
    return calls


@pytest.mark.parametrize("name", SHARED, ids=[s.value for s in SHARED])
def test_open_store_returns_the_right_shared_class_and_opens_it(name, recorder):
    """open_store(name) returns an instance of the class registered for the name and opens it."""
    store = open_store(name, path="/nonexistent/store")
    assert type(store) is cls_of(name) and isinstance(store, SharedStore)
    assert store.name == name
    assert (name.value, "open", ("/nonexistent/store",)) in recorder


@pytest.mark.parametrize("name", CASE_STORES, ids=[s.value for s in CASE_STORES])
def test_open_store_case_store_is_bound_to_case(name, recorder):
    """A case.* store is opened and bound to the given case_id."""
    store = open_store(name, case_id="case-0007")
    assert type(store) is cls_of(name) and isinstance(store, CaseStore)
    assert (name.value, "bind_case", ("case-0007",)) in recorder
    assert any(c[0] == name.value and c[1] == "open" for c in recorder)


@pytest.mark.parametrize("name", CASE_STORES, ids=[s.value for s in CASE_STORES])
def test_open_store_case_store_requires_case_id(name, recorder):
    """case.* stores are per case: no case_id is a ValueError."""
    with pytest.raises(ValueError):
        open_store(name)


def test_open_store_shared_store_needs_no_case_id(recorder):
    """Shared stores open without a case_id and are never bound to a case."""
    open_store(StoreName.LAW_STATUTES)
    assert not [c for c in recorder if c[1] == "bind_case"]


def test_open_store_default_path_is_none_to_use_stores_yaml(recorder):
    """Without `path` the store is opened with path=None so it falls back to configs/stores.yaml."""
    open_store(StoreName.CASELAW_REASONING)
    assert ("caselaw.reasoning", "open", (None,)) in recorder


def test_open_all_returns_all_ten_stores(recorder):
    """open_all returns a mapping keyed by StoreName with all ten stores, each of the registered class."""
    stores = open_all(AppConfig(), case_id="case-0007")
    assert set(stores) == set(StoreName) and len(stores) == 10
    for name, store in stores.items():
        assert type(store) is cls_of(name)


def test_open_all_binds_case_stores_to_the_case(recorder):
    """All three case stores are bound to the case_id."""
    open_all(AppConfig(), case_id="case-0007")
    bound = {c[0] for c in recorder if c[1] == "bind_case" and c[2] == ("case-0007",)}
    assert bound == {s.value for s in CASE_STORES}


def test_open_all_without_case_id_raises(recorder):
    """open_all needs a case_id because three of the ten stores are per case."""
    with pytest.raises(ValueError):
        open_all(AppConfig())
