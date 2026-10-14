"""Shared test-set utilities and manifest format (plan §15.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TestSetManifest(BaseModel):
    """Description of a constructed test set."""

    set_id: str  # T1..T9
    size: int
    answers_from: str
    used_for: list[str] = Field(default_factory=list)
    path: str


def write_manifest(manifest: TestSetManifest, out_dir: str) -> None:
    """Write manifest.json next to the data.

    Args:
        manifest: see behaviour
        out_dir: see behaviour
    """
    raise NotImplementedError


def faker_names(seed: int, n: int) -> list[str]:
    """Synthetic Indian names (Faker) for companion documents and leak tests.

    Args:
        seed: see behaviour
        n: see behaviour

    Returns:
        Names.
    """
    raise NotImplementedError
