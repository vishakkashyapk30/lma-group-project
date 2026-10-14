"""Fixtures of the store-builder tests: a synthetic interim directory and the fake embedder (no BGE-M3, no GPU)."""

from __future__ import annotations

import pytest

from tests.fakes.models import FakeEmbedder
from tests.unit.pipelines._helpers import patch_everywhere
from tests.unit.pipelines.store_builders._helpers import EXCLUDED, write_interim


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    """ASSUMPTION: builders obtain their embedder from `models.factory.get_embedder` (plan §12: all model calls go through `models/`)."""
    embedder = FakeEmbedder()
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_embedder", lambda: embedder)
    return embedder


@pytest.fixture()
def interim(tmp_path):
    return write_interim(tmp_path / "interim")


@pytest.fixture()
def excluded():
    return set(EXCLUDED)
