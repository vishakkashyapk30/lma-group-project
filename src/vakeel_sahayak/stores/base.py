"""Store base classes (plan §5.1)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vakeel_sahayak.schemas.enums import Shelf, StoreName


class Store(ABC):
    """Base class of every store (plan §5.1). All shared stores enforce the leakage rules: test orders and same-FIR orders are excluded; queries only see documents dated before the case's order (plan §2)."""

    name: StoreName
    shelf: Shelf
    index_kind: str  # exact | graph | hybrid | vector

    @abstractmethod
    def open(self, path: str | None = None) -> None:
        """Open the on-disk store (SQLite / LanceDB / networkx pickle).

        Args:
            path: store file or directory; defaults from configs/stores.yaml
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
        raise NotImplementedError

    @abstractmethod
    def count(self) -> int:
        """Number of rows (for the size estimates in plan §5.1 and build reports).

        Returns:
            Row count.
        """
        raise NotImplementedError


class SharedStore(Store):
    """A shared store built offline from Open India Law; read-only at run time."""

    @abstractmethod
    def build(self, source_dir: str, out_dir: str) -> None:
        """Build the store from interim data (called by pipelines/store_builders).

        Args:
            source_dir: see behaviour
            out_dir: see behaviour
        """
        raise NotImplementedError


class CaseStore(Store):
    """A per-case private store living on the laptop (plan §5.1 'Case')."""

    @abstractmethod
    def bind_case(self, case_id: str) -> None:
        """Select the case this store instance serves.

        Args:
            case_id: see behaviour
        """
        raise NotImplementedError
