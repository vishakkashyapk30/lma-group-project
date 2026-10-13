"""Where store files live (plan §5.5, configs/stores.yaml, configs/paths.yaml).

Every store is a SQLite file (hybrid stores optionally add a LanceDB folder next to it). The path in configs/stores.yaml
names the logical location (`caselaw/reasoning.lance`); the always-available SQLite file replaces its suffix with
`.sqlite` (`caselaw/reasoning.sqlite`). A store's `open(path)` accepts the file, the folder a build wrote into, or
':memory:'.
"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.config import load_config
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.schemas.ids import check_case_id

MEMORY = ":memory:"


def configured_relpath(name: StoreName) -> str:
    """The path of a store in configs/stores.yaml (relative to the stores folder), e.g. 'caselaw/reasoning.lance'."""
    shelf, _, key = name.value.partition(".")
    return str(load_config().stores[shelf][key]["path"])


def sqlite_name(name: StoreName) -> str:
    """File name of a store's SQLite file, e.g. 'reasoning.sqlite'."""
    return Path(configured_relpath(name).split("#")[0]).with_suffix(".sqlite").name


def resolve_shared_path(name: StoreName, path: str | None) -> str:
    """The SQLite file of a shared store.

    Args:
        name: store
        path: None for the configured default; a file; a folder (an existing folder, or a path without suffix)
            that holds the file a build wrote; or ':memory:'

    Returns:
        File path as a string, or ':memory:'.
    """
    if path == MEMORY:
        return MEMORY
    if path is None:
        rel = Path(configured_relpath(name)).with_suffix(".sqlite")
        return str(Path(load_config().paths.stores_dir) / rel)
    p = Path(path)
    if p.is_dir() or not p.suffix:
        return str(p / sqlite_name(name))
    return str(p)


def case_dir(case_id: str) -> Path:
    """Folder of one case (laptop only): data/cases/<case_id>.

    Raises:
        ValueError: for an invalid case id (it becomes a folder name).
    """
    return Path(load_config().paths.cases_dir) / check_case_id(case_id)


def resolve_case_path(name: StoreName, case_id: str, path: str | None) -> str:
    """The SQLite file of a case store: `docs.sqlite` for case.docs, `case.sqlite` (tables timeline, facts) for the others."""
    if path == MEMORY:
        return MEMORY
    file = "docs.sqlite" if name == StoreName.CASE_DOCS else "case.sqlite"
    if path is None:
        return str(case_dir(case_id) / file)
    p = Path(path)
    return str(p / file) if p.is_dir() or not p.suffix else str(p)
