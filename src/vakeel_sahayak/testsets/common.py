"""Shared test-set utilities and manifest format (plan §15.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TestSetManifest(BaseModel):
    """Description of a constructed test set."""

    __test__ = False  # not a pytest class

    set_id: str  # T1..T9
    size: int
    answers_from: str
    used_for: list[str] = Field(default_factory=list)
    path: str
    details: dict[str, Any] = Field(default_factory=dict)  # per-court, per-script and coverage statistics, split sizes, notes


def write_manifest(manifest: TestSetManifest, out_dir: str) -> None:
    """Write manifest.json next to the data (the directory is created when missing).

    Args:
        manifest: see behaviour
        out_dir: see behaviour
    """
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(manifest.model_dump_json(indent=1), encoding="utf-8")


def faker_names(seed: int, n: int) -> list[str]:
    """Synthetic Indian names (Faker) for companion documents and leak tests.

    Args:
        seed: sequence seed; the same seed always gives the same sequence, and a longer request extends a shorter one
        n: how many distinct names

    Returns:
        Names.
    """
    from faker import Faker

    fake = Faker("en_IN")
    fake.seed_instance(seed)
    names: list[str] = []
    seen: set[str] = set()
    while len(names) < n:
        name = fake.name().strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
